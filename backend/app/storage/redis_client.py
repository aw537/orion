import asyncio
import json
import logging
from datetime import datetime, timezone
from redis.asyncio import Redis
from app.config import get_settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None
_redis_lock = asyncio.Lock()


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        async with _redis_lock:
            if _redis is None:
                _redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


class RedisClient:
    def __init__(self, redis: Redis):
        self.r = redis

    # --- Key builders ---
    @staticmethod
    def cache_key(galaxy_id: str, biome_id: str, stardust_id: str) -> str:
        return f"orion:{galaxy_id}:biome:{biome_id}:cache:{stardust_id}"

    @staticmethod
    def index_key(galaxy_id: str, biome_id: str) -> str:
        return f"orion:{galaxy_id}:biome:{biome_id}:cache:index"

    @staticmethod
    def strength_key(galaxy_id: str) -> str:
        return f"orion:{galaxy_id}:strength"

    # --- Write ---
    async def cache_stardust(self, galaxy_id: str, biome_id: str, stardust_id: str, data: dict, ttl: int = 28800):
        try:
            key = self.cache_key(galaxy_id, biome_id, stardust_id)
            await self.r.setex(key, ttl, json.dumps(data, default=str))
            await self.r.zadd(self.index_key(galaxy_id, biome_id), {stardust_id: datetime.now(timezone.utc).replace(tzinfo=None).timestamp()})
        except Exception as e:
            logger.warning(f"Redis cache_stardust failed (degraded): {e}")

    # --- Read ---
    async def get_stardust(self, galaxy_id: str, biome_id: str, stardust_id: str) -> dict | None:
        try:
            raw = await self.r.get(self.cache_key(galaxy_id, biome_id, stardust_id))
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"Redis get_stardust failed (degraded): {e}")
            return None

    async def get_recent_stardust(self, galaxy_id: str, biome_id: str, limit: int = 20) -> list[str]:
        try:
            return await self.r.zrevrange(self.index_key(galaxy_id, biome_id), 0, limit - 1)
        except Exception as e:
            logger.warning(f"Redis get_recent_stardust failed (degraded): {e}")
            return []

    async def get_all_cached_stardust(self, galaxy_id: str, biome_id: str) -> list[dict]:
        ids = await self.get_recent_stardust(galaxy_id, biome_id, limit=100)
        if not ids:
            return []
        keys = [self.cache_key(galaxy_id, biome_id, sid) for sid in ids]
        try:
            raws = await self.r.mget(*keys)
            return [json.loads(raw) for raw in raws if raw]
        except Exception as e:
            logger.warning(f"Redis get_all_cached_stardust failed (degraded): {e}")
            return []

    # --- Strength ---
    async def set_strength(self, galaxy_id: str, score: float):
        await self.r.set(self.strength_key(galaxy_id), str(score))

    async def get_strength(self, galaxy_id: str) -> float:
        val = await self.r.get(self.strength_key(galaxy_id))
        return float(val) if val else 0.0
