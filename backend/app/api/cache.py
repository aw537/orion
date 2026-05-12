from fastapi import APIRouter, Depends
from app.config import get_settings
from app.models import Galaxy
from app.auth.dependencies import get_galaxy_for_user

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])

_ttl_overrides: dict[str, int] = {}


@router.get("/ttl-config")
async def get_ttl_config(galaxy: Galaxy = Depends(get_galaxy_for_user)):
    ttls = get_settings().region_cache_ttls
    return {"defaults": ttls.model_dump(), "overrides": _ttl_overrides}


@router.put("/ttl-config")
async def update_ttl_config(overrides: dict[str, int], galaxy: Galaxy = Depends(get_galaxy_for_user)):
    _ttl_overrides.update(overrides)
    defaults = get_settings().region_cache_ttls.model_dump()
    effective = {**defaults, **_ttl_overrides}
    return {"defaults": defaults, "overrides": dict(_ttl_overrides), "effective": effective}


@router.get("/stats")
async def get_cache_stats(galaxy: Galaxy = Depends(get_galaxy_for_user)):
    """Return per-region cache key counts from Redis. Hit rate requires instrumentation not yet in place."""
    from app.storage.redis_client import get_redis
    regions = ["analytical", "procedural", "contextual", "creative", "empathetic", "critical", "strategic"]
    stats = {}
    try:
        redis = await get_redis()
        for r in regions:
            count = 0
            cursor = 0
            while True:
                cursor, batch = await redis.scan(cursor, match=f"orion:{galaxy.id}:{r}:*", count=100)
                count += len(batch)
                if cursor == 0:
                    break
            stats[r] = {"keys": count}
    except Exception:
        stats = {r: {"keys": 0} for r in regions}
    return stats
