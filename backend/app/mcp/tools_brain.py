"""Brain namespace — cognitive tools for AI agents operating from Orion."""
import json
import logging
from datetime import timezone
from sqlalchemy import select, func
from app.database import async_session
from app.mcp.utils import get_galaxy_id as _get_galaxy_id

logger = logging.getLogger(__name__)


async def brain_orient(
    agent_name: str, model: str, agent_type: str = "GENERAL",
    active_planet: str | None = None, active_biome: str | None = None,
    max_tokens: int | None = None,
    include_biome_stardust: bool = False,
    galaxy_id: str | None = None,
) -> dict:
    """Orient yourself in your Galaxy at the start of every session."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    from app.services.agent_identity_service import agent_identity_service
    from app.services.orientation_service import orientation_service
    from app.services.model_switch_service import model_switch_service

    async with async_session() as db:
        # Get or create persistent identity
        identity = await agent_identity_service.get_or_create_identity(
            galaxy_id, agent_name, model, agent_type, db,
        )

        # Detect model switch before building orientation
        if identity.total_sessions > 0:
            # Check if model changed (identity was just updated with new model)
            from app.models.brain import AgentSession
            last_session = (await db.execute(
                select(AgentSession)
                .where(AgentSession.agent_identity_id == identity.id)
                .order_by(AgentSession.started_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if last_session and last_session.model_used != model:
                await model_switch_service.handle_switch(
                    identity, last_session.model_used, model, galaxy_id, db,
                )

        # Build full orientation
        orientation = await orientation_service.build_orientation(
            identity, galaxy_id, active_planet, active_biome, max_tokens, db,
        )

    if include_biome_stardust:
        from app.mcp import tools_memory
        orientation["biome_context"] = await tools_memory.memory_context(
            planet=active_planet, biome=active_biome,
            max_tokens=max_tokens or 4000, galaxy_id=galaxy_id,
        )

    return orientation


async def brain_think(
    content: str, planet: str | None = None, biome: str | None = None,
    cognitive_mode: str = "contextual", confidence: float = 0.7,
    reasoning: str | None = None, supersedes: list[str] | None = None,
    scope: str = "BIOME", context_tags: list[str] | None = None,
    session_id: str | None = None, agent_name: str | None = None,
    galaxy_id: str | None = None,
) -> dict:
    """Integrate new understanding into your brain. Planet is auto-routed if not specified."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    from app.services import stardust_service

    source = agent_name or "brain"

    # Write via stardust service with reasoning and supersedes
    receipt = await stardust_service.write_stardust(
        content=content, galaxy_id=galaxy_id, planet_name=planet, biome_name=biome,
        region=cognitive_mode, context_tags=context_tags or [], gravity=scope,
        source_agent=source, confidence=confidence,
        reasoning=reasoning, supersedes=supersedes or None,
    )

    # Fire async tasks (entity extraction + chroma indexing)
    async with async_session() as db:
        from app.models import Planet as PlanetModel
        p = (await db.execute(select(PlanetModel).where(PlanetModel.id == receipt.planet_id))).scalar_one_or_none()
        if p:
            async def _async_tasks():
                try:
                    await stardust_service.run_async_tasks(receipt.stardust_id, content, galaxy_id, p.id, receipt.biome_id, cognitive_mode)
                except Exception as e:
                    logger.error(f"brain.think async tasks failed: {e}")
                # Run knowledge integration engine
                try:
                    from app.services.knowledge_integration_engine import integration_engine
                    async with async_session() as db2:
                        from app.models.stardust import Stardust
                        stardust = (await db2.execute(select(Stardust).where(Stardust.id == receipt.stardust_id))).scalar_one_or_none()
                        if stardust:
                            await integration_engine.integrate(stardust, galaxy_id, db2)
                except Exception as e:
                    logger.error(f"Knowledge integration failed: {e}")
            from app.mcp.background import spawn
            spawn(_async_tasks(), name=f"brain.think:{receipt.stardust_id}")

    result = receipt.model_dump(mode="json")
    result["cognitive_mode"] = cognitive_mode
    if reasoning:
        result["reasoning_stored"] = True
    if supersedes:
        result["supersedes_count"] = len(supersedes)

    # H1.3: Confirmation line on think
    from app.services.session_summary_service import build_confirmation_line
    biome_name = result.get("biome_name", biome or "Galaxy")
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
    result["orion_confirmation"] = build_confirmation_line(biome_name, cognitive_mode, _today_count)

    return result


async def brain_recall(
    query: str, cognitive_mode: str | None = None,
    planet: str | None = None, biome: str | None = None,
    context_window: str | None = None, include_reasoning: bool = False,
    include_graph_paths: bool = False, recency_weight: float = 0.3,
    limit: int = 5, session_id: str | None = None,
    galaxy_id: str | None = None,
) -> dict:
    """Access knowledge from your brain with graph-enhanced retrieval."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"records": [], "retrieval_metadata": {"error": "No galaxy found"}}

    from app.services import search_service

    # Enhanced query: prepend context_window for better semantic matching
    enhanced_query = f"{context_window} {query}" if context_window else query

    result = await search_service.search(
        enhanced_query, galaxy_id, planet_name=planet, biome_name=biome,
        region=cognitive_mode, limit=limit,
    )
    response = result.model_dump(mode="json")

    # Enrich with reasoning if requested
    if include_reasoning:
        async with async_session() as db:
            from app.models.stardust import Stardust
            for record in response.get("records", []):
                s = (await db.execute(select(Stardust).where(Stardust.id == record["id"]))).scalar_one_or_none()
                if s and s.reasoning:
                    record["reasoning"] = s.reasoning

    # Graph path expansion if requested
    if include_graph_paths:
        try:
            from app.services.graph_service import graph_service
            async with async_session() as db:
                for record in response.get("records", []):
                    from app.models import EntityStardust
                    entity_links = (await db.execute(
                        select(EntityStardust).where(EntityStardust.stardust_id == record["id"])
                    )).scalars().all()
                    if entity_links:
                        neighborhood = await graph_service.get_entity_neighborhood(
                            entity_links[0].entity_id, 1, galaxy_id, db,
                        )
                        record["graph_context"] = {
                            "connected_entities": len(neighborhood.get("entities", [])),
                            "edges": len(neighborhood.get("edges", [])),
                        }
        except Exception as e:
            logger.warning(f"Graph expansion failed: {e}")

    response["cognitive_mode"] = cognitive_mode
    response["context_window_used"] = context_window is not None

    # H1.3: Activity indicator on recall
    records_count = len(response.get("records", []))
    from app.services.session_summary_service import build_status_line
    # Get actual galaxy strength and biome name
    _biome_label = biome or planet or "Galaxy"
    _strength = 0.0
    try:
        from app.services.galaxy_service import get_galaxy_strength
        async with async_session() as _db:
            _gs = await get_galaxy_strength(galaxy_id, _db)
            _strength = _gs.get("score", 0.0)
    except Exception:
        pass
    response["orion_status_line"] = build_status_line(records_count, _biome_label, _strength)

    return response


async def brain_calibrate(
    session_id: str, records_used: list[str],
    records_retrieved_unused: list[str] | None = None,
    knowledge_gaps: list[str] | None = None,
    session_outcome: str | None = None,
    knowledge_quality_score: float | None = None,
    galaxy_id: str | None = None,
) -> dict:
    """Teach your brain what was useful this session."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    from app.services.calibration_service import calibration_service
    async with async_session() as db:
        # Find agent identity from session
        from app.models.brain import AgentSession
        session = (await db.execute(select(AgentSession).where(AgentSession.id == session_id))).scalar_one_or_none()
        if not session:
            return {"error": f"Session '{session_id}' not found"}

        result = await calibration_service.process_calibration(
            session_id=session_id, agent_identity_id=session.agent_identity_id,
            galaxy_id=galaxy_id, records_used=records_used,
            records_retrieved_unused=records_retrieved_unused or [],
            knowledge_gaps=knowledge_gaps or [],
            session_outcome=session_outcome,
            knowledge_quality_score=knowledge_quality_score, db=db,
        )
        return result


async def brain_health(agent_name: str, galaxy_id: str | None = None) -> dict:
    """Assess the current cognitive health of your brain."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    from app.services.brain_health_service import brain_health_service
    async with async_session() as db:
        from app.models.brain import AgentIdentity
        identity = (await db.execute(
            select(AgentIdentity).where(AgentIdentity.galaxy_id == galaxy_id, AgentIdentity.agent_name == agent_name)
        )).scalar_one_or_none()
        if not identity:
            return {"error": f"Agent '{agent_name}' not found. Call brain.orient first.", "hint": "Use brain.orient to register your agent identity before calling brain.health."}
        result = await brain_health_service.get_brain_health(identity, galaxy_id, db)
        return result


async def brain_know(concept: str, depth: str = "summary", galaxy_id: str | None = None) -> dict:
    """Access your synthesized understanding of a concept."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    from app.services import search_service
    async with async_session() as db:
        # Search for the concept
        from app.models import Entity
        entity = (await db.execute(
            select(Entity).where(Entity.galaxy_id == galaxy_id, func.lower(Entity.name) == concept.lower())
        )).scalar_one_or_none()

        # Get related stardust via search
        results = await search_service.search(concept, galaxy_id, limit=10 if depth == "full_history" else 5)
        records = results.model_dump(mode="json").get("records", [])

        response = {
            "concept": concept,
            "depth": depth,
            "entity": None,
            "understanding": records,
            "total_records": len(records),
        }

        if entity:
            response["entity"] = {
                "id": entity.id, "name": entity.name, "type": entity.entity_type,
                "tier": entity.tier, "mentions": entity.mention_count,
                "first_seen": entity.first_seen.isoformat() if entity.first_seen else None,
                "last_seen": entity.last_seen.isoformat() if entity.last_seen else None,
            }

            # Get graph neighborhood if detailed or full
            if depth in ("detailed", "full_history"):
                try:
                    from app.services.graph_service import graph_service
                    neighborhood = await graph_service.get_entity_neighborhood(entity.id, 2, galaxy_id, db)
                    response["graph_neighborhood"] = neighborhood
                except Exception:
                    pass

        return response


async def brain_graph_query(
    entity_name: str, relationship_types: list[str] | None = None, depth: int = 2,
    galaxy_id: str | None = None,
) -> dict:
    """Traverse the knowledge graph from an entity."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    from app.services.graph_service import graph_service
    async with async_session() as db:
        from app.models import Entity
        entity = (await db.execute(
            select(Entity).where(Entity.galaxy_id == galaxy_id, func.lower(Entity.name) == entity_name.lower())
        )).scalar_one_or_none()
        if not entity:
            return {"error": f"Entity '{entity_name}' not found"}

        neighborhood = await graph_service.get_entity_neighborhood(entity.id, depth, galaxy_id, db)
        if relationship_types:
            neighborhood["edges"] = [e for e in neighborhood.get("edges", []) if e.get("type") in relationship_types]
        return neighborhood


async def brain_find_path(source_concept: str, target_concept: str, galaxy_id: str | None = None) -> dict | None:
    """Find the connection between two concepts in your knowledge graph."""
    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    from app.services.graph_service import graph_service
    async with async_session() as db:
        from app.models import Entity
        source = (await db.execute(
            select(Entity).where(Entity.galaxy_id == galaxy_id, func.lower(Entity.name) == source_concept.lower())
        )).scalar_one_or_none()
        target = (await db.execute(
            select(Entity).where(Entity.galaxy_id == galaxy_id, func.lower(Entity.name) == target_concept.lower())
        )).scalar_one_or_none()
        if not source:
            return {"error": f"Entity '{source_concept}' not found"}
        if not target:
            return {"error": f"Entity '{target_concept}' not found"}

        path = await graph_service.find_path(source.id, target.id, galaxy_id, db)
        if not path:
            from app.models import EntityStardust
            edge_count = (await db.execute(
                select(EntityStardust).limit(1)
            )).first()
            reason = "no_edges" if not edge_count else "no_path"
            return {"path": None, "reason": reason}
        return path


async def brain_diff(
    topic: str, since: str, planet: str | None = None,
    galaxy_id: str | None = None,
) -> dict:
    """Show what changed about a topic since a given date.

    Parameters:
    - topic: keyword or phrase to match against stardust content
    - since: ISO 8601 datetime string (e.g. '2026-05-01' or '2026-05-01T00:00:00Z')
    - planet: optional planet name to scope the search
    """
    from datetime import datetime
    from sqlalchemy import and_
    from app.models import Stardust, Planet as PlanetModel, Biome

    galaxy_id = galaxy_id or await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}

    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return {"error": f"Invalid 'since' datetime: '{since}'. Use ISO 8601 format e.g. '2026-05-01'."}

    topic_lower = topic.lower()

    async with async_session() as db:
        q = select(Stardust).where(
            Stardust.galaxy_id == galaxy_id,
            Stardust.valid_from >= since_dt,
        )
        if planet:
            planet_row = (await db.execute(
                select(PlanetModel).where(PlanetModel.galaxy_id == galaxy_id, PlanetModel.name == planet)
            )).scalar_one_or_none()
            if not planet_row:
                return {"error": f"Planet '{planet}' not found"}
            q = q.where(Stardust.planet_id == planet_row.id)

        rows = (await db.execute(q.order_by(Stardust.valid_from.asc()))).scalars().all()

        added = []
        superseded_ids: set[str] = set()

        for s in rows:
            if topic_lower not in s.content.lower():
                continue
            planet_name = (await db.execute(select(PlanetModel.name).where(PlanetModel.id == s.planet_id))).scalar() or ""
            biome_name = (await db.execute(select(Biome.name).where(Biome.id == s.biome_id))).scalar() or ""
            record = {
                "id": s.id,
                "content": s.content,
                "planet": planet_name,
                "biome": biome_name,
                "region": s.region,
                "confidence": s.confidence,
                "valid_from": s.valid_from.isoformat(),
                "source_agent": s.source_agent,
            }
            if s.supersedes:
                record["supersedes"] = s.supersedes
                superseded_ids.update(s.supersedes)
            added.append(record)

        superseded = []
        if superseded_ids:
            s_rows = (await db.execute(select(Stardust).where(Stardust.id.in_(list(superseded_ids))))).scalars().all()
            for sr in s_rows:
                sp_name = (await db.execute(select(PlanetModel.name).where(PlanetModel.id == sr.planet_id))).scalar() or ""
                sb_name = (await db.execute(select(Biome.name).where(Biome.id == sr.biome_id))).scalar() or ""
                superseded.append({
                    "id": sr.id, "content": sr.content, "planet": sp_name,
                    "biome": sb_name, "region": sr.region, "confidence": sr.confidence,
                    "valid_from": sr.valid_from.isoformat() if sr.valid_from else None,
                    "source_agent": sr.source_agent,
                })

        return {
            "topic": topic,
            "since": since,
            "planet": planet,
            "changes_added": added,
            "changes_superseded": superseded,
            "changes_superseded_ids": list(superseded_ids),
            "summary": f"{len(added)} record(s) added, {len(superseded_ids)} superseded since {since}",
        }
