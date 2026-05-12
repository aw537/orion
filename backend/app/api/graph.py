"""Knowledge graph REST API endpoints."""
from itertools import combinations
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
from app.models import Galaxy, Planet, Entity
from app.models.brain import EntityRelationship
from app.services.graph_service import graph_service
from app.auth.dependencies import get_galaxy_for_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

_rebuild_in_progress: set[str] = set()


async def _do_rebuild_edges(galaxy_id: str) -> None:
    try:
        async with async_session() as db:
            stardust_entities = await db.execute(text("""
                SELECT es.stardust_id, array_agg(es.entity_id) as entity_ids
                FROM entity_stardust es
                JOIN entities e ON e.id = es.entity_id
                WHERE e.galaxy_id = :gid
                GROUP BY es.stardust_id
                HAVING COUNT(*) >= 2
            """), {"gid": galaxy_id})
            for row in stardust_entities:
                m = row._mapping
                entity_ids = m["entity_ids"]
                stardust_id = m["stardust_id"]
                for src, tgt in combinations(entity_ids, 2):
                    existing = await db.execute(text("""
                        SELECT 1 FROM entity_relationships
                        WHERE (source_entity_id = :s AND target_entity_id = :t)
                           OR (source_entity_id = :t AND target_entity_id = :s)
                        LIMIT 1
                    """), {"s": src, "t": tgt})
                    if existing.scalar() is None:
                        await graph_service.upsert_relationship(
                            source_id=src, target_id=tgt,
                            rel_type="WORKS_WITH", confidence=0.5,
                            stardust_id=stardust_id, galaxy_id=galaxy_id, db=db,
                        )
            planet_entities = await db.execute(text("""
                SELECT planet_id, array_agg(id) as entity_ids
                FROM entities
                WHERE galaxy_id = :gid AND planet_id IS NOT NULL
                GROUP BY planet_id
                HAVING COUNT(*) >= 2
            """), {"gid": galaxy_id})
            for row in planet_entities:
                m = row._mapping
                entity_ids = m["entity_ids"]
                for src, tgt in combinations(entity_ids, 2):
                    existing = await db.execute(text("""
                        SELECT 1 FROM entity_relationships
                        WHERE (source_entity_id = :s AND target_entity_id = :t)
                           OR (source_entity_id = :t AND target_entity_id = :s)
                        LIMIT 1
                    """), {"s": src, "t": tgt})
                    if existing.scalar() is None:
                        await graph_service.upsert_relationship(
                            source_id=src, target_id=tgt,
                            rel_type="WORKS_WITH", confidence=0.3,
                            stardust_id="planet-cooccurrence", galaxy_id=galaxy_id, db=db,
                        )
            await db.commit()
    except Exception as e:
        logger.error(f"rebuild_edges background task failed: {e}")
    finally:
        _rebuild_in_progress.discard(galaxy_id)


@router.get("/full")
async def full_graph(
    planet: str | None = Query(default=None),
    max_nodes: int = Query(default=200, le=1000),
    galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db),
):
    """Return the entity graph with planet colors. Use planet to scope to one domain."""
    # Load planets for color mapping
    planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id))).scalars().all()
    planet_map = {p.id: {"name": p.name, "color": p.color} for p in planets}

    # Resolve planet filter to planet_id
    planet_id_filter = None
    if planet:
        matched = next((p for p in planets if p.name == planet), None)
        if matched is None:
            return {"entities": [], "edges": [], "planets": [
                {"id": p.id, "name": p.name, "color": p.color} for p in planets
            ]}
        planet_id_filter = matched.id

    # Entities with degree counts, optionally scoped to one planet
    planet_clause = "AND e.planet_id = :planet_id" if planet_id_filter else ""
    sql_params: dict = {"gid": galaxy.id, "limit": max_nodes}
    if planet_id_filter:
        sql_params["planet_id"] = planet_id_filter

    rows = await db.execute(text(f"""
        SELECT e.id, e.name, e.entity_type, e.tier, e.planet_id, e.mention_count,
            (SELECT COUNT(*) FROM entity_relationships er
             WHERE er.source_entity_id = e.id OR er.target_entity_id = e.id) as degree
        FROM entities e WHERE e.galaxy_id = :gid {planet_clause}
        LIMIT :limit
    """), sql_params)
    entities = []
    entity_ids: set[str] = set()
    for r in rows:
        m = r._mapping
        pid = m["planet_id"]
        planet_info = planet_map.get(pid, {})
        eid = m["id"]
        entity_ids.add(eid)
        entities.append({
            "id": eid, "name": m["name"], "type": m["entity_type"],
            "tier": m["tier"], "mentions": m["mention_count"], "degree": m["degree"],
            "planet_id": pid, "planet_name": planet_info.get("name"),
            "planet_color": planet_info.get("color", "#6B7280"),
        })

    # Edges scoped to retained entities
    rels = (await db.execute(
        select(EntityRelationship).where(EntityRelationship.galaxy_id == galaxy.id)
    )).scalars().all()
    edges = [
        {"source": r.source_entity_id, "target": r.target_entity_id,
         "type": r.relationship_type, "confidence": r.confidence, "strength": r.strength}
        for r in rels
        if r.source_entity_id in entity_ids and r.target_entity_id in entity_ids
    ]

    result = {"entities": entities, "edges": edges, "planets": [
        {"id": p.id, "name": p.name, "color": p.color} for p in planets
    ]}
    if len(entities) == max_nodes:
        result["truncated"] = True
    return result


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


@router.post("/rebuild-edges")
async def rebuild_edges(background_tasks: BackgroundTasks, galaxy: Galaxy = Depends(get_galaxy_for_user)):
    """Enqueue a background rebuild of co-occurrence edges for all entities sharing stardust records."""
    if galaxy.id in _rebuild_in_progress:
        raise HTTPException(429, "A rebuild is already in progress for this galaxy")
    _rebuild_in_progress.add(galaxy.id)
    background_tasks.add_task(_do_rebuild_edges, galaxy.id)
    return {"status": "rebuild_started"}
