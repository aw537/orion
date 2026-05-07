"""Orion MCP Server — standalone, calls the Orion REST API.

20 tools across 4 namespaces:
  memory.* (5)  — knowledge management
  brain.*  (11) — cognitive operations + graph
  sun.*    (3)  — Galaxy steering
  orion_session_end (1) — session lifecycle
"""
import os
import logging
from mcp.server.fastmcp import FastMCP
from orion_mcp import client
from orion_mcp.session import tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orion.mcp")

MCP_PORT = int(os.environ.get("MCP_PORT", "8787"))
mcp = FastMCP("Orion", host="0.0.0.0", port=MCP_PORT)

_DEFAULT_AGENT = "mcp_client"


def _resolve_agent(agent_name: str | None) -> str:
    if agent_name:
        return agent_name
    sessions = tracker._sessions
    if len(sessions) == 1:
        return next(iter(sessions.values())).agent
    return _DEFAULT_AGENT


async def _wrap(agent: str, tool: str, result: dict, verbose: bool = False) -> dict:
    """Session tracking wrapper. On brain.orient first call, prepend session header.

    Compact mode (default): injects only _session; tool_result already contains all orientation data.
    Verbose mode: also injects raw _sun and _context blobs.
    """
    session = tracker.touch(agent, tool)
    if tracker.needs_context(agent):
        tracker.mark_context_injected(agent)
        if tool == "brain.orient":
            try:
                if verbose:
                    ctx = await client.memory_context()
                    sun = await client.sun_read()
                    result = {
                        "_session": {"session_id": session.id, "message": "Session started. Sun and context auto-loaded."},
                        "_sun": sun, "_context": ctx, "tool_result": result,
                    }
                else:
                    result = {
                        "_session": {"session_id": session.id, "message": "Session started."},
                        "tool_result": result,
                    }
            except Exception as e:
                logger.warning(f"Failed to wrap orient context: {e}")
    return result


# ── memory.* (5 tools) ──────────────────────────────────────────────

@mcp.tool(name="memory.write")
async def memory_write(content: str, planet: str | None = None, biome: str | None = None,
                        region: str = "contextual", context_tags: list[str] | None = None,
                        gravity: str = "BIOME") -> dict:
    """Store a piece of knowledge in your Galaxy. Planet is auto-routed if not specified."""
    r = await client.memory_write(content, planet, biome, region, context_tags, gravity)
    return await _wrap(_DEFAULT_AGENT, "memory.write", r)

@mcp.tool(name="memory.search")
async def memory_search(query: str, planet: str | None = None, biome: str | None = None,
                         region: str | None = None, limit: int = 5) -> dict:
    """Search for relevant knowledge in your Galaxy."""
    r = await client.memory_search(query, planet, biome, region, limit)
    return await _wrap(_DEFAULT_AGENT, "memory.search", r)

@mcp.tool(name="memory.context")
async def memory_context(planet: str | None = None, biome: str | None = None,
                          max_tokens: int = 4000, model: str | None = None) -> dict:
    """Get a structured context bundle for the current session."""
    r = await client.memory_context(planet, biome, max_tokens, model)
    return await _wrap(_DEFAULT_AGENT, "memory.context", r)

@mcp.tool(name="memory.status")
async def memory_status() -> dict:
    """Get current Galaxy health and system state."""
    r = await client.memory_status()
    return await _wrap(_DEFAULT_AGENT, "memory.status", r)

@mcp.tool(name="memory.entity_get")
async def memory_entity_get(entity_name: str, planet: str | None = None) -> dict:
    """Retrieve an entity profile with relationship context and timeline."""
    r = await client.memory_entity_get(entity_name, planet)
    return await _wrap(_DEFAULT_AGENT, "memory.entity_get", r)


# ── brain.* (10 tools) ──────────────────────────────────────────────

@mcp.tool(name="brain.orient")
async def brain_orient(agent_name: str, model: str, agent_type: str = "GENERAL",
                        active_planet: str | None = None, active_biome: str | None = None,
                        max_tokens: int | None = None, include_biome_stardust: bool = False,
                        verbose: bool = False) -> dict:
    """Orient yourself in your Galaxy at the start of every session. REQUIRED: Call this once at session start.

    Returns your persistent identity, current context, synthesized knowledge state, and operating protocol.
    The response includes session_id — pass it to subsequent calls to maintain session continuity.

    Parameters:
    - verbose: set True to also receive raw _sun and _context dumps (larger response, rarely needed)
    - include_biome_stardust: set True to embed biome stardust in one call (eliminates a memory.context follow-up)
    """
    r = await client.brain_orient(agent_name, model, agent_type, active_planet, active_biome, max_tokens, include_biome_stardust)
    return await _wrap(agent_name, "brain.orient", r, verbose=verbose)

@mcp.tool(name="brain.think")
async def brain_think(content: str, planet: str | None = None, biome: str | None = None,
                       cognitive_mode: str = "contextual", confidence: float = 0.7,
                       reasoning: str | None = None, supersedes: list[str] | None = None,
                       scope: str = "BIOME", context_tags: list[str] | None = None,
                       session_id: str | None = None, agent_name: str | None = None) -> dict:
    """Integrate new understanding into your brain. Planet is auto-routed if not specified."""
    r = await client.brain_think(content, planet, biome, cognitive_mode, confidence,
                                  reasoning, supersedes, scope, context_tags, session_id, agent_name)
    return await _wrap(_resolve_agent(agent_name), "brain.think", r)

@mcp.tool(name="brain.recall")
async def brain_recall(query: str, cognitive_mode: str | None = None,
                        planet: str | None = None, biome: str | None = None,
                        context_window: str | None = None, include_reasoning: bool = False,
                        include_graph_paths: bool = False, recency_weight: float = 0.3,
                        limit: int = 5, session_id: str | None = None,
                        agent_name: str | None = None, mode: str = "semantic") -> dict:
    """Access knowledge from your brain. Use the mode parameter to express retrieval intent:

    - mode="semantic" (default): raw records ranked by semantic similarity + recency + confidence.
      Best for: finding relevant knowledge chunks, filtering by cognitive_mode or biome.
    - mode="ask": natural language Q&A — returns a cited answer backed by specific records.
      Best for: "What decisions were made about auth?", "Who knows about Stripe?"
    - mode="synthesize": prose narrative over a topic — one LLM pass, no citations.
      Best for: summarising a broad topic, drafting a brief.
    - mode="concept": synthesized profile of a named entity or concept.
      Best for: "Tell me everything about FastAPI", "What is the MVP entity?"

    Parameters:
    - cognitive_mode: filter by region — 'contextual', 'strategic', 'analytical', 'creative'
    - context_window: prepend to query for better semantic matching
    """
    if mode == "ask":
        r = await client.brain_ask(query, planet, depth=2)
    elif mode == "synthesize":
        r = await client.brain_synthesize(query, planet, biome)
    elif mode == "concept":
        r = await client.brain_know(query, depth="detailed")
    else:
        r = await client.brain_recall(query, cognitive_mode, planet, biome, context_window,
                                       include_reasoning, include_graph_paths, recency_weight, limit, session_id)
    return await _wrap(_resolve_agent(agent_name), "brain.recall", r)

@mcp.tool(name="brain.calibrate")
async def brain_calibrate(session_id: str, records_used: list[str],
                           records_retrieved_unused: list[str] | None = None,
                           knowledge_gaps: list[str] | None = None,
                           session_outcome: str | None = None,
                           knowledge_quality_score: float | None = None,
                           agent_name: str | None = None) -> dict:
    """Teach your brain what was useful this session."""
    r = await client.brain_calibrate(session_id, records_used, records_retrieved_unused,
                                      knowledge_gaps, session_outcome, knowledge_quality_score)
    return await _wrap(_resolve_agent(agent_name), "brain.calibrate", r)

@mcp.tool(name="brain.health")
async def brain_health(agent_name: str) -> dict:
    """Assess the current cognitive health of your brain."""
    r = await client.brain_health(agent_name)
    return await _wrap(agent_name, "brain.health", r)

@mcp.tool(name="brain.know")
async def brain_know(concept: str, depth: str = "summary", agent_name: str | None = None) -> dict:
    """Access your synthesized understanding of a concept."""
    r = await client.brain_know(concept, depth)
    return await _wrap(_resolve_agent(agent_name), "brain.know", r)

@mcp.tool(name="brain.graph_query")
async def brain_graph_query(entity_name: str, relationship_types: list[str] | None = None,
                             depth: int = 2, agent_name: str | None = None) -> dict:
    """Traverse the knowledge graph from an entity."""
    r = await client.brain_graph_query(entity_name, relationship_types, depth)
    return await _wrap(_resolve_agent(agent_name), "brain.graph_query", r)

@mcp.tool(name="brain.find_path")
async def brain_find_path(source_concept: str, target_concept: str,
                           agent_name: str | None = None) -> dict:
    """Find the connection between two concepts in your knowledge graph. When no path exists, returns reason: 'no_path' (concepts unrelated) or 'no_edges' (graph is empty)."""
    r = await client.brain_find_path(source_concept, target_concept)
    if isinstance(r, dict) and r.get("path") is None and "reason" not in r:
        r["reason"] = "no_path"
    return await _wrap(_resolve_agent(agent_name), "brain.find_path", r)

@mcp.tool(name="brain.diff")
async def brain_diff(topic: str, since: str, planet: str | None = None,
                     agent_name: str | None = None) -> dict:
    """Show what changed about a topic since a given date.

    Parameters:
    - topic: keyword or phrase to match against stardust content
    - since: ISO 8601 datetime (e.g. '2026-05-01' or '2026-05-01T00:00:00')
    - planet: optional planet name to scope the diff
    """
    r = await client.brain_diff(topic, since, planet)
    return await _wrap(_resolve_agent(agent_name), "brain.diff", r)


@mcp.tool(name="brain.ask")
async def brain_ask(question: str, planet: str | None = None, depth: int = 2,
                     agent_name: str | None = None) -> dict:
    """Ask a natural language question and get a cited answer from your Galaxy's knowledge. Routes to graph traversal or semantic search based on intent. Use brain.synthesize instead when you want a prose narrative with no citations."""
    r = await client.brain_ask(question, planet, depth)
    return await _wrap(_resolve_agent(agent_name), "brain.ask", r)

@mcp.tool(name="brain.synthesize")
async def brain_synthesize(topic: str, planet: str | None = None, biome: str | None = None,
                            include_open_questions: bool = True, include_contradictions: bool = True,
                            max_tokens: int = 1000, agent_name: str | None = None) -> dict:
    """Get a synthesized prose narrative about a topic from your brain. Runs a single LLM pass over all relevant records and returns a coherent narrative with no citations. Use brain.ask instead when you want a cited factual answer."""
    r = await client.brain_synthesize(topic, planet, biome, include_open_questions,
                                       include_contradictions, max_tokens)
    return await _wrap(_resolve_agent(agent_name), "brain.synthesize", r)


@mcp.tool(name="brain.graph_full")
async def brain_graph_full(
    planet: str | None = None, max_nodes: int = 100, agent_name: str | None = None,
) -> dict:
    """Get the entity knowledge graph with all edges. Use planet to scope to one domain. max_nodes caps the result to avoid token explosion on large graphs."""
    r = await client.graph_full(planet=planet, max_nodes=max_nodes)
    return await _wrap(_resolve_agent(agent_name), "brain.graph_full", r)


# ── sun.* (6 tools) ─────────────────────────────────────────────────

@mcp.tool(name="sun.read")
async def sun_read(section: str | None = None) -> dict:
    """Read the Galaxy's Sun — the steering document for all agents."""
    r = await client.sun_read(section)
    return await _wrap(_DEFAULT_AGENT, "sun.read", r)

@mcp.tool(name="sun.update")
async def sun_update(section_key: str, content: dict, summary: str) -> dict:
    """Update a Sun section. Changes logged to evolution_log."""
    r = await client.sun_update(section_key, content, summary)
    return await _wrap(_DEFAULT_AGENT, "sun.update", r)

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
    - add_hot_biome / remove_hot_biome (str): manage frequently-accessed biomes (surfaced in brain.orient orientation and used as retrieval hints)
    - add_decision (str): append a decision to recent_decisions
    - clear_decisions (bool): wipe the recent_decisions list
    """
    r = await client.sun_working_context(
        current_focus, add_blocker, remove_blocker, add_decision,
        add_hot_biome, remove_hot_biome, clear_decisions,
    )
    return await _wrap(_DEFAULT_AGENT, "sun.working_context", r)


@mcp.tool(name="sun.lesson")
async def sun_lesson(correction: str, context: str = "", tags: list[str] | None = None,
                     severity: str = "medium", agent_name: str | None = None) -> dict:
    """Record a lesson learned — a correction or rule the agent should remember permanently.

    Parameters:
    - severity: one of 'low', 'medium' (default), 'high', 'critical'
    - tags: list of topic tags for filtering (e.g. ['retrieval', 'routing'])
    """
    resolved = _resolve_agent(agent_name)
    r = await client.sun_lesson(correction, context, tags, resolved, severity)
    return await _wrap(resolved, "sun.lesson", r)


@mcp.tool(name="sun.lesson_list")
async def sun_lesson_list(tags: list[str] | None = None, limit: int = 20,
                           include_resolved: bool = False) -> dict:
    """List lessons recorded in the Sun. Active lessons only by default.

    Parameters:
    - tags: filter to lessons matching any of these topic tags
    - limit: max lessons to return (default 20)
    - include_resolved: set True to also include resolved lessons
    """
    r = await client.sun_lesson_list(tags, limit, include_resolved)
    return await _wrap(_DEFAULT_AGENT, "sun.lesson_list", r)


@mcp.tool(name="sun.lesson_resolve")
async def sun_lesson_resolve(lesson_id: str) -> dict:
    """Mark a lesson as resolved so it no longer appears in active lists.

    Parameters:
    - lesson_id: the ID from sun.lesson_list (e.g. 'L001')
    """
    r = await client.sun_lesson_resolve(lesson_id)
    return await _wrap(_DEFAULT_AGENT, "sun.lesson_resolve", r)


# ── Planet / Biome / Stardust management ────────────────────────────────────

@mcp.tool(name="planet.list")
async def planet_list() -> dict:
    """List all planets and their biomes in the Galaxy, including those not in the Sun's planet_registry. Use this to discover the full routing namespace before writing stardust."""
    r = await client.planet_list()
    return await _wrap(_DEFAULT_AGENT, "planet.list", r)


@mcp.tool(name="biome.list")
async def biome_list(planet: str | None = None) -> dict:
    """List all biomes, optionally scoped to one planet. Use when you need to know valid biome names before writing stardust to a specific location."""
    r = await client.biome_list(planet)
    return await _wrap(_DEFAULT_AGENT, "biome.list", r)


@mcp.tool(name="stardust.get")
async def stardust_get(stardust_id: str) -> dict:
    """Fetch a specific stardust record by ID. Use to verify what was written or retrieve a record before superseding it with brain.think."""
    r = await client.stardust_get(stardust_id)
    return await _wrap(_DEFAULT_AGENT, "stardust.get", r)


@mcp.tool(name="stardust.delete")
async def stardust_delete(stardust_id: str) -> dict:
    """Permanently delete a stardust record by ID. Use to remove incorrect or test writes. Irreversible — use with care."""
    r = await client.stardust_delete(stardust_id)
    return await _wrap(_DEFAULT_AGENT, "stardust.delete", r)


# ── Session management ───────────────────────────────────────────────

@mcp.tool(name="orion_session_end")
async def orion_session_end(summary: str = "", agent_name: str | None = None) -> dict:
    """End the current session."""
    resolved = _resolve_agent(agent_name)
    stats = tracker.end_session(resolved)
    if not stats:
        return {"status": "no_active_session"}
    return {"status": "session_ended", **stats}


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health_check(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})


def main():
    logger.info(f"Starting Orion MCP server on port {MCP_PORT}")
    logger.info(f"Backend API: {client.API_BASE}")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
