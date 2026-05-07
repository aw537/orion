"""Orion MCP Server — exposes tools to AI agents on port 8787.

Three namespaces:
  memory.* — 5 tools for knowledge management (any caller)
  brain.*  — 8 tools for cognitive operations (AI agents)
  sun.*    — 3 tools for Galaxy steering

Session lifecycle:
  1. First tool call from an agent auto-starts a session and injects Sun + context
  2. Every call updates last_active timestamp
  3. Idle sessions (5min) auto-close with SESSION_END logged to Nebula
  4. Agents can explicitly close with orion_session_end
"""
import logging
from mcp.server.fastmcp import FastMCP
from app.config import get_settings
from app.mcp import tools_memory, tools_brain, tools_sun
from app.mcp.session import tracker
from app.database import async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orion.mcp")

mcp = FastMCP("Orion", host="0.0.0.0", port=get_settings().MCP_PORT)

_DEFAULT_AGENT = "mcp_client"


from app.mcp.utils import get_galaxy_id as _get_galaxy_id


async def _resolve_agent(agent_name: str | None) -> str:
    """Resolve agent name: use provided name, or look up from active session, or default."""
    if agent_name:
        return agent_name
    # Check if there's exactly one active session — use that agent
    sessions = tracker._local_cache
    if len(sessions) == 1:
        return next(iter(sessions.values())).agent
    return _DEFAULT_AGENT


async def _session_wrap(agent: str, tool_name: str, result: dict) -> dict:
    """Wrap a tool result with session tracking. On brain.orient, prepend full context bundle."""
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return result

    session = await tracker.touch(agent, tool_name, galaxy_id)

    if tracker.needs_context(agent):
        tracker.mark_context_injected(agent)
        if tool_name == "brain.orient":
            context = await tools_memory.memory_context()
            sun = await tools_sun.sun_read()
            result = {
                "_session": {
                    "session_id": session.id,
                    "message": "Session started. Sun and context auto-loaded below. Follow the agent_protocol.",
                },
                "_sun": sun,
                "_context": context,
                "tool_result": result,
            }
            logger.info(f"Auto-injected context for session {session.id}")

    return result


# ── memory.* namespace (5 tools) ───────────────────────────────────────────

@mcp.tool(name="memory.write")
async def memory_write(
    content: str, planet: str | None = None, biome: str | None = None,
    region: str = "contextual", context_tags: list[str] | None = None,
    gravity: str = "BIOME",
) -> dict:
    """Store a piece of knowledge in your Galaxy. Planet is auto-routed if not specified.

    Use this when: storing facts without active integration (logs, references, raw notes).
    Use brain.think instead when: the content should update your understanding, supersede a decision, or trigger contradiction detection.

    Parameters:
    - region: cognitive mode — one of: 'contextual' (default), 'strategic', 'analytical', 'creative'
    - gravity: indexing scope — one of: 'BIOME' (default), 'PLANET', 'GALAXY'
    """
    result = await tools_memory.memory_write(content, planet, biome, region, context_tags, gravity)
    return await _session_wrap(_DEFAULT_AGENT, "memory.write", result)


@mcp.tool(name="memory.search")
async def memory_search(
    query: str, planet: str | None = None, biome: str | None = None,
    region: str | None = None, limit: int = 5,
) -> dict:
    """Search for relevant knowledge in your Galaxy using semantic search.

    Use this when: doing simple keyword/semantic lookup with no graph expansion needed.
    Use brain.recall instead when: you want records weighted by cognitive mode and graph-expanded context.
    Use brain.ask instead when: you have a natural language question and want a synthesized answer.
    """
    result = await tools_memory.memory_search(query, planet, biome, region, limit)
    return await _session_wrap(_DEFAULT_AGENT, "memory.search", result)


@mcp.tool(name="memory.context")
async def memory_context(
    planet: str | None = None, biome: str | None = None,
    max_tokens: int = 4000, model: str | None = None,
) -> dict:
    """Get a structured context bundle for the current session. For agents with persistent identity, brain.orient provides richer orientation including expertise profiles and history."""
    result = await tools_memory.memory_context(planet, biome, max_tokens, model)
    return await _session_wrap(_DEFAULT_AGENT, "memory.context", result)


@mcp.tool(name="memory.status")
async def memory_status() -> dict:
    """Get current Galaxy health and system state."""
    result = await tools_memory.memory_status()
    return await _session_wrap(_DEFAULT_AGENT, "memory.status", result)


@mcp.tool(name="memory.entity_get")
async def memory_entity_get(entity_name: str, planet: str | None = None) -> dict:
    """Retrieve an entity profile with relationship context and timeline."""
    result = await tools_memory.memory_entity_get(entity_name, planet)
    return await _session_wrap(_DEFAULT_AGENT, "memory.entity_get", result)


# ── brain.* namespace (8 tools) ────────────────────────────────────────────

@mcp.tool(name="brain.orient")
async def brain_orient(
    agent_name: str, model: str, agent_type: str = "GENERAL",
    active_planet: str | None = None, active_biome: str | None = None,
    max_tokens: int | None = None, include_biome_stardust: bool = False,
) -> dict:
    """Orient yourself in your Galaxy at the start of every session. REQUIRED: Call this once at session start. Returns your persistent identity, accumulated expertise, current context, synthesized knowledge state, and operating protocol. Set include_biome_stardust=true to also embed biome-scoped stardust in one call (eliminates a follow-up memory.context call)."""
    result = await tools_brain.brain_orient(agent_name, model, agent_type, active_planet, active_biome, max_tokens, include_biome_stardust)
    return await _session_wrap(agent_name, "brain.orient", result)


@mcp.tool(name="brain.think")
async def brain_think(
    content: str, planet: str | None = None, biome: str | None = None,
    cognitive_mode: str = "contextual", confidence: float = 0.7,
    reasoning: str | None = None, supersedes: list[str] | None = None,
    scope: str = "BIOME", context_tags: list[str] | None = None,
    session_id: str | None = None, agent_name: str | None = None,
) -> dict:
    """Integrate new understanding into your brain — the primary write tool for AI agents.

    Use this when: integrating decisions, learnings, or conclusions that should update your knowledge.
    Use memory.write instead when: storing raw facts or notes without active integration.

    Parameters:
    - cognitive_mode: one of 'contextual' (default), 'strategic', 'analytical', 'creative'
    - scope: indexing breadth — one of 'BIOME' (default, narrow), 'PLANET', 'GALAXY' (broadest)
    - supersedes: list of stardust_ids this record replaces (marks them as outdated)
    - reasoning: why you believe this — stored alongside the content for future calibration
    """
    result = await tools_brain.brain_think(content, planet, biome, cognitive_mode, confidence, reasoning, supersedes, scope, context_tags, session_id, agent_name)
    return await _session_wrap(await _resolve_agent(agent_name), "brain.think", result)


@mcp.tool(name="brain.recall")
async def brain_recall(
    query: str, cognitive_mode: str | None = None,
    planet: str | None = None, biome: str | None = None,
    context_window: str | None = None, include_reasoning: bool = False,
    include_graph_paths: bool = False, recency_weight: float = 0.3,
    limit: int = 5, session_id: str | None = None, agent_name: str | None = None,
) -> dict:
    """Access knowledge from your brain with graph-enhanced retrieval.

    Use this when: you need raw records with graph context, or want to filter by cognitive mode.
    Use memory.search instead when: you just need a fast semantic search with no graph expansion.
    Use brain.ask instead when: you have a natural language question and want a synthesized answer.
    Use brain.know instead when: you want synthesized understanding of a specific named concept.

    Parameters:
    - cognitive_mode: filter by — one of 'contextual', 'strategic', 'analytical', 'creative'
    - context_window: prepend to query for better semantic matching (e.g. current task description)
    """
    result = await tools_brain.brain_recall(query, cognitive_mode, planet, biome, context_window, include_reasoning, include_graph_paths, recency_weight, limit, session_id)
    return await _session_wrap(await _resolve_agent(agent_name), "brain.recall", result)


@mcp.tool(name="brain.calibrate")
async def brain_calibrate(
    session_id: str, records_used: list[str],
    records_retrieved_unused: list[str] | None = None,
    knowledge_gaps: list[str] | None = None,
    session_outcome: str | None = None,
    knowledge_quality_score: float | None = None,
    agent_name: str | None = None,
) -> dict:
    """Teach your brain what was useful this session. Call at the end of every session."""
    result = await tools_brain.brain_calibrate(session_id, records_used, records_retrieved_unused, knowledge_gaps, session_outcome, knowledge_quality_score)
    return await _session_wrap(await _resolve_agent(agent_name), "brain.calibrate", result)


@mcp.tool(name="brain.health")
async def brain_health(agent_name: str) -> dict:
    """Assess the current cognitive health of your brain. Returns overall health, knowledge freshness, coverage gaps, stale beliefs, expertise summary, and enrichment recommendations."""
    result = await tools_brain.brain_health(agent_name)
    return await _session_wrap(agent_name, "brain.health", result)


@mcp.tool(name="brain.know")
async def brain_know(concept: str, depth: str = "summary", agent_name: str | None = None) -> dict:
    """Access your synthesized understanding of a named concept or entity.

    Use this when: you want to understand what a specific named thing is and how it relates to your knowledge.
    Use brain.ask instead when: you have a natural language question rather than a named concept.
    Use brain.recall instead when: you want raw records, not a synthesized understanding.

    Parameters:
    - depth: one of 'summary' (default, fast), 'detailed' (includes graph neighborhood), 'full_history' (all records)
    """
    result = await tools_brain.brain_know(concept, depth)
    return await _session_wrap(await _resolve_agent(agent_name), "brain.know", result)


@mcp.tool(name="brain.graph_query")
async def brain_graph_query(
    entity_name: str, relationship_types: list[str] | None = None, depth: int = 2,
    agent_name: str | None = None,
) -> dict:
    """Traverse the knowledge graph from an entity. Returns the entity and everything connected within the specified depth."""
    result = await tools_brain.brain_graph_query(entity_name, relationship_types, depth)
    return await _session_wrap(await _resolve_agent(agent_name), "brain.graph_query", result)


@mcp.tool(name="brain.find_path")
async def brain_find_path(source_concept: str, target_concept: str, agent_name: str | None = None) -> dict:
    """Find the connection between two concepts in your knowledge graph. Returns the shortest path with all relationship types. When no path exists, returns reason: 'no_path' (concepts unrelated) or 'no_edges' (graph is empty)."""
    result = await tools_brain.brain_find_path(source_concept, target_concept)
    if not result:
        result = {"path": None, "reason": "no_path", "message": f"No path found between '{source_concept}' and '{target_concept}'"}
    return await _session_wrap(await _resolve_agent(agent_name), "brain.find_path", result)


@mcp.tool(name="brain.diff")
async def brain_diff(topic: str, since: str, planet: str | None = None,
                     agent_name: str | None = None) -> dict:
    """Show what changed about a topic since a given date.

    Parameters:
    - topic: keyword or phrase to match against stardust content
    - since: ISO 8601 datetime (e.g. '2026-05-01' or '2026-05-01T00:00:00')
    - planet: optional planet name to scope the diff
    """
    result = await tools_brain.brain_diff(topic, since, planet)
    return await _session_wrap(await _resolve_agent(agent_name), "brain.diff", result)


@mcp.tool(name="brain.ask")
async def brain_ask(
    question: str, planet: str | None = None, depth: int = 2,
    agent_name: str | None = None,
) -> dict:
    """Ask a natural language question and get a synthesized answer from your Galaxy's knowledge.

    Use this when: you have a question and want an interpreted, synthesized answer.
    Use brain.recall instead when: you want raw records and full control over retrieval.
    Use brain.know instead when: you have a specific named concept, not a question.

    Routes automatically to graph traversal or semantic search based on question intent.
    Examples: 'Who knows about Stripe?', 'What decisions were made about auth?', 'How does FastAPI connect to deployment?'
    """
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    from app.services import brain_ask_service
    async with async_session() as db:
        result = await brain_ask_service.answer(
            question=question, galaxy_id=galaxy_id,
            planet_name=planet, depth=depth, db=db,
        )
    return await _session_wrap(await _resolve_agent(agent_name), "brain.ask", result.model_dump())


@mcp.tool(name="brain.synthesize")
async def brain_synthesize(
    topic: str, planet: str | None = None, biome: str | None = None,
    include_open_questions: bool = True, include_contradictions: bool = True,
    max_tokens: int = 1000, agent_name: str | None = None,
) -> dict:
    """Get a synthesized understanding of a topic from your brain. Unlike brain.recall which returns individual records, brain.synthesize runs a single LLM pass over all relevant records and returns a coherent narrative."""
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    from app.services.synthesis_service import synthesis_service
    from app.storage.redis_client import get_redis as _get_redis
    redis = await _get_redis()
    async with async_session() as db:
        result = await synthesis_service.synthesize(
            topic=topic, galaxy_id=galaxy_id,
            planet_id=None, biome_id=None,
            include_open_questions=include_open_questions,
            include_contradictions=include_contradictions,
            max_tokens=max_tokens, db=db, redis=redis,
        )
    return await _session_wrap(await _resolve_agent(agent_name), "brain.synthesize", result.model_dump())


@mcp.tool(name="brain.graph_full")
async def brain_graph_full(
    planet: str | None = None, max_nodes: int = 100, agent_name: str | None = None,
) -> dict:
    """Get the entity knowledge graph with all edges. Use planet to scope to one domain. max_nodes caps the result to avoid token explosion on large graphs."""
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    from app.services.graph_service import graph_service
    async with async_session() as db:
        from app.models import Planet as PlanetModel, Entity
        from sqlalchemy import select as _select
        q = _select(Entity).where(Entity.galaxy_id == galaxy_id)
        if planet:
            p = (await db.execute(_select(PlanetModel).where(PlanetModel.galaxy_id == galaxy_id, PlanetModel.name == planet))).scalar_one_or_none()
            if p:
                q = q.where(Entity.planet_id == p.id)
        entities = (await db.execute(q.limit(max_nodes))).scalars().all()
        planets = (await db.execute(_select(PlanetModel).where(PlanetModel.galaxy_id == galaxy_id))).scalars().all()
        planet_map = {p.id: {"name": p.name, "color": p.color} for p in planets}
        entity_list = []
        for e in entities:
            pi = planet_map.get(e.planet_id, {})
            entity_list.append({"id": e.id, "name": e.name, "entity_type": e.entity_type, "tier": e.tier, "planet_name": pi.get("name"), "planet_color": pi.get("color", "#6B7280"), "mention_count": e.mention_count})
        from app.models import EntityRelationship
        edge_q = _select(EntityRelationship).where(EntityRelationship.galaxy_id == galaxy_id)
        edges = (await db.execute(edge_q)).scalars().all()
        entity_ids = {e["id"] for e in entity_list}
        edge_list = [{"source": e.source_entity_id, "target": e.target_entity_id, "type": e.relationship_type, "confidence": e.confidence} for e in edges if e.source_entity_id in entity_ids and e.target_entity_id in entity_ids]
        return {"entities": entity_list, "edges": edge_list, "planets": [{"id": p.id, "name": p.name, "color": p.color} for p in planets], "truncated": len(entities) == max_nodes}


# ── planet / biome / stardust management ───────────────────────────────────

@mcp.tool(name="planet.list")
async def planet_list() -> dict:
    """List all planets and their biomes in the Galaxy, including those not in the Sun's planet_registry. Use this to discover the full routing namespace before writing stardust."""
    result = await tools_memory.planet_list()
    return await _session_wrap(_DEFAULT_AGENT, "planet.list", result)


@mcp.tool(name="biome.list")
async def biome_list(planet: str | None = None) -> dict:
    """List all biomes, optionally scoped to one planet. Use when you need to know valid biome names before writing stardust to a specific location."""
    result = await tools_memory.biome_list(planet)
    return await _session_wrap(_DEFAULT_AGENT, "biome.list", result)


@mcp.tool(name="stardust.get")
async def stardust_get(stardust_id: str) -> dict:
    """Fetch a specific stardust record by ID. Use to verify what was written or retrieve a record before superseding it with brain.think."""
    result = await tools_memory.stardust_get(stardust_id)
    return await _session_wrap(_DEFAULT_AGENT, "stardust.get", result)


@mcp.tool(name="stardust.delete")
async def stardust_delete(stardust_id: str) -> dict:
    """Permanently delete a stardust record by ID. Use to remove incorrect or test writes. Irreversible — use with care."""
    result = await tools_memory.stardust_delete(stardust_id)
    return await _session_wrap(_DEFAULT_AGENT, "stardust.delete", result)


# ── sun.* namespace (3 tools) ──────────────────────────────────────────────

@mcp.tool(name="sun.read")
async def sun_read(section: str | None = None) -> dict:
    """Read the Galaxy's Sun — the steering document for all agents. Sections: identity, values, agent_protocol, planet_registry, working_context, evolution_log."""
    result = await tools_sun.sun_read(section)
    return await _session_wrap(_DEFAULT_AGENT, "sun.read", result)


@mcp.tool(name="sun.update")
async def sun_update(section_key: str, content: dict, summary: str) -> dict:
    """Update a Sun section. Changes logged to evolution_log."""
    result = await tools_sun.sun_update(section_key, content, summary)
    return await _session_wrap(_DEFAULT_AGENT, "sun.update", result)


@mcp.tool(name="sun.working_context")
async def sun_working_context(
    current_focus: str | None = None,
    add_blocker: str | None = None,
    remove_blocker: str | None = None,
    add_decision: str | None = None,
    add_hot_biome: str | None = None,
    remove_hot_biome: str | None = None,
    clear_decisions: bool = False,
) -> dict:
    """Quick-update the working context scratchpad.

    Operations (all optional, combine freely):
    - current_focus (str): set what you're working on right now
    - add_blocker / remove_blocker (str): manage the blockers list
    - add_hot_biome / remove_hot_biome (str): manage frequently-accessed biomes
    - add_decision (str): append a decision to recent_decisions
    - clear_decisions (bool): wipe the recent_decisions list
    """
    result = await tools_sun.sun_working_context(
        current_focus, add_blocker, remove_blocker, add_decision,
        add_hot_biome, remove_hot_biome, clear_decisions,
    )
    return await _session_wrap(_DEFAULT_AGENT, "sun.working_context", result)


@mcp.tool(name="sun.lesson")
async def sun_lesson(correction: str, context: str = "", tags: list[str] | None = None,
                     severity: str = "medium", agent_name: str | None = None) -> dict:
    """Record a lesson learned — a correction or rule the agent should remember permanently.

    Parameters:
    - severity: 'low' · 'medium' (default) · 'high' · 'critical'
    - tags: topic tags for filtering (e.g. ['retrieval', 'routing'])
    """
    resolved = await _resolve_agent(agent_name)
    result = await tools_sun.sun_lesson(correction, context, tags or [], severity, resolved)
    return await _session_wrap(resolved, "sun.lesson", result)


@mcp.tool(name="sun.lesson_list")
async def sun_lesson_list(tags: list[str] | None = None, limit: int = 50,
                           include_resolved: bool = False) -> dict:
    """List lessons recorded in the Sun.

    Parameters:
    - tags: filter to lessons matching any of these topic tags
    - limit: max lessons to return (default 50)
    - include_resolved: set True to also include resolved lessons
    """
    result = await tools_sun.sun_lesson_list(tags, limit, include_resolved)
    return await _session_wrap(_DEFAULT_AGENT, "sun.lesson_list", result)


@mcp.tool(name="sun.lesson_resolve")
async def sun_lesson_resolve(lesson_id: str) -> dict:
    """Mark a lesson as resolved so it no longer appears in active lists.

    Parameters:
    - lesson_id: the ID from sun.lesson_list (e.g. 'L001')
    """
    result = await tools_sun.sun_lesson_resolve(lesson_id)
    return await _session_wrap(_DEFAULT_AGENT, "sun.lesson_resolve", result)


# ── Session management ──────────────────────────────────────────────────────

@mcp.tool(name="orion_session_end")
async def orion_session_end(summary: str = "", agent_name: str | None = None) -> dict:
    """End the current session. Logs session stats to Nebula."""
    resolved = await _resolve_agent(agent_name)
    stats = await tracker.end_session(resolved, summary or "Session ended by agent.")
    if not stats:
        return {"status": "no_active_session"}
    return {"status": "session_ended", **stats}


if __name__ == "__main__":
    settings = get_settings()
    logger.info(f"Starting Orion MCP server on port {settings.MCP_PORT}")
    mcp.run(transport="streamable-http")
