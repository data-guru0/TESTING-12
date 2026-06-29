import asyncio
import httpx
import logging
from typing import TypedDict
from langgraph.graph import StateGraph, END, START
from langsmith import traceable
from app.config import Config
from app.retry import with_retry

logger = logging.getLogger(__name__)


class ResearchState(TypedDict):
    topic: str
    session_id: str
    session_history: list[dict]  # prior conversation turns passed into agent
    ltm_context: str             # related previous report passed to writer
    search_results: list[str]
    summaries: list[str]
    report: str
    verified: bool
    error: str
    iterations: int


async def _tz_call(config: Config, function_name: str, message: str) -> str:
    return await with_retry(
        lambda: _tz_call_once(config, function_name, message),
        max_retries=config.llm_max_retries,
        delay=config.llm_retry_delay,
    )


async def _tz_call_once(config: Config, function_name: str, message: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{config.tensorzero_url}/inference",
            json={
                "function_name": function_name,
                "input": {"messages": [{"role": "user", "content": message}]},
            },
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]


class SearchAgent:
    """Finds key facts. Receives session history so it understands what the user has asked before."""

    def __init__(self, config: Config):
        self.config = config

    @traceable(run_type="tool", name="agent:search")
    async def run(self, topic: str, session_history: list[dict]) -> str:
        logger.info(f"SearchAgent: researching '{topic}'")

        history_ctx = ""
        if session_history:
            recent = session_history[-4:]  # last 4 turns for context
            history_ctx = "\n\nPrevious conversation context (use this to understand what the user already knows and what angle they care about):\n"
            history_ctx += "\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)

        return await _tz_call(
            self.config,
            "research_summarize",
            f"You are a research specialist. Find and list 5 key facts, recent developments, "
            f"and important details about: {topic}. Be thorough and specific."
            f"{history_ctx}",
        )


class SummarizeAgent:
    """Condenses raw search results into structured bullet points."""

    def __init__(self, config: Config):
        self.config = config

    @traceable(run_type="tool", name="agent:summarize")
    async def run(self, search_results: list[str]) -> str:
        logger.info("SummarizeAgent: condensing search results")
        combined = "\n\n".join(search_results)
        return await _tz_call(
            self.config,
            "research_summarize",
            f"Summarize these research findings into clear, structured bullet points:\n\n{combined}",
        )


class WriterAgent:
    """
    Produces the final structured report. If a related previous report exists in LTM,
    it uses it as reference so the new report builds on existing knowledge rather than
    starting from scratch.
    """

    def __init__(self, config: Config):
        self.config = config

    @traceable(run_type="tool", name="agent:writer")
    async def run(self, topic: str, summaries: list[str], ltm_context: str) -> str:
        logger.info("WriterAgent: drafting report")
        combined = "\n\n".join(summaries)

        ltm_section = ""
        if ltm_context:
            ltm_section = (
                f"\n\nPREVIOUS RESEARCH ON A RELATED TOPIC (use this as reference — "
                f"build on it, correct outdated information, and highlight what has changed):\n"
                f"{ltm_context[:2000]}"
            )

        return await _tz_call(
            self.config,
            "report_write",
            f"Write a comprehensive, well-structured research report on: '{topic}'\n\n"
            f"Current research findings:\n{combined}"
            f"{ltm_section}\n\n"
            f"Include: Executive Summary, Key Findings, Analysis, and Conclusion.",
        )


class CriticAgent:
    """Verifies factual consistency and logical coherence of the report."""

    def __init__(self, config: Config):
        self.config = config

    @traceable(run_type="tool", name="agent:critic")
    async def run(self, report: str) -> bool:
        logger.info("CriticAgent: verifying report")
        check = await _tz_call(
            self.config,
            "research_summarize",
            f"Review this report for factual consistency and logical coherence. "
            f"Reply with YES if it passes or NO with a brief reason:\n\n"
            f"{report[:self.config.agent_report_truncate]}",
        )
        return check.strip().upper().startswith("YES")


class OrchestratorAgent:
    """
    Coordinates all sub-agents. Passes session history to SearchAgent and LTM context
    to WriterAgent so the pipeline is genuinely context-aware. If the critic rejects
    the report it loops back for another pass (up to agent_max_iterations times).
    """

    def __init__(self, config: Config):
        self.config = config
        self.search_agent = SearchAgent(config)
        self.summarize_agent = SummarizeAgent(config)
        self.writer_agent = WriterAgent(config)
        self.critic_agent = CriticAgent(config)

    @traceable(run_type="chain", name="orchestrator:search")
    async def search_node(self, state: ResearchState) -> dict:
        result = await self.search_agent.run(state["topic"], state.get("session_history", []))
        return {"search_results": [result]}

    @traceable(run_type="chain", name="orchestrator:summarize")
    async def summarize_node(self, state: ResearchState) -> dict:
        summary = await self.summarize_agent.run(state["search_results"])
        return {"summaries": [summary]}

    @traceable(run_type="chain", name="orchestrator:write")
    async def write_node(self, state: ResearchState) -> dict:
        report = await self.writer_agent.run(
            state["topic"],
            state["summaries"],
            state.get("ltm_context", ""),
        )
        return {"report": report, "iterations": state.get("iterations", 0) + 1}

    @traceable(run_type="chain", name="orchestrator:verify")
    async def verify_node(self, state: ResearchState) -> dict:
        verified = await self.critic_agent.run(state["report"])
        return {"verified": verified}

    def route(self, state: ResearchState) -> str:
        """Orchestrator decision: retry search or finish."""
        if not state["verified"] and state.get("iterations", 0) < self.config.agent_max_iterations:
            logger.info(f"Critic rejected report — retrying (iteration {state['iterations']})")
            return "search"
        return END


def build_graph(config: Config):
    orchestrator = OrchestratorAgent(config)
    workflow = StateGraph(ResearchState)

    workflow.add_node("search", orchestrator.search_node)
    workflow.add_node("summarize", orchestrator.summarize_node)
    workflow.add_node("write", orchestrator.write_node)
    workflow.add_node("verify", orchestrator.verify_node)

    workflow.add_edge(START, "search")
    workflow.add_edge("search", "summarize")
    workflow.add_edge("summarize", "write")
    workflow.add_edge("write", "verify")
    workflow.add_conditional_edges(
        "verify",
        orchestrator.route,
        {"search": "search", END: END},
    )

    return workflow.compile()
