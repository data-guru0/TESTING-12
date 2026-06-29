import json
import uuid
import redis.asyncio as aioredis
from app.config import Config


async def push_job(redis: aioredis.Redis, config: Config, topic: str, session_id: str, output_format: str) -> str:
    job_id = str(uuid.uuid4())
    await redis.xadd(config.stream_key, {
        "job_id": job_id,
        "topic": topic,
        "session_id": session_id,
        "output_format": output_format,
    })
    return job_id


async def get_result(redis: aioredis.Redis, config: Config, job_id: str) -> dict | None:
    data = await redis.get(f"result:{job_id}")
    return json.loads(data) if data else None


async def set_result(redis: aioredis.Redis, config: Config, job_id: str, result: dict) -> None:
    await redis.setex(f"result:{job_id}", config.result_ttl, json.dumps(result))


async def ensure_group(redis: aioredis.Redis, config: Config) -> None:
    try:
        await redis.xgroup_create(config.stream_key, config.consumer_group, id="0", mkstream=True)
    except Exception:
        pass


async def consume_jobs(redis: aioredis.Redis, config: Config) -> list[dict]:
    messages = await redis.xreadgroup(
        config.consumer_group,
        config.consumer_name,
        {config.stream_key: ">"},
        count=1,
        block=5000,
    )
    if not messages:
        return []
    jobs = []
    for _, entries in messages:
        for msg_id, data in entries:
            jobs.append({"msg_id": msg_id, "data": data})
    return jobs


async def ack_job(redis: aioredis.Redis, config: Config, msg_id: str) -> None:
    await redis.xack(config.stream_key, config.consumer_group, msg_id)
