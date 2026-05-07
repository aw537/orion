"""Orion MCP — HTTP client for the Orion REST API."""
import httpx
import os
import logging

logger = logging.getLogger("orion.mcp.client")

API_BASE = os.environ.get("ORION_API_URL", "http://localhost:8000")
API_TOKEN = os.environ.get("ORION_TOKEN", "")

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=API_BASE, timeout=60.0)
    return _client


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Bearer {API_TOKEN}"
    return h


async def _get(path: str, params: dict | None = None) -> dict:
    try:
        c = _get_client()
        r = await c.get(path, params=params, headers=_headers())
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        body = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("detail") or body.get("error") or str(e)
        logger.warning(f"API error {e.response.status_code} on GET {path}: {detail}")
        return {"error": detail, "status_code": e.response.status_code}
    except httpx.ConnectError:
        logger.error(f"Cannot connect to Orion API at {API_BASE}")
        return {"error": f"Cannot connect to Orion API at {API_BASE}. Is the backend running?"}
    except Exception as e:
        logger.error(f"Unexpected error on GET {path}: {e}")
        return {"error": str(e)}


async def _post(path: str, json: dict | None = None) -> dict:
    try:
        c = _get_client()
        r = await c.post(path, json=json, headers=_headers())
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        body = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("detail") or body.get("error") or str(e)
        logger.warning(f"API error {e.response.status_code} on POST {path}: {detail}")
        return {"error": detail, "status_code": e.response.status_code}
    except httpx.ConnectError:
        logger.error(f"Cannot connect to Orion API at {API_BASE}")
        return {"error": f"Cannot connect to Orion API at {API_BASE}. Is the backend running?"}
    except Exception as e:
        logger.error(f"Unexpected error on POST {path}: {e}")
        return {"error": str(e)}


async def _put(path: str, json: dict | None = None) -> dict:
    try:
        c = _get_client()
        r = await c.put(path, json=json, headers=_headers())
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        body = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("detail") or body.get("error") or str(e)
        logger.warning(f"API error {e.response.status_code} on PUT {path}: {detail}")
        return {"error": detail, "status_code": e.response.status_code}
    except httpx.ConnectError:
        logger.error(f"Cannot connect to Orion API at {API_BASE}")
        return {"error": f"Cannot connect to Orion API at {API_BASE}. Is the backend running?"}
    except Exception as e:
        logger.error(f"Unexpected error on PUT {path}: {e}")
        return {"error": str(e)}


# ── Brain endpoints ─────────────────────────────────────────────────

async def brain_orient(agent_name, model, agent_type="GENERAL", active_planet=None, active_biome=None, max_tokens=None, include_biome_stardust=False):
    return await _post("/api/v1/brain/orient", {
        "agent_name": agent_name, "model": model, "agent_type": agent_type,
        "active_planet": active_planet, "active_biome": active_biome, "max_tokens": max_tokens,
        "include_biome_stardust": include_biome_stardust,
    })

async def brain_think(content, planet, biome=None, cognitive_mode="contextual", confidence=0.7,
                       reasoning=None, supersedes=None, scope="BIOME", context_tags=None,
                       session_id=None, agent_name=None):
    return await _post("/api/v1/brain/think", {
        "content": content, "planet": planet, "biome": biome,
        "cognitive_mode": cognitive_mode, "confidence": confidence,
        "reasoning": reasoning, "supersedes": supersedes, "scope": scope,
        "context_tags": context_tags, "session_id": session_id, "agent_name": agent_name,
    })

async def brain_recall(query, cognitive_mode=None, planet=None, biome=None, context_window=None,
                        include_reasoning=False, include_graph_paths=False, recency_weight=0.3,
                        limit=5, session_id=None):
    return await _post("/api/v1/brain/recall", {
        "query": query, "cognitive_mode": cognitive_mode, "planet": planet, "biome": biome,
        "context_window": context_window, "include_reasoning": include_reasoning,
        "include_graph_paths": include_graph_paths, "recency_weight": recency_weight,
        "limit": limit, "session_id": session_id,
    })

async def brain_calibrate(session_id, records_used, records_retrieved_unused=None,
                           knowledge_gaps=None, session_outcome=None, knowledge_quality_score=None):
    return await _post("/api/v1/brain/calibrate", {
        "session_id": session_id, "records_used": records_used,
        "records_retrieved_unused": records_retrieved_unused,
        "knowledge_gaps": knowledge_gaps, "session_outcome": session_outcome,
        "knowledge_quality_score": knowledge_quality_score,
    })

async def brain_health(agent_name):
    return await _get(f"/api/v1/brain/health/{agent_name}")

async def brain_know(concept, depth="summary"):
    return await _post("/api/v1/brain/know", {"concept": concept, "depth": depth})

async def brain_graph_query(entity_name, relationship_types=None, depth=2):
    return await _post("/api/v1/brain/graph-query", {
        "entity_name": entity_name, "relationship_types": relationship_types, "depth": depth,
    })

async def brain_find_path(source_concept, target_concept):
    return await _post("/api/v1/brain/find-path", {
        "source_concept": source_concept, "target_concept": target_concept,
    })

async def brain_ask(question, planet=None, depth=2):
    return await _post("/api/v1/ask", {"question": question, "planet": planet, "depth": depth})

async def brain_synthesize(topic, planet=None, biome=None, include_open_questions=True,
                            include_contradictions=True, max_tokens=1000):
    return await _post("/api/v1/synthesize", {
        "topic": topic, "planet": planet, "biome": biome,
        "include_open_questions": include_open_questions,
        "include_contradictions": include_contradictions,
    })


# ── Memory endpoints ────────────────────────────────────────────────

async def memory_write(content, planet, biome=None, region="contextual", context_tags=None, gravity="BIOME"):
    return await _post("/api/v1/brain/write", {
        "content": content, "planet": planet, "biome": biome,
        "region": region, "context_tags": context_tags, "gravity": gravity,
    })

async def memory_search(query, planet=None, biome=None, region=None, limit=5):
    params = {"query": query, "limit": limit}
    if planet: params["planet"] = planet
    if biome: params["biome"] = biome
    if region: params["region"] = region
    return await _get("/api/v1/search", params)

async def memory_context(planet=None, biome=None, max_tokens=4000, model=None):
    return await _post("/api/v1/brain/context", {
        "planet": planet, "biome": biome, "max_tokens": max_tokens, "model": model,
    })

async def memory_status():
    return await _get("/api/v1/brain/status")

async def memory_entity_get(entity_name, planet=None):
    return await _post("/api/v1/brain/entity-get", {"entity_name": entity_name, "planet": planet})


# ── Sun endpoints ───────────────────────────────────────────────────

async def sun_read(section=None):
    if section:
        return await _get(f"/api/v1/sun/{section}")
    return await _get("/api/v1/sun")

async def sun_update(section_key, content, summary):
    return await _put(f"/api/v1/sun/{section_key}", content)

async def sun_working_context(
    current_focus=None, add_blocker=None, remove_blocker=None,
    add_decision=None, add_hot_biome=None, remove_hot_biome=None,
    clear_decisions=False,
):
    results = {}
    if current_focus is not None:
        wc = await _get("/api/v1/sun/working_context")
        c = wc.get("content", {}) if isinstance(wc, dict) and "error" not in wc else {}
        c["current_focus"] = current_focus
        results["focus"] = await _put("/api/v1/sun/working_context", {"content": c, "changed_by": "agent", "summary": f"Set current focus: {str(current_focus)[:50]}"})
    if add_blocker:
        results["blocker"] = await _post("/api/v1/sun/working-context/add-blocker", {"blocker": add_blocker})
    if remove_blocker:
        results["remove_blocker"] = await _post("/api/v1/sun/working-context/remove-blocker", {"blocker": remove_blocker})
    if add_hot_biome:
        results["hot_biome"] = await _post("/api/v1/sun/working-context/add-hot-biome", {"biome": add_hot_biome})
    if remove_hot_biome:
        results["remove_hot_biome"] = await _post("/api/v1/sun/working-context/remove-hot-biome", {"biome": remove_hot_biome})
    if add_decision:
        results["decision"] = await _post("/api/v1/sun/working-context/add-decision", {"decision": add_decision})
    if clear_decisions:
        results["clear_decisions"] = await _post("/api/v1/sun/working-context/clear-decisions", {})
    return results or {"status": "no changes"}


async def sun_lesson(correction: str, context: str = "", tags: list[str] | None = None, agent_name: str = "mcp_client", severity: str = "medium"):
    return await _post("/api/v1/sun/lessons", {
        "correction": correction, "context": context,
        "tags": tags or [], "agent_name": agent_name, "severity": severity,
    })


async def sun_lesson_list(tags: list[str] | None = None, limit: int = 50, include_resolved: bool = False):
    params: dict = {"limit": limit, "include_resolved": str(include_resolved).lower()}
    if tags:
        params["tags"] = ",".join(tags)
    lessons = await _get("/api/v1/sun/lessons", params)
    if isinstance(lessons, list):
        return {"lessons": lessons, "total": len(lessons)}
    return lessons


async def sun_lesson_resolve(lesson_id: str):
    return await _post(f"/api/v1/sun/lessons/{lesson_id}/resolve")


# ── Planet / Biome / Stardust management ───────────────────────────────────

async def planet_list():
    return await _get("/api/v1/brain/planets")

async def biome_list(planet: str | None = None):
    params = {"planet": planet} if planet else None
    return await _get("/api/v1/brain/biomes", params)

async def stardust_get(stardust_id: str):
    return await _get(f"/api/v1/brain/stardust/{stardust_id}")

async def stardust_delete(stardust_id: str):
    try:
        c = _get_client()
        r = await c.delete(f"/api/v1/brain/stardust/{stardust_id}", headers=_headers())
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Nebula (session logging) ────────────────────────────────────────

async def graph_full():
    return await _get("/api/v1/graph/full")


async def log_nebula_event(galaxy_id: str, action_type: str, initiated_by: str,
                            session_id: str | None = None, payload: str | None = None):
    """Post a session lifecycle event to the Nebula interaction log."""
    return await _post("/api/v1/nebula", {
        "galaxy_id": galaxy_id, "action_type": action_type,
        "initiated_by": initiated_by, "session_id": session_id,
        "payload_after": payload,
    })
