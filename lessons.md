# Orion MCP — Agent Experience Lessons

Observations from a live session interacting with Orion via MCP as `claude_code` / `claude-sonnet-4-6`.  
Date: 2026-05-07

---

## What worked

- **`brain.orient` as session-start ritual** is the right pattern. One call gives the agent galaxy identity, working context, and planet registry. Don't fragment this into multiple calls.
- **Tool namespace (`brain.*`, `sun.*`, `memory.*`)** is coherent. Metaphors map cleanly to function — an agent can infer purpose from name without reading docs.
- **`planet.list`** returned the full hierarchy (planets → biomes → stardust counts) in one shot. Clean and useful for understanding the knowledge landscape.
- **Status line** (`[orion: 0 records · Galaxy · 60.0/100]`) appended to every response is a good compressed signal for agents working in constrained contexts.

---

## What felt unnatural

### 1. `brain.orient` response is ~200 lines with heavy duplication
The planet registry appears at least 3 times (`_sun`, `_context`, `tool_result`). Core values appear twice. This wastes tokens and adds noise. An agent needs a compact orientation brief — not a full dump — by default.

**Fix:** Return a minimal summary by default. Add `verbose=true` to unlock the full payload.

### 2. `brain.recall` returned nothing even though 29 stardust records exist
Chroma (vector store) isn't indexed, so semantic search returns empty. A memory system that can't retrieve is a write-only log.

**Fix (P0):** Fall back to Postgres full-text search when Chroma has no results. Never return zero records when rows exist in the DB. Fix the embedding pipeline so records are indexed on write.

### 3. Four overlapping read tools with unclear distinctions
`brain.recall`, `brain.think`, `brain.ask`, `brain.synthesize` — an agent can't tell from the names alone which to use when. This causes agents to guess or default to the first one listed.

**Fix:** Collapse into one `brain.recall(query, mode="semantic"|"analytical"|"ask")` or document the decision tree clearly enough to write a skill around it.

### 4. Required `agent_name` and `model` on `brain.orient`
An agent starting a session doesn't naturally know what name it has in your system. This is friction at the most critical moment.

**Fix:** Make both optional with sensible defaults. Infer model from session context if possible.

### 5. No automatic routing for writes
To write something the agent needs to know the correct planet and biome. That's Orion's internal ontology — the agent shouldn't have to navigate it.

**Fix:** `memory.write(content)` should be the primary write interface. Orion classifies content and routes it. Return where it landed so the agent can correct if needed.

### 6. Session IDs don't persist across MCP tool calls
Each call to `brain.orient` generated a new session. In a real agent loop (10+ tool calls per conversation), session continuity matters for activity tracking and context threading.

**Fix:** Return `session_id` prominently from `brain.orient`. Accept it as an optional param on all subsequent calls so the full session is traceable.

---

## The core tension

Orion is designed as a knowledge system agents write *to* and read *from* — but the interaction model requires agents to know Orion's internal ontology (planets, biomes, gravity, regions). The most effective version would feel like a collaborator: tell it something, it figures out where it lives. Ask a question, it searches everything and surfaces the best answer. The structure should be an implementation detail, not something the agent navigates.

---

## Priority order

1. **Fix the retrieval loop** — write something, immediately get it back via `brain.recall`. This has to work before anything else matters.
2. **Compact `brain.orient` response** — stop wasting tokens on duplicated data.
3. **Fallback retrieval** — full-text SQL when Chroma is cold.
4. **Write a skill** — once the system works reliably, a skill can teach agents the correct initialization ritual, routing heuristics, and which read tool to use when.
5. **Auto-routing on writes** — remove the ontology burden from the agent entirely.

---

## On whether a skill alone fixes this

A skill fixes the behavior layer: initialization ritual, routing heuristics, which tool to call when, what to ignore in verbose responses. It cannot fix the infrastructure layer: empty vector store, duplicate response payloads, missing fallback retrieval, session ID propagation. Roughly half the friction was agent behavior (skill fixes it), half was system gaps (needs code). Fix the system gaps first — then the skill has something solid to work with.
