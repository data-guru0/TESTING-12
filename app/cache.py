import json
import numpy as np
import redis.asyncio as aioredis
from sentence_transformers import SentenceTransformer
from app.config import Config

_model = SentenceTransformer("all-MiniLM-L6-v2")
_CACHE_PREFIX = "semantic:"
_EMB_PREFIX = "emb:"


def _cosine_similarity(a: list, b: list) -> float:
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def _embed(text: str) -> list:
    return _model.encode(text).tolist()


async def cache_get(redis: aioredis.Redis, config: Config, query: str) -> str | None:
    query_emb = _embed(query)
    async for key in redis.scan_iter(f"{_EMB_PREFIX}*"):
        stored_emb = json.loads(await redis.get(key))
        if _cosine_similarity(query_emb, stored_emb) >= config.cache_similarity_threshold:
            cache_key = key.replace(_EMB_PREFIX, _CACHE_PREFIX)
            return await redis.get(cache_key)
    return None


async def cache_set(redis: aioredis.Redis, config: Config, query: str, result: str) -> None:
    key_suffix = abs(hash(query))
    await redis.setex(f"{_CACHE_PREFIX}{key_suffix}", config.cache_ttl, result)
    await redis.setex(f"{_EMB_PREFIX}{key_suffix}", config.cache_ttl, json.dumps(_embed(query)))
