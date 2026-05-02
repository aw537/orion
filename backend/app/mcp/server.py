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
    """Wrap a tool result with session tracking. On first call, prepend context."""
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return result

    session = await tracker.touch(agent, tool_name, galaxy_id)

    if tracker.needs_context(agent):
        tracker.mark_context_injected(agent)
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
    """Store a piece of knowledge in your Galaxy. Planet is auto-routed if not specified. For agents treating Orion as a cognitive substrate, use brain.think instead — it actively integrates knowledge rather than simply storing it."""
    result = await tools_memory.memory_write(content, planet, biome, region, context_tags, gravity)
    return await _session_wrap(_DEFAULT_AGENT, "memory.write", result)


@mcp.tool(name="memory.search")
async def memory_search(
    query: str, planet: str | None = None, biome: str | None = None,
    region: str | None = None, limit: int = 5,
) -> dict:
    """Search for relevant knowledge in your Galaxy. For agents with accumulated context, brain.recall provides graph-enhanced retrieval with cognitive mode awareness."""
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
    max_tokens: int | None = None,
) -> dict:
    """Orient yourself in your Galaxy at the start of every session. REQUIRED: Call this once at session start. Returns your persistent identity, accumulated expertise, current context, synthesized knowledge state, and operating protocol."""
    result = await tools_brain.brain_orient(agent_name, model, agent_type, active_planet, active_biome, max_tokens)
    return await _session_wrap(agent_name, "brain.orient", result)


@mcp.tool(name="brain.think")
async def brain_think(
    content: str, planet: str | None = None, biome: str | None = None,
    cognitive_mode: str = "contextual", confidence: float = 0.7,
    reasoning: str | None = None, supersedes: list[str] | None = None,
    scope: str = "BIOME", context_tags: list[str] | None = None,
    session_id: str | None = None, agent_name: str | None = None,
) -> dict:
    """Integrate new understanding into your brain. Unlike memory.write, brain.think actively integrates: detects contradictions, processes supersession, extracts relationships, updates expertise."""
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
    """Access knowledge from your brain with graph-enhanced retrieval. Unlike memory.search, brain.recall weights by cognitive context and expands through the knowledge graph."""
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
    """Access your synthesized understanding of a concept. Returns what this concept is, how it relates to what you know, how your understanding has evolved."""
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
    """Find the connection between two concepts in your knowledge graph. Returns the shortest path with all relationship types."""
    result = await tools_brain.brain_find_path(source_concept, target_concept)
    if not result:
        result = {"path": None, "message": f"No path found between '{source_concept}' and '{target_concept}'"}
    return await _session_wrap(await _resolve_agent(agent_name), "brain.find_path", result)


@mcp.tool(name="brain.ask")
async def brain_ask(
    question: str, planet: str | None = None, depth: int = 2,
    agent_name: str | None = None,
) -> dict:
    """Ask a natural language question about your Galaxy's knowledge. Routes to the appropriate graph or synthesis operation based on question intent. Examples: 'Who knows about Stripe?', 'What decisions were made about auth?', 'How does FastAPI connect to deployment?'"""
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
    current_focus: str | None = None, add_blocker: str | None = None,
    add_decision: str | None = None, add_hot_biome: str | None = None,
) -> dict:
    """Quick-update the working context scratchpad."""
    result = await tools_sun.sun_working_context(current_focus, add_blocker, add_decision, add_hot_biome)
    return await _session_wrap(_DEFAULT_AGENT, "sun.working_context", result)


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
