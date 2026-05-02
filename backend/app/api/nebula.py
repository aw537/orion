import asyncio
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, text, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
from app.models import Galaxy, InteractionLog, Stardust, Entity, EntityStardust, Biome, Planet, Contradiction
from app.auth.dependencies import get_galaxy_for_user
from app.services import nebula_service
from app.schemas.nebula import NebulaEvent, NebulaLogResponse

router = APIRouter(prefix="/api/v1/nebula", tags=["nebula"])


@router.get("", response_model=NebulaLogResponse)
async def get_nebula_log(limit: int = 50, offset: int = 0, action_type: str | None = None, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    rows, total = await nebula_service.get_events(galaxy.id, limit=limit, offset=offset, action_type=action_type)
    events = [NebulaEvent(event_id=r.id, action_type=r.action_type, planet_id=r.planet_id, biome_id=r.biome_id, record_id=r.record_id, initiated_by=r.initiated_by, timestamp=r.timestamp) for r in rows]
    return NebulaLogResponse(events=events, total=total, offset=offset, limit=limit)


@router.get("/dashboard")
async def get_dashboard(days: int = Query(default=30, le=365), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    gid = galaxy.id

    # Check Redis cache
    try:
        from app.storage.redis_client import get_redis
        redis = await get_redis()
        cache_key = f"orion:{gid}:dashboard:{days}"
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        redis = None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    days_ago_dt = now - timedelta(days=days)
    week_ago_dt = now - timedelta(days=7)
    day_ago_dt = now - timedelta(days=1)
    ninety_days_ago_dt = now - timedelta(days=90)

    # Query 1: Summary metrics (single query with subselects)
    summary_row = (await db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM stardust WHERE galaxy_id = :gid AND valid_until IS NULL) as total_stardust,
            (SELECT COUNT(*) FROM entities WHERE galaxy_id = :gid) as total_entities,
            (SELECT COUNT(*) FROM stardust WHERE galaxy_id = :gid AND created_at > :week_ago) as added_this_week,
            (SELECT COUNT(*) FROM stardust WHERE galaxy_id = :gid AND created_at > :day_ago) as added_today,
            (SELECT COUNT(*) FROM contradictions WHERE galaxy_id = :gid AND status = 'UNRESOLVED') as unresolved_contradictions,
            (SELECT COUNT(*) FROM biomes WHERE galaxy_id = :gid AND lifecycle_state = 'ACTIVE') as active_biomes,
            (SELECT ROUND(CAST(AVG(confidence) AS NUMERIC), 3) FROM stardust WHERE galaxy_id = :gid AND valid_until IS NULL) as avg_confidence
    """), {"gid": gid, "week_ago": week_ago_dt, "day_ago": day_ago_dt})).one()

    summary = {
        "total_stardust": summary_row[0] or 0, "total_entities": summary_row[1] or 0,
        "added_this_week": summary_row[2] or 0, "added_today": summary_row[3] or 0,
        "unresolved_contradictions": summary_row[4] or 0, "active_biomes": summary_row[5] or 0,
        "avg_confidence": float(summary_row[6] or 0),
    }

    # Query 2: Activity by biome (top 10)
    activity_rows = (await db.execute(
        select(
            Biome.id, Biome.name, Planet.name.label("planet_name"), Biome.lifecycle_state, Biome.stardust_count,
            func.count(case((InteractionLog.action_type == "WRITE", 1))).label("write_count"),
            func.count(case((InteractionLog.action_type == "READ", 1))).label("read_count"),
            func.max(InteractionLog.timestamp).label("last_activity"),
        )
        .join(InteractionLog, InteractionLog.biome_id == Biome.id)
        .join(Planet, Biome.planet_id == Planet.id)
        .where(InteractionLog.galaxy_id == gid, InteractionLog.timestamp > days_ago_dt)
        .group_by(Biome.id, Planet.name).order_by(text("write_count DESC")).limit(10)
    )).all()
    activity_by_biome = [
        {"biome_id": r[0], "biome_name": r[1], "planet_name": r[2], "lifecycle_state": r[3], "stardust_count": r[4], "write_count": r[5], "read_count": r[6], "last_activity": r[7].isoformat() if r[7] else None}
        for r in activity_rows
    ]

    # Query 3: Knowledge gaps (read/write ratio > 3)
    gap_rows = (await db.execute(
        select(
            Biome.id, Biome.name, Planet.name.label("planet_name"),
            func.count(case((InteractionLog.action_type == "READ", 1))).label("read_count"),
            func.count(case((InteractionLog.action_type == "WRITE", 1))).label("write_count"),
            Biome.stardust_count,
        )
        .join(InteractionLog, InteractionLog.biome_id == Biome.id)
        .join(Planet, Biome.planet_id == Planet.id)
        .where(InteractionLog.galaxy_id == gid, InteractionLog.timestamp > days_ago_dt)
        .group_by(Biome.id, Planet.name)
        .having(func.count(case((InteractionLog.action_type == "READ", 1))) > func.count(case((InteractionLog.action_type == "WRITE", 1))) * 3)
        .order_by(text("read_count DESC")).limit(10)
    )).all()
    knowledge_gaps = [
        {"biome_id": r[0], "biome_name": r[1], "planet_name": r[2], "read_count": r[3], "write_count": r[4], "read_write_ratio": round(r[3] / max(r[4], 1), 1), "stardust_count": r[5]}
        for r in gap_rows
    ]

    # Query 4: Contradiction trend (90 days)
    contradiction_rows = (await db.execute(
        select(
            func.date(Contradiction.detected_at).label("date"),
            func.count().label("detected"),
            func.count(case((Contradiction.status != "UNRESOLVED", 1))).label("resolved"),
        )
        .where(Contradiction.galaxy_id == gid, Contradiction.detected_at > ninety_days_ago_dt)
        .group_by(text("date")).order_by(text("date ASC"))
    )).all()
    contradiction_trend = [{"date": str(r[0]), "detected": r[1], "resolved": r[2]} for r in contradiction_rows]

    # Query 5: Top entities by influence
    entity_rows = (await db.execute(
        select(
            Entity.id, Entity.name, Entity.entity_type, Entity.tier, Entity.mention_count,
            func.count(func.distinct(EntityStardust.stardust_id)).label("linked_stardust"),
            func.count(func.distinct(Stardust.biome_id)).label("biomes_spanning"),
            Entity.last_seen,
        )
        .join(EntityStardust, Entity.id == EntityStardust.entity_id)
        .join(Stardust, EntityStardust.stardust_id == Stardust.id)
        .where(Entity.galaxy_id == gid)
        .group_by(Entity.id)
        .order_by((func.count(func.distinct(EntityStardust.stardust_id)) * func.count(func.distinct(Stardust.biome_id))).desc())
        .limit(15)
    )).all()
    top_entities = [
        {"id": r[0], "name": r[1], "entity_type": r[2], "tier": r[3], "mention_count": r[4], "linked_stardust": r[5], "biomes_spanning": r[6], "last_seen": r[7].isoformat() if r[7] else None}
        for r in entity_rows
    ]

    # Query 6: Growth over time
    growth_rows = (await db.execute(
        select(func.date(Stardust.created_at).label("date"), func.count().label("records_added"))
        .where(Stardust.galaxy_id == gid)
        .group_by(text("date")).order_by(text("date ASC"))
    )).all()
    cumulative = 0
    growth = []
    for r in growth_rows:
        cumulative += r[1]
        growth.append({"date": str(r[0]), "records_added": r[1], "cumulative": cumulative})

    result = {
        "summary": summary, "activity_by_biome": activity_by_biome,
        "knowledge_gaps": knowledge_gaps, "contradiction_trend": contradiction_trend,
        "top_entities": top_entities, "growth_over_time": growth,
        "computed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }

    # Cache in Redis (15 min)
    if redis:
        try:
            await redis.setex(cache_key, 900, json.dumps(result, default=str))
        except Exception:
            pass

    return result


@router.get("/stream")
async def nebula_stream(galaxy_id: str | None = Query(None)):
    async def event_generator():
        last_id = 0
        keepalive_interval = 15  # seconds
        while True:
            async with async_session() as db:
                gid = galaxy_id
                if not gid:
                    galaxy = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
                    gid = galaxy.id if galaxy else None
                if gid:
                    rows = (await db.execute(
                        select(InteractionLog).where(InteractionLog.galaxy_id == gid, InteractionLog.id > last_id).order_by(InteractionLog.id).limit(20)
                    )).scalars().all()
                    for r in rows:
                        last_id = r.id
                        event = {"event_id": r.id, "action_type": r.action_type, "planet_id": r.planet_id, "biome_id": r.biome_id, "record_id": r.record_id, "initiated_by": r.initiated_by, "timestamp": r.timestamp.isoformat() if r.timestamp else None, "metadata": {}}
                        # Enrich entity events with name/type/tier from payload_after
                        if r.payload_after and r.action_type in ("ENTITY_EXTRACTED", "ENTITY_ENRICHED", "SESSION_SUMMARY"):
                            try:
                                extra = json.loads(r.payload_after)
                                event.update({k: v for k, v in extra.items() if k.startswith("entity_") or k in ("previous_tier", "new_tier")})
                            except (json.JSONDecodeError, TypeError):
                                pass
                        yield f"data: {json.dumps(event, default=str)}\n\n"
                    if not rows:
                        yield ": keepalive\n\n"
                else:
                    yield ": keepalive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
