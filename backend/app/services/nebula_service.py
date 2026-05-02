import logging
from datetime import datetime, timezone
from sqlalchemy import insert, select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.nebula import InteractionLog
from app.database import async_session

logger = logging.getLogger(__name__)


async def log_event(
    galaxy_id: str,
    action_type: str,
    initiated_by: str = "system",
    planet_id: str | None = None,
    biome_id: str | None = None,
    region: str | None = None,
    record_id: str | None = None,
    payload_before: str | None = None,
    payload_after: str | None = None,
    confidence_delta: float | None = None,
    latency_ms: int | None = None,
    cache_hit: bool | None = None,
    session_id: str | None = None,
    db: AsyncSession | None = None,
) -> int:
    values = {
        "galaxy_id": galaxy_id,
        "action_type": action_type,
        "initiated_by": initiated_by,
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
        "planet_id": planet_id,
        "biome_id": biome_id,
        "region": region,
        "record_id": record_id,
        "payload_before": payload_before,
        "payload_after": payload_after,
        "confidence_delta": confidence_delta,
        "latency_ms": latency_ms,
        "cache_hit": 1 if cache_hit else (0 if cache_hit is not None else None),
        "session_id": session_id,
    }

    if db:
        result = await db.execute(insert(InteractionLog).values(**values))
        return result.inserted_primary_key[0]

    async with async_session() as session:
        result = await session.execute(insert(InteractionLog).values(**values))
        await session.commit()
        return result.inserted_primary_key[0]


async def get_events(galaxy_id: str, limit: int = 50, offset: int = 0, action_type: str | None = None) -> tuple[list, int]:
    async with async_session() as session:
        q = select(InteractionLog).where(InteractionLog.galaxy_id == galaxy_id)
        count_q = select(func.count()).select_from(InteractionLog).where(InteractionLog.galaxy_id == galaxy_id)
        if action_type:
            q = q.where(InteractionLog.action_type == action_type)
            count_q = count_q.where(InteractionLog.action_type == action_type)
        total = (await session.execute(count_q)).scalar() or 0
        rows = (await session.execute(q.order_by(desc(InteractionLog.timestamp)).offset(offset).limit(limit))).scalars().all()
        return rows, total


async def get_dashboard_stats(galaxy_id: str) -> dict:
    async with async_session() as session:
        total = (await session.execute(
            select(func.count()).select_from(InteractionLog).where(InteractionLog.galaxy_id == galaxy_id)
        )).scalar() or 0

        type_counts = (await session.execute(
            select(InteractionLog.action_type, func.count()).where(InteractionLog.galaxy_id == galaxy_id).group_by(InteractionLog.action_type)
        )).all()

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=0, minute=0, second=0)
        recent = (await session.execute(
            select(func.count()).select_from(InteractionLog).where(InteractionLog.galaxy_id == galaxy_id, InteractionLog.timestamp >= cutoff)
        )).scalar() or 0

        return {
            "total_events": total,
            "events_by_type": {t: c for t, c in type_counts},
            "events_last_24h": recent,
        }
