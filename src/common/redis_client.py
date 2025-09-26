import redis.asyncio as redis
from settings import config

_redis: redis.Redis | None = None


async def init_redis() -> None:
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )


async def get_redis() -> redis.Redis:
    await init_redis()
    assert _redis is not None
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None