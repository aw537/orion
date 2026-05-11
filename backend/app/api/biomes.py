import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Planet, Biome, Stardust, Entity, EntityStardust
from app.models.brain import StardustRelationship
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.auth.permissions import permission_checker
from app.schemas.biome import BiomeCreate, BiomeResponse, BiomeLifecycleUpdate, BiomeGraphResponse, GraphNode, GraphEdge

router = APIRouter(prefix="/api/v1", tags=["biomes"])


@router.get("/planets/{planet_id}/biomes", response_model=list[BiomeResponse])
async def list_biomes(planet_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await permission_checker.require_planet_access(user, planet_id, "read", db)
    biomes = (await db.execute(select(Biome).where(Biome.planet_id == planet_id))).scalars().all()
    return [BiomeResponse(id=b.id, planet_id=b.planet_id, galaxy_id=b.galaxy_id, name=b.name, description=b.description, lifecycle_state=b.lifecycle_state, created_at=b.created_at, last_active_at=b.last_active_at, stardust_count=b.stardust_count, cache_ttl_seconds=b.cache_ttl_seconds) for b in biomes]


@router.post("/planets/{planet_id}/biomes", response_model=BiomeResponse, status_code=201)
async def create_biome(planet_id: str, body: BiomeCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await permission_checker.require_planet_access(user, planet_id, "write", db)
    planet = (await db.execute(select(Planet).where(Planet.id == planet_id))).scalar_one_or_none()
    if not planet:
        raise HTTPException(404, "Planet not found")
    biome_id = str(uuid.uuid4())
    ttl_kw = {"cache_ttl_seconds": body.cache_ttl_seconds} if body.cache_ttl_seconds is not None else {}
    await db.execute(insert(Biome).values(id=biome_id, planet_id=planet_id, galaxy_id=planet.galaxy_id, name=body.name, description=body.description, **ttl_kw))
    await db.commit()
    from app.services import sun_service
    await sun_service.update_planet_registry(planet.galaxy_id)
    biome = (await db.execute(select(Biome).where(Biome.id == biome_id))).scalar_one()
    return BiomeResponse(id=biome.id, planet_id=biome.planet_id, galaxy_id=biome.galaxy_id, name=biome.name, description=biome.description, lifecycle_state=biome.lifecycle_state, created_at=biome.created_at, last_active_at=biome.last_active_at, stardust_count=biome.stardust_count, cache_ttl_seconds=biome.cache_ttl_seconds)


@router.get("/biomes/{biome_id}", response_model=BiomeResponse)
async def get_biome(biome_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    biome = (await db.execute(select(Biome).where(Biome.id == biome_id))).scalar_one_or_none()
    if not biome:
        raise HTTPException(404, "Biome not found")
    await permission_checker.require_planet_access(user, biome.planet_id, "read", db)
    return BiomeResponse(id=biome.id, planet_id=biome.planet_id, galaxy_id=biome.galaxy_id, name=biome.name, description=biome.description, lifecycle_state=biome.lifecycle_state, created_at=biome.created_at, last_active_at=biome.last_active_at, stardust_count=biome.stardust_count, cache_ttl_seconds=biome.cache_ttl_seconds)


@router.put("/biomes/{biome_id}/lifecycle", response_model=BiomeResponse)
async def update_lifecycle(biome_id: str, body: BiomeLifecycleUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    biome = (await db.execute(select(Biome).where(Biome.id == biome_id))).scalar_one_or_none()
    if not biome:
        raise HTTPException(404, "Biome not found")
    await permission_checker.require_planet_access(user, biome.planet_id, "write", db)
    await db.execute(update(Biome).where(Biome.id == biome_id).values(lifecycle_state=body.lifecycle_state))
    await db.commit()
    from app.services import sun_service
    await sun_service.update_planet_registry(biome.galaxy_id)
    await db.refresh(biome)
    return BiomeResponse(id=biome.id, planet_id=biome.planet_id, galaxy_id=biome.galaxy_id, name=biome.name, description=biome.description, lifecycle_state=biome.lifecycle_state, created_at=biome.created_at, last_active_at=biome.last_active_at, stardust_count=biome.stardust_count, cache_ttl_seconds=biome.cache_ttl_seconds)


@router.get("/biomes/{biome_id}/graph", response_model=BiomeGraphResponse)
async def get_biome_graph(biome_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    biome = (await db.execute(select(Biome).where(Biome.id == biome_id))).scalar_one_or_none()
    if not biome:
        raise HTTPException(404, "Biome not found")
    await permission_checker.require_planet_access(user, biome.planet_id, "read", db)
    stardust_rows = (await db.execute(select(Stardust).where(Stardust.biome_id == biome_id).limit(200))).scalars().all()
    nodes, edges = [], []
    stardust_ids = set()
    for s in stardust_rows:
        stardust_ids.add(s.id)
        nodes.append(GraphNode(id=s.id, label=s.content[:60], type="stardust", size=s.confidence, color=None, metadata={"region": s.region, "confidence": s.confidence}))

    # Get entities linked to these stardust records
    if stardust_ids:
        links = (await db.execute(select(EntityStardust).where(EntityStardust.stardust_id.in_(stardust_ids)))).scalars().all()
        entity_ids = {l.entity_id for l in links}
        if entity_ids:
            entities = (await db.execute(select(Entity).where(Entity.id.in_(entity_ids)))).scalars().all()
            for e in entities:
                nodes.append(GraphNode(id=e.id, label=e.name, type="entity", size=float(e.tier), metadata={"entity_type": e.entity_type}))
            for l in links:
                edges.append(GraphEdge(source=l.entity_id, target=l.stardust_id, type="entity_link"))

        # Get stardust relationships (co_chunk, wikilink) between visible nodes only
        sd_rels = (await db.execute(
            select(StardustRelationship).where(StardustRelationship.source_stardust_id.in_(stardust_ids))
        )).scalars().all()
        for r in sd_rels:
            if r.target_stardust_id in stardust_ids:
                edges.append(GraphEdge(source=r.source_stardust_id, target=r.target_stardust_id, type=r.relationship_type))

    return BiomeGraphResponse(nodes=nodes, edges=edges)


@router.get("/biomes/{biome_id}/entities", response_model=list[dict])
async def get_biome_entities(biome_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    biome = (await db.execute(select(Biome).where(Biome.id == biome_id))).scalar_one_or_none()
    if not biome:
        raise HTTPException(404, "Biome not found")
    await permission_checker.require_planet_access(user, biome.planet_id, "read", db)
    stardust_ids = (await db.execute(select(Stardust.id).where(Stardust.biome_id == biome_id))).scalars().all()
    if not stardust_ids:
        return []
    entity_ids = (await db.execute(select(EntityStardust.entity_id).where(EntityStardust.stardust_id.in_(stardust_ids)).distinct())).scalars().all()
    if not entity_ids:
        return []
    entities = (await db.execute(select(Entity).where(Entity.id.in_(entity_ids)))).scalars().all()
    return [{"id": e.id, "name": e.name, "entity_type": e.entity_type, "tier": e.tier, "mention_count": e.mention_count} for e in entities]
