import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy, Stardust, Biome, Planet
from app.auth.dependencies import get_galaxy_for_user
from app.schemas.stardust import StardustCreate, StardustResponse, StardustUpdate, WriteReceipt, PaginatedResponse
from app.services import stardust_service, nebula_service
from pydantic import BaseModel as _BaseModel


class QuickCaptureBody(_BaseModel):
    content: str
    planet: str
    region: str = "contextual"
    gravity: str = "BIOME"

router = APIRouter(prefix="/api/v1", tags=["stardust"])


def _stardust_to_response(s: Stardust) -> StardustResponse:
    tags = json.loads(s.context_tags) if isinstance(s.context_tags, str) else s.context_tags
    return StardustResponse(
        id=s.id, biome_id=s.biome_id, planet_id=s.planet_id, galaxy_id=s.galaxy_id,
        content=s.content, region=s.region, gravity=s.gravity, confidence=s.confidence,
        valid_from=s.valid_from, valid_until=s.valid_until, context_tags=tags,
        contradiction_id=s.contradiction_id, reinforcement_sources=s.reinforcement_sources,
        source_agent=s.source_agent, chroma_id=s.chroma_id, created_at=s.created_at,
        last_accessed=s.last_accessed, access_count=s.access_count,
    )


@router.get("/biomes/{biome_id}/stardust")
async def list_stardust(biome_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count()).select_from(Stardust).where(Stardust.biome_id == biome_id))).scalar() or 0
    rows = (await db.execute(select(Stardust).where(Stardust.biome_id == biome_id).order_by(Stardust.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return PaginatedResponse(items=[_stardust_to_response(s) for s in rows], total=total, offset=offset, limit=limit)


@router.post("/biomes/{biome_id}/stardust", response_model=WriteReceipt, status_code=201)
async def create_stardust(biome_id: str, body: StardustCreate, background_tasks: BackgroundTasks, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    biome = (await db.execute(select(Biome).where(Biome.id == biome_id))).scalar_one_or_none()
    if not biome:
        raise HTTPException(404, "Biome not found")
    planet = (await db.execute(select(Planet).where(Planet.id == biome.planet_id))).scalar_one()

    receipt = await stardust_service.write_stardust(
        content=body.content, galaxy_id=galaxy.id, planet_name=planet.name,
        biome_name=biome.name, region=body.region, context_tags=body.context_tags,
        gravity=body.gravity, source_agent=body.source_agent,
    )
    background_tasks.add_task(stardust_service.run_async_tasks, receipt.stardust_id, body.content, galaxy.id, planet.id, biome.id, body.region)
    return receipt


@router.post("/stardust/quick-capture", response_model=WriteReceipt, status_code=201)
async def quick_capture(body: QuickCaptureBody, background_tasks: BackgroundTasks, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    """Quick-capture: resolves the most recently active Biome for the given Planet."""
    planet = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id, Planet.name == body.planet))).scalar_one_or_none()
    if not planet:
        raise HTTPException(404, f"Planet '{body.planet}' not found")
    # Find most recently active biome
    biome = (await db.execute(
        select(Biome).where(Biome.planet_id == planet.id).order_by(Biome.last_active_at.desc().nullslast()).limit(1)
    )).scalar_one_or_none()
    if not biome:
        # Create Inbox biome
        import uuid
        biome_id = str(uuid.uuid4())
        from sqlalchemy import insert
        await db.execute(insert(Biome).values(id=biome_id, planet_id=planet.id, galaxy_id=galaxy.id, name="Inbox", lifecycle_state="ACTIVE"))
        await db.commit()
        biome = (await db.execute(select(Biome).where(Biome.id == biome_id))).scalar_one()
    receipt = await stardust_service.write_stardust(
        content=body.content, galaxy_id=galaxy.id, planet_name=planet.name,
        biome_name=biome.name, region=body.region, gravity=body.gravity, source_agent="user",
    )
    background_tasks.add_task(stardust_service.run_async_tasks, receipt.stardust_id, body.content, galaxy.id, planet.id, biome.id, body.region)
    return receipt


@router.get("/stardust/{stardust_id}", response_model=StardustResponse)
async def get_stardust(stardust_id: str, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Stardust).where(Stardust.id == stardust_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Stardust not found")
    await db.execute(update(Stardust).where(Stardust.id == stardust_id).values(last_accessed=datetime.now(timezone.utc).replace(tzinfo=None), access_count=Stardust.access_count + 1))
    await db.commit()
    await db.refresh(s)
    return _stardust_to_response(s)


@router.put("/stardust/{stardust_id}", response_model=StardustResponse)
async def update_stardust(stardust_id: str, body: StardustUpdate, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Stardust).where(Stardust.id == stardust_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Stardust not found")
    updates = {}
    if body.content is not None:
        updates["content"] = body.content
    if body.context_tags is not None:
        updates["context_tags"] = body.context_tags
    if body.gravity is not None:
        updates["gravity"] = body.gravity
    if body.valid_until is not None:
        updates["valid_until"] = body.valid_until
    if updates:
        await db.execute(update(Stardust).where(Stardust.id == stardust_id).values(**updates))
        await nebula_service.log_event(galaxy_id=s.galaxy_id, action_type="HUMAN_EDIT", record_id=stardust_id, initiated_by="user")
        await db.commit()
        await db.refresh(s)
    return _stardust_to_response(s)
