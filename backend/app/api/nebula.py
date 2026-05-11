import asyncio
import json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
from app.models import Galaxy, InteractionLog
from app.auth.dependencies import get_galaxy_for_user
from app.services import nebula_service
from app.schemas.nebula import NebulaEvent, NebulaLogResponse

router = APIRouter(prefix="/api/v1/nebula", tags=["nebula"])


@router.get("", response_model=NebulaLogResponse)
async def get_nebula_log(limit: int = 50, offset: int = 0, action_type: str | None = None, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    rows, total = await nebula_service.get_events(galaxy.id, limit=limit, offset=offset, action_type=action_type)
    events = [NebulaEvent(event_id=r.id, action_type=r.action_type, planet_id=r.planet_id, biome_id=r.biome_id, record_id=r.record_id, initiated_by=r.initiated_by, timestamp=r.timestamp) for r in rows]
    return NebulaLogResponse(events=events, total=total, offset=offset, limit=limit)


@router.get("/stream")
async def nebula_stream(galaxy_id: str | None = Query(None), galaxy: Galaxy = Depends(get_galaxy_for_user)):
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
