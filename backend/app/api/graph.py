"""Knowledge graph REST API endpoints."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy, Planet, Entity
from app.models.brain import EntityRelationship
from app.services.graph_service import graph_service
from app.auth.dependencies import get_galaxy_for_user

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.get("/full")
async def full_graph(
    galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db),
):
    """Return the complete entity graph with planet colors for visualization."""
    # Load planets for color mapping
    planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id))).scalars().all()
    planet_map = {p.id: {"name": p.name, "color": p.color} for p in planets}

    # All entities with degree counts
    rows = await db.execute(text("""
        SELECT e.id, e.name, e.entity_type, e.tier, e.planet_id, e.mention_count,
            (SELECT COUNT(*) FROM entity_relationships er
             WHERE er.source_entity_id = e.id OR er.target_entity_id = e.id) as degree
        FROM entities e WHERE e.galaxy_id = :gid
    """), {"gid": galaxy.id})
    entities = []
    for r in rows:
        m = r._mapping
        pid = m["planet_id"]
        planet_info = planet_map.get(pid, {})
        entities.append({
            "id": m["id"], "name": m["name"], "type": m["entity_type"],
            "tier": m["tier"], "mentions": m["mention_count"], "degree": m["degree"],
            "planet_id": pid, "planet_name": planet_info.get("name"),
            "planet_color": planet_info.get("color", "#6B7280"),
        })

    # All edges
    rels = (await db.execute(
        select(EntityRelationship).where(EntityRelationship.galaxy_id == galaxy.id)
    )).scalars().all()
    edges = [
        {"source": r.source_entity_id, "target": r.target_entity_id,
         "type": r.relationship_type, "confidence": r.confidence, "strength": r.strength}
        for r in rels
    ]

    return {"entities": entities, "edges": edges, "planets": [
        {"id": p.id, "name": p.name, "color": p.color} for p in planets
    ]}


@router.get("/entity/{entity_id}/neighborhood")
async def entity_neighborhood(
    entity_id: str, depth: int = Query(2, le=5),
    relationship_types: str | None = Query(None),
    galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db),
):
    result = await graph_service.get_entity_neighborhood(entity_id, depth, galaxy.id, db)
    if relationship_types:
        types = [t.strip() for t in relationship_types.split(",")]
        result["edges"] = [e for e in result.get("edges", []) if e.get("type") in types]

    # Enrich entities with planet color
    planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id))).scalars().all()
    planet_map = {p.id: {"name": p.name, "color": p.color} for p in planets}
    for ent in result.get("entities", []):
        pid = ent.get("planet_id")
        planet_info = planet_map.get(pid, {})
        ent["planet_name"] = planet_info.get("name")
        ent["planet_color"] = planet_info.get("color", "#6B7280")

    return result


@router.get("/path")
async def find_path(source: str = Query(...), target: str = Query(...), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    result = await graph_service.find_path(source, target, galaxy.id, db)
    if not result:
        return {"path": None, "message": "No path found within 6 hops"}
    return result


@router.get("/hubs")
async def hub_entities(limit: int = Query(10, le=50), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    return await graph_service.get_hub_entities(galaxy.id, limit, db)


@router.get("/unlinked-mentions")
async def unlinked_mentions(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    return await graph_service.find_unlinked_mentions(galaxy.id, db)


class LinkRequest(BaseModel):
    entity_id: str
    stardust_id: str


@router.post("/link")
async def create_link(req: LinkRequest, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    backlink = await graph_service.link_entity_stardust(req.entity_id, req.stardust_id, db)
    await db.commit()
    return {"id": backlink.id, "entity_id": backlink.entity_id, "stardust_id": backlink.stardust_id}


@router.post("/link-all/{entity_id}")
async def link_all(entity_id: str, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    count = await graph_service.link_all_unlinked(entity_id, galaxy.id, db)
    await db.commit()
    return {"entity_id": entity_id, "links_created": count}
