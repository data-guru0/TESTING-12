import json
import asyncio
from datetime import datetime
import redis.asyncio as aioredis
from sentence_transformers import SentenceTransformer
from app.config import Config
from app.pool import get_pool

_model = SentenceTransformer("all-MiniLM-L6-v2")


async def session_add(redis: aioredis.Redis, config: Config, session_id: str, role: str, content: str) -> None:
    key = f"session:{session_id}"
    await redis.rpush(key, json.dumps({"role": role, "content": content}))
    await redis.ltrim(key, -config.session_max_messages, -1)
    await redis.expire(key, config.session_ttl)


async def session_get(redis: aioredis.Redis, session_id: str) -> list[dict]:
    messages = await redis.lrange(f"session:{session_id}", 0, -1)
    return [json.loads(m) for m in messages]


async def db_migrate(config: Config) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id         TEXT PRIMARY KEY,
                topic      TEXT NOT NULL,
                report     TEXT NOT NULL,
                embedding  vector(384),
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS reports_embedding_idx
            ON reports USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {config.ivfflat_lists})
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS reports_topic_idx ON reports (topic)")
        await conn.execute("CREATE INDEX IF NOT EXISTS reports_created_idx ON reports (created_at DESC)")


async def ltm_store(config: Config, topic: str, report: str, report_id: str) -> None:
    embedding = await asyncio.to_thread(lambda: _model.encode(topic).tolist())
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO reports (id, topic, report, embedding, created_at)
            VALUES ($1, $2, $3, $4::vector, $5)
            ON CONFLICT (id) DO NOTHING
            """,
            report_id, topic, report, str(embedding), datetime.utcnow(),
        )


async def ltm_search(config: Config, topic: str) -> dict | None:
    embedding = await asyncio.to_thread(lambda: _model.encode(topic).tolist())
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, topic, report, created_at,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM reports
            WHERE created_at > NOW() - ($2 || ' days')::INTERVAL
              AND 1 - (embedding <=> $1::vector) > $3
            ORDER BY similarity DESC LIMIT 1
            """,
            str(embedding), str(config.ltm_days), config.ltm_threshold,
        )
        return dict(row) if row else None


async def ltm_search_related(config: Config, topic: str) -> str | None:
    """
    Finds a related (but not identical) previous report to use as reference context
    for the writer agent. Uses a lower threshold than ltm_search so it finds
    nearby topics rather than exact matches.
    """
    embedding = await asyncio.to_thread(lambda: _model.encode(topic).tolist())
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT report FROM reports
            WHERE 1 - (embedding <=> $1::vector) BETWEEN 0.5 AND $2
            ORDER BY created_at DESC LIMIT 1
            """,
            str(embedding), config.ltm_threshold - 0.01,
        )
        return row["report"] if row else None


async def ltm_diff(config: Config, topic: str) -> str | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT report, created_at FROM reports WHERE topic = $1 ORDER BY created_at DESC LIMIT 2",
            topic,
        )
        if len(rows) < 2:
            return None
        old_sentences = set(rows[1]["report"].split(". "))
        new_sentences = set(rows[0]["report"].split(". "))
        added = [f"[NEW] {s}" for s in list(new_sentences - old_sentences)[:config.ltm_diff_limit]]
        removed = [f"[REMOVED] {s}" for s in list(old_sentences - new_sentences)[:config.ltm_diff_limit]]
        return "\n".join(added + removed) or "No significant changes detected."
