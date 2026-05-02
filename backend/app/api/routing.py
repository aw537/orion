"""REST endpoints for the Inbox — holding area for unrouted knowledge."""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Galaxy
from app.models.biome import Biome
from app.models.planet import Planet
from app.models.routing_log import RoutingLog
from app.models.stardust import Stardust
from app.services import nebula_service
from app.services.planet_assignment_engine import planet_assignment_engine
from app.auth.dependencies import get_galaxy_for_user

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])


@router.get("/inbox")
async def get_inbox_records(
    limit: int = Query(20, le=100), offset: int = 0,
    galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db),
):
    inbox = (await db.execute(
        select(Biome).join(Planet, Biome.planet_id == Planet.id)
        .where(Planet.galaxy_id == galaxy.id, Biome.is_inbox == True)
    )).scalar_one_or_none()
    if not inbox:
        return []

    records = list((await db.execute(
        select(Stardust).where(Stardust.biome_id == inbox.id)
        .order_by(Stardust.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all())

    result = []
    for rec in records:
        log = (await db.execute(
            select(RoutingLog).where(RoutingLog.stardust_id == rec.id)
            .order_by(RoutingLog.routed_at.desc()).limit(1)
        )).scalar_one_or_none()

        # Fresh suggestion
        suggestion = await planet_assignment_engine.assign(
            content=rec.content, galaxy_id=galaxy.id,
            caller_planet=None, caller_biome=None, filename=None, db=db,
        )
        result.append({
            "stardust": {"id": rec.id, "content": rec.content, "region": rec.region,
                         "created_at": rec.created_at.isoformat() if rec.created_at else None},
            "original_reasoning": log.reasoning if log else None,
            "suggestion": suggestion.planet.name if suggestion.confidence > 0.5 else None,
            "suggestion_confidence": suggestion.confidence,
            "suggestion_reasoning": suggestion.reasoning,
        })
    return result


@router.post("/inbox/{stardust_id}/route")
async def route_inbox_record(
    stardust_id: str, planet_name: str, biome_name: str | None = None,
    galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db),
):
    rec = await db.get(Stardust, stardust_id)
    if not rec:
        raise HTTPException(404, "Record not found")

    planet = (await db.execute(
        select(Planet).where(Planet.galaxy_id == rec.galaxy_id, Planet.name == planet_name)
    )).scalar_one_or_none()
    if not planet:
        raise HTTPException(404, "Planet not found")

    biome = None
    if biome_name:
        biome = (await db.execute(
            select(Biome).where(Biome.planet_id == planet.id, Biome.name == biome_name)
        )).scalar_one_or_none()

    old_planet_id = rec.planet_id
    rec.planet_id = planet.id
    if biome:
        rec.biome_id = biome.id

    # Log correction
    log = (await db.execute(
        select(RoutingLog).where(RoutingLog.stardust_id == stardust_id)
        .order_by(RoutingLog.routed_at.desc()).limit(1)
    )).scalar_one_or_none()
    if log:
        log.corrected_planet_id = planet.id
        log.corrected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        log.corrected_by = "user"

    await db.commit()

    await nebula_service.log_event(
        galaxy_id=rec.galaxy_id, action_type="INBOX_RESOLVED",
        record_id=stardust_id, planet_id=planet.id,
        payload_before=json.dumps({"planet_id": old_planet_id}),
        payload_after=json.dumps({"planet_id": planet.id, "planet_name": planet_name, "routed_by": "user"}),
    )
    return {"stardust_id": stardust_id, "new_planet": planet_name, "new_biome": biome_name}


@router.get("/stats")
async def get_routing_stats(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            RoutingLog.routing_method,
            func.count(RoutingLog.id).label("count"),
            func.avg(RoutingLog.confidence).label("avg_confidence"),
            func.sum(case((RoutingLog.corrected_planet_id.isnot(None), 1), else_=0)).label("corrections"),
        ).where(RoutingLog.galaxy_id == galaxy.id).group_by(RoutingLog.routing_method)
    )).fetchall()

    return {
        "by_method": [
            {"method": r.routing_method, "count": r.count,
             "avg_confidence": round(r.avg_confidence, 3) if r.avg_confidence else 0.0,
             "correction_rate": round(r.corrections / r.count, 3) if r.count else 0.0}
            for r in rows
        ]
    }
