import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Entity, EntityStardust, EntityTimeline, Stardust, Biome, Planet, Galaxy
from app.auth.dependencies import get_galaxy_for_user
from app.schemas.stardust import EntityResponse, EntityProfileResponse, SearchRecord, PaginatedResponse

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.get("", response_model=PaginatedResponse)
async def list_entities(limit: int = 50, offset: int = 0, entity_type: str | None = None, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    q = select(Entity).where(Entity.galaxy_id == galaxy.id)
    count_q = select(func.count()).select_from(Entity).where(Entity.galaxy_id == galaxy.id)
    if entity_type:
        q = q.where(Entity.entity_type == entity_type)
        count_q = count_q.where(Entity.entity_type == entity_type)
    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(q.order_by(Entity.mention_count.desc()).offset(offset).limit(limit))).scalars().all()
    items = [EntityResponse(id=e.id, name=e.name, entity_type=e.entity_type, tier=e.tier, profile=json.loads(e.profile) if isinstance(e.profile, str) else e.profile, mention_count=e.mention_count, first_seen=e.first_seen, last_seen=e.last_seen) for e in rows]
    return PaginatedResponse(items=[i.model_dump() for i in items], total=total, offset=offset, limit=limit)


@router.get("/{entity_id}", response_model=EntityProfileResponse)
async def get_entity(entity_id: str, db: AsyncSession = Depends(get_db)):
    entity = (await db.execute(select(Entity).where(Entity.id == entity_id))).scalar_one_or_none()
    if not entity:
        raise HTTPException(404, "Entity not found")

    # Related stardust
    links = (await db.execute(select(EntityStardust).where(EntityStardust.entity_id == entity_id))).scalars().all()
    stardust_ids = [l.stardust_id for l in links]
    related = []
    if stardust_ids:
        rows = (await db.execute(select(Stardust).where(Stardust.id.in_(stardust_ids)).limit(20))).scalars().all()
        for s in rows:
            biome = (await db.execute(select(Biome.name).where(Biome.id == s.biome_id))).scalar() or ""
            planet = (await db.execute(select(Planet.name).where(Planet.id == s.planet_id))).scalar() or ""
            tags = json.loads(s.context_tags) if isinstance(s.context_tags, str) else s.context_tags
            related.append(SearchRecord(id=s.id, content=s.content, region=s.region, biome_name=biome, planet_name=planet, confidence=s.confidence, valid_from=s.valid_from, valid_until=s.valid_until, context_tags=tags, source_agent=s.source_agent, access_count=s.access_count))

    # Timeline
    timeline_rows = (await db.execute(select(EntityTimeline).where(EntityTimeline.entity_id == entity_id).order_by(EntityTimeline.event_date.desc()).limit(50))).scalars().all()
    timeline = [{"event_date": t.event_date.isoformat(), "event_type": t.event_type, "event_content": t.event_content} for t in timeline_rows]

    rel_types = list({l.relationship_type for l in links if l.relationship_type})

    return EntityProfileResponse(
        entity=EntityResponse(id=entity.id, name=entity.name, entity_type=entity.entity_type, tier=entity.tier, profile=json.loads(entity.profile) if isinstance(entity.profile, str) else entity.profile, mention_count=entity.mention_count, first_seen=entity.first_seen, last_seen=entity.last_seen),
        related_stardust=related, timeline=timeline, relationship_types=rel_types,
    )
