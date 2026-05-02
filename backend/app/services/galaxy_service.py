"""Galaxy Strength — 5-dimension score from 0 to 100."""
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Galaxy
from app.models.profiles import StrengthHistory
from app.storage.redis_client import get_redis

logger = logging.getLogger(__name__)


def _naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure_naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


STRENGTH_CACHE_TTL = 3600  # 1 hour


def score_to_grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


async def compute_galaxy_strength(galaxy_id: str, db: AsyncSession) -> dict:
    galaxy = (await db.execute(select(Galaxy).where(Galaxy.id == galaxy_id))).scalar_one_or_none()
    if not galaxy:
        return {"score": 0, "grade": "F", "dimensions": {}, "days_active": 0}

    days_active = max((_naive_utcnow() - _ensure_naive(galaxy.created_at)).days, 1)

    # Single query for all counts
    from sqlalchemy import text
    row = (await db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM stardust WHERE galaxy_id = :gid) as stardust_count,
            (SELECT COUNT(*) FROM entity_stardust es JOIN stardust s ON es.stardust_id = s.id WHERE s.galaxy_id = :gid) as entity_links,
            (SELECT COUNT(*) FROM contradictions WHERE galaxy_id = :gid) as total_contradictions,
            (SELECT COUNT(*) FROM contradictions WHERE galaxy_id = :gid AND status != 'UNRESOLVED') as resolved_contradictions,
            (SELECT COUNT(*) FROM stardust WHERE galaxy_id = :gid AND reinforcement_sources > 1) as diverse_records,
            (SELECT COUNT(*) FROM biomes WHERE galaxy_id = :gid AND last_active_at >= :week_ago) as active_biomes,
            (SELECT COUNT(*) FROM biomes WHERE galaxy_id = :gid) as total_biomes
    """), {"gid": galaxy_id, "week_ago": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)})).one()

    stardust_count = row[0] or 0
    total_entity_links = row[1] or 0
    total_contradictions = row[2] or 0
    resolved_contradictions = row[3] or 0
    diverse_records = row[4] or 0
    active_biomes = row[5] or 0
    total_biomes = row[6] or 0

    # Dimension scores
    records_per_day = stardust_count / days_active
    volume_score = min(100.0, (records_per_day / 20.0) * 100)
    density_ratio = total_entity_links / max(stardust_count, 1)
    density_score = min(100.0, density_ratio * 200)
    health_score = 50.0 if total_contradictions == 0 else (resolved_contradictions / total_contradictions) * 100
    diversity_score = min(100.0, (diverse_records / max(stardust_count, 1)) * 150)
    coverage_score = (active_biomes / max(total_biomes, 1)) * 100

    combined = (
        volume_score * 0.25 +
        density_score * 0.20 +
        health_score * 0.20 +
        diversity_score * 0.20 +
        coverage_score * 0.15
    )
    combined = round(min(100.0, max(0.0, combined)), 1)

    # Store in history
    await db.execute(insert(StrengthHistory).values(
        galaxy_id=galaxy_id, score=combined,
        volume_score=round(volume_score, 1), density_score=round(density_score, 1),
        health_score=round(health_score, 1), diversity_score=round(diversity_score, 1),
        coverage_score=round(coverage_score, 1),
    ))
    galaxy.strength_score = combined
    await db.commit()

    # Trend: compare to 7 days ago
    week_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    prev = (await db.execute(
        select(StrengthHistory.score)
        .where(StrengthHistory.galaxy_id == galaxy_id, StrengthHistory.computed_at <= week_ago)
        .order_by(StrengthHistory.computed_at.desc()).limit(1)
    )).scalar()
    trend = f"{combined - prev:+.1f} vs last week" if prev is not None else "first measurement"

    result = {
        "score": combined,
        "grade": score_to_grade(combined),
        "dimensions": {
            "volume":    {"score": round(volume_score, 1),    "weight": 0.25, "label": "Knowledge Volume"},
            "density":   {"score": round(density_score, 1),   "weight": 0.20, "label": "Entity Graph Density"},
            "health":    {"score": round(health_score, 1),    "weight": 0.20, "label": "Contradiction Health"},
            "diversity": {"score": round(diversity_score, 1), "weight": 0.20, "label": "Reinforcement Diversity"},
            "coverage":  {"score": round(coverage_score, 1),  "weight": 0.15, "label": "Active Coverage"},
        },
        "trend": trend,
        "computed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "days_active": days_active,
    }

    # Cache in Redis
    try:
        redis = await get_redis()
        await redis.setex(f"orion:{galaxy_id}:strength", STRENGTH_CACHE_TTL, json.dumps(result))
    except Exception:
        pass

    return result


async def get_galaxy_strength(galaxy_id: str, db: AsyncSession) -> dict:
    """Get strength, using Redis cache if available."""
    try:
        redis = await get_redis()
        cached = await redis.get(f"orion:{galaxy_id}:strength")
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    return await compute_galaxy_strength(galaxy_id, db)
