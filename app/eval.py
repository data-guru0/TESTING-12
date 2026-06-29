import asyncio
import re
import httpx
import logging
from langsmith import Client, traceable
from app.config import Config
from app.retry import with_retry

logger = logging.getLogger(__name__)


_ls_client: Client | None = None


def _ls() -> Client:
    global _ls_client
    if _ls_client is None:
        _ls_client = Client()
    return _ls_client


def _parse_score(text: str) -> float:
    m = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10", text, re.IGNORECASE)
    return round(float(m.group(1)) / 10.0, 2) if m else 0.5


async def _judge(config: Config, prompt: str) -> str:
    return await with_retry(
        lambda: _judge_once(config, prompt),
        max_retries=config.llm_max_retries,
        delay=config.llm_retry_delay,
    )


async def _judge_once(config: Config, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{config.tensorzero_url}/inference",
            json={
                "function_name": "research_summarize",
                "input": {"messages": [{"role": "user", "content": prompt}]},
            },
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]


@traceable(run_type="chain", name="eval:relevance")
async def eval_relevance(config: Config, topic: str, report: str) -> dict:
    verdict = await _judge(
        config,
        f"Rate how relevant this research report is to the topic '{topic}'.\n"
        f"Reply with exactly: SCORE: X/10 on the first line, then one sentence reason.\n\n"
        f"Report:\n{report[:config.eval_report_truncate]}",
    )
    return {"key": "relevance", "score": _parse_score(verdict), "comment": verdict[:config.eval_comment_truncate]}


@traceable(run_type="chain", name="eval:completeness")
async def eval_completeness(config: Config, report: str) -> dict:
    verdict = await _judge(
        config,
        f"Does this research report contain all four required sections: "
        f"Executive Summary, Key Findings, Analysis, and Conclusion?\n"
        f"Reply with exactly: SCORE: X/10 on the first line, then one sentence reason.\n\n"
        f"Report:\n{report[:config.eval_report_truncate]}",
    )
    return {"key": "completeness", "score": _parse_score(verdict), "comment": verdict[:config.eval_comment_truncate]}


@traceable(run_type="chain", name="eval:hallucination_risk")
async def eval_hallucination(config: Config, topic: str, report: str) -> dict:
    verdict = await _judge(
        config,
        f"Check this report on '{topic}' for hallucinations — fabricated statistics, "
        f"impossible dates, or claims that contradict well-known facts.\n"
        f"Score: 1/10 = zero hallucinations detected, 10/10 = many hallucinations.\n"
        f"Reply with exactly: SCORE: X/10 on the first line, then list any suspicious claims.\n\n"
        f"Report:\n{report[:config.eval_report_truncate]}",
    )
    return {"key": "hallucination_risk", "score": _parse_score(verdict), "comment": verdict[:config.eval_comment_truncate]}


@traceable(run_type="chain", name="eval:overall_quality")
async def eval_quality(config: Config, topic: str, report: str) -> dict:
    verdict = await _judge(
        config,
        f"Rate the overall quality of this research report on '{topic}'.\n"
        f"Consider: depth of analysis, factual accuracy, writing clarity, logical structure, "
        f"and practical usefulness to a business analyst.\n"
        f"Reply with exactly: SCORE: X/10 on the first line, then two sentences explaining the rating.\n\n"
        f"Report:\n{report[:config.eval_report_truncate]}",
    )
    return {"key": "overall_quality", "score": _parse_score(verdict), "comment": verdict[:config.eval_comment_truncate]}


@traceable(run_type="chain", name="evaluate-report")
async def evaluate_report(config: Config, job_id: str, topic: str, report: str) -> dict:
    """Runs all 4 LLM judges in parallel. Called on EVERY research job automatically."""
    results = await asyncio.gather(
        eval_relevance(config, topic, report),
        eval_completeness(config, report),
        eval_hallucination(config, topic, report),
        eval_quality(config, topic, report),
    )
    scores = {r["key"]: r["score"] for r in results}
    try:
        client = _ls()
        try:
            dataset = client.read_dataset(dataset_name=config.langsmith_dataset)
        except Exception:
            dataset = client.create_dataset(
                config.langsmith_dataset,
                description="Research agent LLM-as-judge evaluation results",
            )
        client.create_example(
            inputs={"topic": topic},
            outputs={"report_preview": report[:400]},
            dataset_id=dataset.id,
            metadata={"job_id": job_id, **scores},
        )
    except Exception as e:
        logger.warning(f"LangSmith logging failed for job {job_id}: {e}")
    return scores


async def fetch_recent_topics(limit: int = 10) -> list[str]:
    """Pull distinct topics from the reports table — real user queries, nothing hardcoded."""
    from app.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT topic FROM reports GROUP BY topic ORDER BY MAX(created_at) DESC LIMIT $1",
            limit,
        )
        return [row["topic"] for row in rows]


async def run_batch_evaluation(config: Config, graph, topics: list[str]) -> list[dict]:
    from app.agents import ResearchState
    from app.memory import ltm_search_related
    results = []
    for topic in topics:
        ltm_context = await ltm_search_related(config, topic) or ""
        state = ResearchState(
            topic=topic, session_id="batch-eval",
            session_history=[],
            ltm_context=ltm_context,
            search_results=[], summaries=[], report="",
            verified=False, error="", iterations=0,
        )
        final = await graph.ainvoke(state)
        scores = await evaluate_report(config, f"batch-{topic[:20]}", topic, final["report"])
        results.append({"topic": topic, "scores": scores})
    return results
