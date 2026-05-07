"""Memory namespace — knowledge storage and retrieval tools."""
import json
import logging
from datetime import timezone
from sqlalchemy import select, func, delete
from app.database import async_session
from app.models import Galaxy, Planet, Biome, Entity, EntityStardust, EntityTimeline, Stardust, Contradiction
from app.services import search_service, stardust_service, context_service, sun_service
from app.mcp.utils import get_galaxy_id as _get_galaxy_id

logger = logging.getLogger(__name__)


async def memory_write(
    content: str, planet: str | None = None, biome: str | None = None,
    region: str = "contextual", context_tags: list[str] | None = None,
    gravity: str = "BIOME",
    galaxy_id: str | None = None,
) -> dict:
    """Store a piece of knowledge in your Galaxy. Planet is auto-routed if not specified."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"status": "error", "message": "No galaxy found"}
    receipt = await stardust_service.write_stardust(
        content=content, galaxy_id=galaxy_id, planet_name=planet, biome_name=biome,
        region=region, context_tags=context_tags or [], gravity=gravity, source_agent="mcp_client",
    )
    async with async_session() as db:
        from app.models import Planet as PlanetModel
        p = (await db.execute(select(PlanetModel).where(PlanetModel.id == receipt.planet_id))).scalar_one_or_none()
        if p:
            async def _safe_async_tasks():
                try:
                    await stardust_service.run_async_tasks(receipt.stardust_id, content, galaxy_id, p.id, receipt.biome_id, region)
                except Exception as e:
                    logger.error(f"MCP async tasks failed for {receipt.stardust_id}: {e}")
            from app.mcp.background import spawn
            spawn(_safe_async_tasks(), name=f"memory.write:{receipt.stardust_id}")
    result = receipt.model_dump(mode="json")

    # H1.3: Confirmation line on write
    from app.services.session_summary_service import build_confirmation_line
    _today_count = 0
    try:
        from sqlalchemy import text as _text
        from datetime import datetime
        _today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        async with async_session() as _db:
            _row = await _db.execute(_text(
                "SELECT COUNT(*) FROM interaction_log "
                "WHERE galaxy_id = :gid AND action_type = 'WRITE' "
                "AND timestamp >= :today_start"
            ), {"gid": galaxy_id, "today_start": _today_start})
            _today_count = _row.scalar() or 0
    except Exception:
        pass
    result["orion_confirmation"] = build_confirmation_line(biome or planet or "auto-routed", region, _today_count)

    return result


async def memory_search(
    query: str, planet: str | None = None, biome: str | None = None,
    region: str | None = None, limit: int = 5,
    galaxy_id: str | None = None,
) -> dict:
    """Search for relevant knowledge in your Galaxy."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"records": [], "retrieval_metadata": {"error": "No galaxy found"}}
    result = await search_service.search(query, galaxy_id, planet_name=planet, biome_name=biome, region=region, limit=limit)
    return result.model_dump(mode="json")


async def memory_context(
    planet: str | None = None, biome: str | None = None,
    max_tokens: int = 4000, model: str | None = None,
    galaxy_id: str | None = None,
) -> dict:
    """Get a structured context bundle for the current session."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    bundle = await context_service.build_context(galaxy_id, planet_name=planet, biome_name=biome, max_tokens=max_tokens)
    return bundle.model_dump(mode="json")


async def memory_status(galaxy_id: str | None = None) -> dict:
    """Get current Galaxy health and system state."""
    async with async_session() as db:
        if galaxy_id:
            galaxy = (await db.execute(select(Galaxy).where(Galaxy.id == galaxy_id))).scalar_one_or_none()
        else:
            galaxy = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
        if not galaxy:
            return {"error": "No galaxy found"}
        planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id))).scalars().all()
        total_stardust = (await db.execute(select(func.count()).select_from(Stardust).where(Stardust.galaxy_id == galaxy.id))).scalar() or 0
        total_entities = (await db.execute(select(func.count()).select_from(Entity).where(Entity.galaxy_id == galaxy.id))).scalar() or 0
        unresolved = (await db.execute(select(func.count()).select_from(Contradiction).where(Contradiction.galaxy_id == galaxy.id, Contradiction.status == "UNRESOLVED"))).scalar() or 0

        planet_list = []
        for p in planets:
            biomes = (await db.execute(select(Biome.name).where(Biome.planet_id == p.id, Biome.lifecycle_state.in_(["SEED", "ACTIVE", "MATURE"])))).scalars().all()
            planet_list.append({"id": p.id, "name": p.name, "stardust_count": p.stardust_count, "health_status": p.health_status, "active_biomes": list(biomes)})

        sun_summary = None
        sun = await sun_service.get_full_sun(galaxy.id, db)
        if sun:
            identity = sun.get("identity", {})
            wc = sun.get("working_context", {})
            sun_summary = {
                "identity_name": identity.get("name", ""),
                "current_focus": wc.get("current_focus", ""),
                "hot_biomes": wc.get("hot_biomes", []),
                "unresolved_blockers": len(wc.get("blockers", [])),
                "last_updated": wc.get("updated_at", ""),
            }

        return {
            "galaxy_id": galaxy.id, "galaxy_name": galaxy.name, "strength_score": galaxy.strength_score,
            "total_stardust": total_stardust, "total_entities": total_entities,
            "planets": planet_list, "active_session_agents": 0,
            "last_audit_at": None, "contradiction_count_unresolved": unresolved,
            "sun_summary": sun_summary,
        }


async def planet_list(galaxy_id: str | None = None) -> dict:
    """Enumerate all planets and their biomes in the Galaxy, including those not in the Sun registry."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy_id).order_by(Planet.name))).scalars().all()
        result = []
        for p in planets:
            biomes = (await db.execute(
                select(Biome).where(Biome.planet_id == p.id, Biome.lifecycle_state.in_(["SEED", "ACTIVE", "MATURE"]))
                .order_by(Biome.name)
            )).scalars().all()
            result.append({
                "id": p.id, "name": p.name, "description": p.description,
                "stardust_count": p.stardust_count, "health_status": p.health_status,
                "biomes": [{"id": b.id, "name": b.name, "lifecycle_state": b.lifecycle_state, "stardust_count": b.stardust_count} for b in biomes],
            })
        return {"planets": result, "total": len(result)}


async def biome_list(planet: str | None = None, galaxy_id: str | None = None) -> dict:
    """List all biomes across a planet (or all planets). Use when you need to know valid biome names before writing stardust."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        q = select(Biome, Planet.name.label("planet_name")).join(Planet, Biome.planet_id == Planet.id).where(Planet.galaxy_id == galaxy_id)
        if planet:
            q = q.where(Planet.name == planet)
        rows = (await db.execute(q.order_by(Planet.name, Biome.name))).all()
        biomes = [{"id": b.id, "name": b.name, "planet": pn, "lifecycle_state": b.lifecycle_state, "stardust_count": b.stardust_count} for b, pn in rows]
        return {"biomes": biomes, "total": len(biomes)}


async def stardust_get(stardust_id: str, galaxy_id: str | None = None) -> dict:
    """Fetch a specific stardust record by ID. Use to verify what was written or to retrieve the record before superseding it."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        s = (await db.execute(select(Stardust).where(Stardust.id == stardust_id, Stardust.galaxy_id == galaxy_id))).scalar_one_or_none()
        if not s:
            return {"error": f"Stardust record '{stardust_id}' not found"}
        planet_name = (await db.execute(select(Planet.name).where(Planet.id == s.planet_id))).scalar()
        biome_name = (await db.execute(select(Biome.name).where(Biome.id == s.biome_id))).scalar()
        tags = json.loads(s.context_tags) if isinstance(s.context_tags, str) else s.context_tags
        return {
            "id": s.id, "content": s.content, "region": s.region, "gravity": s.gravity,
            "planet": planet_name, "biome": biome_name, "confidence": s.confidence,
            "source_agent": s.source_agent, "access_count": s.access_count,
            "valid_from": s.valid_from.isoformat() if s.valid_from else None,
            "context_tags": tags, "reasoning": s.reasoning,
        }


async def stardust_delete(stardust_id: str, galaxy_id: str | None = None) -> dict:
    """Permanently delete a stardust record by ID. Use to remove incorrect or test writes. This action is irreversible."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        s = (await db.execute(select(Stardust).where(Stardust.id == stardust_id, Stardust.galaxy_id == galaxy_id))).scalar_one_or_none()
        if not s:
            return {"error": f"Stardust record '{stardust_id}' not found"}
        from app.services import nebula_service
        from app.models import (
            EntityStardust as _ES, EntityTimeline as _ET,
            StardustRelationship as _SR, EntityBacklink as _EB, RoutingLog as _RL,
            KnowledgeIntegrationLog as _KIL,
        )
        await nebula_service.log_event(galaxy_id=galaxy_id, action_type="DELETE", initiated_by="mcp_client", record_id=stardust_id, db=db)
        await db.execute(delete(_ES).where(_ES.stardust_id == stardust_id))
        await db.execute(delete(_ET).where(_ET.source_stardust_id == stardust_id))
        await db.execute(delete(_SR).where((_SR.source_stardust_id == stardust_id) | (_SR.target_stardust_id == stardust_id)))
        await db.execute(delete(_EB).where(_EB.stardust_id == stardust_id))
        await db.execute(delete(_RL).where(_RL.stardust_id == stardust_id))
        await db.execute(delete(_KIL).where(_KIL.stardust_id == stardust_id))
        await db.delete(s)
        await db.commit()
        return {"status": "deleted", "deleted_id": stardust_id}


async def memory_entity_get(entity_name: str, planet: str | None = None, galaxy_id: str | None = None) -> dict:
    """Retrieve an entity profile with relationship context and timeline."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    async with async_session() as db:
        q = select(Entity).where(Entity.galaxy_id == galaxy_id, func.lower(Entity.name) == entity_name.lower())
        if planet:
            p = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy_id, Planet.name == planet))).scalar_one_or_none()
            if p:
                q = q.where(Entity.planet_id == p.id)
        entity = (await db.execute(q)).scalar_one_or_none()
        if not entity:
            return {"error": f"Entity '{entity_name}' not found"}

        links = (await db.execute(select(EntityStardust).where(EntityStardust.entity_id == entity.id))).scalars().all()
        stardust_ids = [l.stardust_id for l in links]
        primary_planet = None
        if entity.planet_id:
            primary_planet = (await db.execute(select(Planet.name).where(Planet.id == entity.planet_id))).scalar()
        related = []
        if stardust_ids:
            rows = (await db.execute(select(Stardust).where(Stardust.id.in_(stardust_ids)).limit(10))).scalars().all()
            for s in rows:
                biome_name = (await db.execute(select(Biome.name).where(Biome.id == s.biome_id))).scalar() or ""
                planet_name = (await db.execute(select(Planet.name).where(Planet.id == s.planet_id))).scalar() or ""
                tags = json.loads(s.context_tags) if isinstance(s.context_tags, str) else s.context_tags
                related.append({"id": s.id, "content": s.content, "region": s.region, "biome_name": biome_name, "planet_name": planet_name, "confidence": s.confidence, "valid_from": s.valid_from.isoformat() if s.valid_from else None, "valid_until": None, "context_tags": tags, "source_agent": s.source_agent, "access_count": s.access_count})

        timeline_rows = (await db.execute(select(EntityTimeline).where(EntityTimeline.entity_id == entity.id).order_by(EntityTimeline.event_date.desc()).limit(20))).scalars().all()
        timeline = [{"event_date": t.event_date.isoformat(), "event_type": t.event_type, "event_content": t.event_content} for t in timeline_rows]
        rel_types = list({l.relationship_type for l in links if l.relationship_type})

        profile = {
            "primary_planet": primary_planet,
            "stardust_count": len(stardust_ids),
            "relationship_type_count": len(rel_types),
            "relationship_types": rel_types,
        }
        return {
            "entity": {"id": entity.id, "name": entity.name, "entity_type": entity.entity_type, "tier": entity.tier, "profile": profile, "mention_count": entity.mention_count, "first_seen": entity.first_seen.isoformat(), "last_seen": entity.last_seen.isoformat()},
            "related_stardust": related, "timeline": timeline, "relationship_types": rel_types,
        }
