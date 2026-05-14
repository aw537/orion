# Orion — Persistent Memory & Brain for AI Agents

https://www.starmemory.ai

Orion gives AI agents persistent memory across sessions. It runs locally via Docker — no cloud, no subscriptions, your data stays on your machine.

**Without Orion:** every AI session starts from zero.
**With Orion:** agents accumulate knowledge, build expertise, and get better over time.

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- ~4 GB disk space (for Ollama models)

### 1. Clone and start

```bash
git clone https://github.com/aw537/orion && cd orion
cp .env.example .env
docker compose up
```

First startup takes a few minutes — Ollama downloads the embedding model (`nomic-embed-text`) and LLM (`llama3`). Subsequent starts are fast.

### 2. Create your Galaxy

Open `http://localhost:3000` and complete the onboarding wizard (7 steps, all skippable):

1. **Role** — your role determines the default Planet structure
2. **Galaxy template** — pick a pre-configured template (Full-Stack SaaS, ML & Research, Open Source, Solo Founder) or start from scratch
3. **Import source** — local folder, Obsidian vault, Git repo, or start empty
4. **Name your first Biome** — name your first project context
5. **About you** — name, communication style, current goal
6. **Steering document** — import a CLAUDE.md or custom agent rules file
7. **Tools & preferences** — technologies you use, contradiction handling

Or via CLI:

```bash
pip install -e ./backend
orion init
```

### 3. Connect your AI tool

**Claude Code:**
```bash
claude mcp add orion --transport http http://localhost:8787/mcp
```

**Cursor:** Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "orion": { "url": "http://localhost:8787/mcp" }
  }
}
```

**Any MCP-compatible client:** Point to `http://localhost:8787/mcp`

That's it. Your AI agent now has persistent memory.

---

## Architecture

Orion is three independent services that communicate over HTTP, backed by three storage engines:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐
│   Frontend      │     │   MCP Server    │     │    REST API         │
│   :3000         │────▶│   :8787         │────▶│    :8000            │
│   React/D3 UI   │     │   28 tools      │     │    21 route groups  │
└─────────────────┘     └─────────────────┘     └──────────┬──────────┘
                                                            │
                        ┌───────────────────────────────────┼───────────────────────────┐
                        │                                   │                           │
                 ┌──────┴──────┐                   ┌────────┴───────┐         ┌────────┴────────┐
                 │  PostgreSQL │                   │     Redis      │         │    ChromaDB     │
                 │  :5432      │                   │    :6379       │         │  (7 vector      │
                 │  relational │                   │  hot cache +   │         │   collections   │
                 │  store      │                   │  sessions      │         │   per galaxy)   │
                 └─────────────┘                   └────────────────┘         └─────────────────┘
                                                                                        │
                                                                              ┌─────────┴──────────┐
                                                                              │    Ollama  :11434  │
                                                                              │  (embeddings + LLM)│
                                                                              └────────────────────┘
```

**The MCP server is a standalone HTTP client of the REST API.** It has zero direct dependencies on the backend — it only needs the API URL. This means:

- All Orion features work through the REST API alone, without MCP
- The MCP server can run anywhere — locally, at the edge, or as a hosted service
- AI tool extensions are thin wrappers around the MCP package

### Services

| URL | Service | Description |
|-----|---------|-------------|
| `http://localhost:3000` | Frontend | Galaxy visualization, knowledge graph, agent panels |
| `http://localhost:8000` | REST API | 21 route groups, OpenAPI docs at `/docs` |
| `http://localhost:8787` | MCP Server | 28 tools for AI agents |
| `http://localhost:5432` | PostgreSQL | Primary relational store |
| `http://localhost:6379` | Redis | Hot stardust cache + session store |
| `http://localhost:8000` | ChromaDB | Semantic vector search (internal port) |
| `http://localhost:11434` | Ollama | Local LLM + embedding inference |

### Project Structure

```
orion/
├── backend/        # FastAPI REST API — models, services, database
│   ├── app/
│   │   ├── api/            # Route handlers (21 modules)
│   │   ├── services/       # Business logic (search, brain, routing, audit…)
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── storage/        # Redis, ChromaDB, embedding router clients
│   │   ├── mcp/            # MCP tool implementations (tools_brain, tools_memory, tools_sun)
│   │   ├── auth/           # JWT auth, permissions, role checks
│   │   └── scheduler/      # APScheduler (weekly audit, digest)
│   └── alembic/            # Database migrations (6 versions)
├── frontend/       # React UI — Galaxy Canvas, knowledge graph, dashboards
│   └── src/
│       ├── views/          # Page-level components (GalaxyView, BiomeView, SunView…)
│       ├── components/     # Feature components (galaxy/, search/, inbox/, ui/)
│       │   └── ui/         # Shared design system: Button, NavButton, Panel, Input, Pill
│       ├── hooks/          # Custom hooks (useFocusTrap, useNebulaStream)
│       ├── api/            # API client and TanStack Query hooks
│       └── store/          # Zustand stores (nebulaStore)
├── mcp/            # Standalone MCP server — calls backend via HTTP
│   └── orion_mcp/
│       ├── server.py       # FastMCP server, 28 registered tools
│       ├── client.py       # HTTP client to backend REST API
│       └── session.py      # Per-agent session tracking + idle timeout
├── content/        # Galaxy templates (YAML) and default steering doc
└── docker-compose.yml
```

---

## MCP Tools (what your AI agent can use)

### Memory tools — for any AI tool, zero config

| Tool | What it does |
|------|-------------|
| `memory.write` | Store knowledge. `planet` is optional — the routing engine assigns it automatically. Receipt includes `planet_name`, `biome_name`, `routing_method`, and `routing_reasoning`. |
| `memory.search` | Semantic search across your Galaxy with RRF fusion (semantic + recency + confidence). |
| `memory.context` | Structured context bundle sized to a token budget. Priority-ranked: Sun → hot cache → high-confidence → entities → medium-confidence. |
| `memory.status` | Galaxy health, planets, biomes, strength score. |
| `memory.entity_get` | Entity profile with relationships, timeline, and related stardust. |

### Brain tools — for agents with persistent identity

| Tool | What it does |
|------|-------------|
| `brain.orient` | Call at session start. Returns identity, context, knowledge state, and protocol. Detects model switches and injects a transition brief. Compact by default; pass `verbose=true` for full Sun and context blobs. |
| `brain.think` | Store understanding with auto-routing, contradiction detection, relationship extraction, and expertise tracking. `planet` is optional. Receipt includes routing details. |
| `brain.recall` | Retrieval with `mode` param: `semantic` (default, RRF-ranked), `ask` (natural language Q&A with citations), `synthesize` (LLM prose with confidence + open questions), `concept` (entity profile + graph neighborhood). |
| `brain.calibrate` | End-of-session feedback. Teaches the brain what was useful — adjusts confidence scores on retrieved records. |
| `brain.health` | Cognitive health: freshness score, coverage gaps, stale beliefs, enrichment recommendations. |
| `brain.know` | Synthesized understanding of a concept at `summary`, `detailed`, or `full_history` depth. |
| `brain.graph_query` | Traverse the knowledge graph from an entity with optional relationship type filtering. |
| `brain.find_path` | Shortest path between two concepts (max 6 hops, BFS, cached 1h). |
| `brain.diff` | What changed about a topic since a given date — useful for catching up between sessions. |
| `brain.ask` | Natural language question, routed to graph traversal or semantic search depending on intent. |
| `brain.synthesize` | Generate a prose narrative over a topic with open questions and contradictions. |
| `brain.graph_full` | Full knowledge graph — all entities and edges (max 100 nodes). |

### Sun tools — Galaxy steering document

| Tool | What it does |
|------|-------------|
| `sun.read` | Read the Sun or a specific section (identity, values, agent_protocol, planet_registry, working_context, evolution_log). |
| `sun.update` | Update a Sun section. Changes are logged to the evolution log. |
| `sun.working_context` | Quick-update current focus, blockers, recent decisions, hot biomes. |
| `sun.lesson` | Record a permanent lesson or correction with severity (low/medium/high/critical) and tags. |
| `sun.lesson_list` | List active lessons, optionally filtered by tags or including resolved ones. |
| `sun.lesson_resolve` | Mark a lesson as resolved — it stays in history but is excluded from active lists. |

### Management tools

| Tool | What it does |
|------|-------------|
| `planet.list` | All planets and biomes in the galaxy. |
| `biome.list` | All biomes, optionally scoped to a planet. |
| `stardust.get` | Fetch a single knowledge record by ID. |
| `stardust.delete` | Permanently delete a record (requires `confirm=true`). Cascades to backlinks, relationships, and routing logs. |

### Session lifecycle

| Tool | What it does |
|------|-------------|
| `orion_session_end` | End the current session and return usage stats (reads, writes, duration). |

---

## Using Orion Without MCP

Every MCP tool has a corresponding REST endpoint. You can use Orion entirely through the REST API — no MCP required.

```bash
# Write knowledge
curl -X POST http://localhost:8000/api/v1/brain/write \
  -H "Content-Type: application/json" \
  -d '{"content": "FastAPI uses Starlette under the hood", "planet": "Engineering"}'

# Search
curl "http://localhost:8000/api/v1/search?query=FastAPI&limit=5"

# Orient an agent
curl -X POST http://localhost:8000/api/v1/brain/orient \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "my-agent", "model": "claude-sonnet-4-6"}'

# Ask a natural language question
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the team know about authentication?"}'

# Galaxy status
curl http://localhost:8000/api/v1/brain/status
```

Full OpenAPI docs at `http://localhost:8000/docs`.

---

## The Data Model

```
Galaxy (your entire knowledge universe)
├── Sun (steering document — identity, values, agent protocol, working context, lessons)
├── Agent Identities (persistent AI agents with expertise profiles and quality scores)
├── Knowledge Graph (entities with typed relationships, BFS-traversable)
└── Planets (knowledge domains — Engineering, Personal, Research)
    └── Biomes (project contexts — "Orion Backend", "Auth Refactor")
        │   lifecycle: SEED → ACTIVE → MATURE → DORMANT → ARCHIVED
        ├── Stardust (atomic knowledge records)
        │   ├── region      one of 7 cognitive types (see below)
        │   ├── gravity     BIOME | PLANET | GALAXY (scope)
        │   ├── confidence  0.0–1.0, evolves over time
        │   └── valid_from / valid_until (temporal validity)
        ├── Entities (people, tools, concepts — auto-extracted)
        └── Contradictions (conflicting facts — tracked and resolved)
```

### Cognitive Regions

Every piece of stardust is classified into one of seven cognitive regions. Each region has its own Chroma vector collection and Redis TTL policy:

| Region | TTL | Captures |
|--------|-----|---------|
| `analytical` | 8h | Decisions, trade-offs, reasoning chains |
| `procedural` | 24h | Steps, how-tos, runbooks |
| `contextual` | 4h | Background, general knowledge |
| `creative` | 72h | Analogies, novel approaches, lateral thinking |
| `empathetic` | 1h | Team dynamics, relationships, communication |
| `critical` | 8h | Risks, failures, edge cases, assumptions |
| `strategic` | 7d | Goals, roadmaps, long-term planning |

Shorter TTLs force more frequent re-embedding of high-churn knowledge; longer TTLs persist stable decisions without redundant cache misses.

---

## How It Works

### Agent Identity

When an agent calls `brain.orient`, Orion creates or retrieves a persistent identity. The same agent reconnecting after months gets the same identity with all accumulated expertise. The model can change — the brain persists.

### Model Switch Continuity

When an agent reconnects with a different model, Orion detects the switch, assesses continuity, and generates a transition brief:

> "You are taking over from claude-opus-4-5. This agent has operated in this Galaxy for 47 sessions. Here are recent decisions, expertise, and open threads."

### Confidence & Knowledge Quality

Orion actively tracks how trustworthy every piece of knowledge is and evolves it over time:

| Event | Confidence change |
|---|---|
| Agent uses record in session (via `brain.calibrate`) | +0.02 (capped at 1.0) |
| Record retrieved but never used | −0.005 |
| Weekly audit: stale > 30 days | −5% |
| Weekly audit: stale > 90 days | −15% |
| Contradiction resolved (winner) | +0.05 |
| Contradiction resolved (loser) | marked `valid_until = now` |
| Cache promotion to PLANET gravity | requires access ≥ 3 + confidence ≥ 0.7 + reinforcement ≥ 2 |

Agent quality scores are updated via exponential moving average (α = 0.1) based on calibration feedback, so retrieval improves the more an agent uses the system.

### Knowledge Gravity

Gravity controls the scope of a knowledge record:

- **BIOME** — relevant only to the current project context (temporary working memory)
- **PLANET** — relevant to the whole domain (Engineering, Product, etc.)
- **GALAXY** — universal facts that always appear in context bundles

Records can be promoted automatically from BIOME → PLANET by the weekly audit when they prove consistently useful.

### Auto-Routing

Every write goes through a routing engine that decides which Planet and Biome it belongs in. You never have to specify a planet — the engine figures it out.

**Routing priority (for writes):**

1. **Caller context** — if an agent is operating in a Planet, writes default there (confidence 0.85). The engine only overrides at ≥0.90 confidence to a *different* Planet, meaning the content is unambiguously wrong for the current context.
2. **Graphify** — semantic cluster analysis on longer content and code files (≥0.75 confidence).
3. **Entity routing** — existing entities in the knowledge graph vote for the Planet where they appear most (≥0.70 confidence).
4. **Keyword match** — Planet name or description overlap in content (≥0.55 confidence).
5. **Semantic neighbor** — embeds the content and finds the most similar existing stardust across all non-inbox Planets (≥0.40 confidence).
6. **Inbox** — true last resort, for when the Galaxy is empty or content genuinely matches nothing.

Every write receipt includes `routing_method` and `routing_reasoning` so agents can see what happened.

### Retrieval (RRF Fusion)

Search results are ranked using Reciprocal Rank Fusion across three signals:

```
score = Σ 1 / (60 + rank)  fused across:
  • semantic similarity    (Chroma vector query)
  • recency                (similarity × 1/(1 + days_since_created))
  • confidence             (similarity × confidence_score)
```

This means a recently-written, high-confidence record ranks ahead of an older, semantically similar one — even if the old record has a slightly higher cosine similarity.

### Knowledge Graph

Entities and relationships build automatically from every `brain.think`. The graph supports:
- Neighborhood traversal with relationship type filtering
- BFS shortest path (max 6 hops, results cached 1h)
- Hub detection by degree centrality
- Transitive relationship inference (`A USES B + B DEPENDS_ON C → A INDIRECTLY_DEPENDS_ON C`)
- Unlinked mention detection (entities that appear in content but lack explicit graph links)

### Weekly Audit

Runs automatically (Sunday 2 AM) or manually via `orion audit --run`:

1. **Deduplication** — merges records with >95% cosine similarity, keeping the higher-scored version
2. **Contradiction detection** — flags records with 70–90% similarity that contain negation patterns; classifies as TEMPORAL, CONTEXTUAL, or FACTUAL
3. **Transitive relationship inference** — composes multi-hop entity relationships
4. **Confidence decay** — applies decay to stale records (>30d or >90d without access)
5. **Cache promotion** — elevates frequently-used BIOME-gravity records to PLANET gravity
6. **Biome lifecycle** — advances biomes based on stardust count and last-active timestamp
7. **Galaxy strength recomputation** — updates the 5-dimension (volume, density, health, diversity, coverage) strength score

---

## Multi-User

Orion supports multiple users in a single Galaxy.

### Invite a team member

```bash
# Owner/admin creates an invite scoped to a Planet
POST /api/v1/galaxy/invite
{ "planet_id": "<planet-id>", "role": "member" }
# Returns a one-time invite token (expires in 7 days)

# New user joins with the token
POST /api/v1/galaxy/join
{ "invite_token": "<token>", "email": "...", "name": "...", "password": "..." }
```

### Roles

| Role | Access |
|------|--------|
| **owner** | All Planets, read/write, full Sun control |
| **admin** | All Planets, read/write |
| **member** | Assigned Planet only, read/write |
| **viewer** | Assigned Planet only, read-only |

Fine-grained overrides via `PlanetAccessGrant` (per-planet, per-user, with optional expiry). Every permission check is logged to an audit table.

### Galaxy Merge

Two established Galaxies can merge into one:

```
POST /api/v1/galaxy/merge/propose     → propose merge
POST /api/v1/galaxy/merge/{id}/accept → accept
POST /api/v1/galaxy/merge/{id}/execute → execute
```

The merge negotiates Sun sections, reconciles duplicate entities, and migrates all data.

---

## Authentication

**Local development (default):** Auth is bypassed. Set `ORION_AUTH_DISABLED=true` in `.env` for zero-friction single-user mode.

**Multi-user / production:** Tokens are PBKDF2-HMAC-SHA256 signed (100k iterations), stored as SHA256 hashes in the database, with a 7-day lifetime.

```bash
# Register (creates user + Galaxy)
POST /api/v1/auth/register { "email": "...", "password": "...", "name": "..." }

# Login
POST /api/v1/auth/login { "email": "...", "password": "..." }
# Returns: { "token": "...", "user_id": "...", ... }

# Use token in all requests
Authorization: Bearer <token>

# For MCP server, set the environment variable:
ORION_TOKEN=<token>
```

---

## CLI

```bash
pip install -e ./backend

# Lifecycle
orion start [--detach] [--build]    # boot services, open TUI
orion stop                          # shut down
orion status                        # galaxy status + service health

# Memory
orion memory write "content" -p Engineering
orion memory search "query" [-p planet] [-n limit]
orion memory import ~/path/to/notes/   # auto-detects Obsidian, CLAUDE.md, plain markdown
orion memory status

# Brain (inspect agent state)
orion brain status <agent-name>
orion brain health <agent-name>
orion brain expertise <agent-name>
orion brain sessions <agent-name>
orion brain switches <agent-name>    # model transition history

# Knowledge graph
orion graph query <entity> [-d depth]
orion graph path <entity-a> <entity-b>
orion graph hubs [-n limit]
orion graph unlinked                 # entities with unlinked mentions

# Sun
orion sun show
orion sun read [-s section]
orion sun edit working-context

# Planets & Biomes
orion planet list
orion planet create <name>
orion biome list --planet <name>
orion biome lifecycle <biome-id> MATURE

# Stardust
orion stardust list <biome-id>
orion stardust get <stardust-id>

# Other
orion init                          # create Galaxy (onboarding wizard)
orion audit [--run]                 # view/trigger weekly audit
orion connect claude                # MCP connection instructions
```

All commands support `--json` for scripting.

### TUI Keybindings

`G` Galaxy · `S` Search · `D` Dashboard · `U` Sun · `B` Brain · `N` New stardust · `?` Help · `Q` Quit

---

## Configuration

All config via `.env`. Defaults work with zero changes for local use.

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `ollama` | `ollama` (local, free) or `google` |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `LLM_PROVIDER` | `ollama` | `ollama`, `anthropic`, `openai`, or `google` |
| `LLM_MODEL` | `llama3` | LLM model name |
| `ORION_AUTH_DISABLED` | `true` | Set `false` for multi-user mode |
| `ORION_LOCAL_TOKEN` | — | Optional static bearer token for API access |
| `ORION_API_URL` | `http://localhost:8000` | Backend URL (used by MCP server) |
| `POSTGRES_PASSWORD` | `orion_dev` | PostgreSQL password (Docker) |
| `GOOGLE_API_KEY` | — | For Google text-embedding-004 |
| `ANTHROPIC_API_KEY` | — | For Anthropic Claude LLM |
| `OPENAI_API_KEY` | — | For OpenAI GPT LLM |

### Running the MCP server standalone

The MCP server can run independently, pointing to any Orion backend:

```bash
cd mcp
pip install .
ORION_API_URL=http://your-orion-server:8000 orion-mcp
```

### Local development without Docker

```bash
# Backend (requires PostgreSQL, or set DATABASE_URL=sqlite+aiosqlite:///./data/orion.db)
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# MCP server (separate terminal)
cd mcp
pip install -e .
orion-mcp

# Frontend
cd frontend
npm install && npm run dev
```

---

## Development

### Frontend conventions

- **Design tokens** live in `frontend/src/index.css` as CSS custom properties. This is the single source of truth for colors, spacing, and typography. `theme.ts` exists only for canvas/SVG rendering where CSS vars can't be used.
- **Shared components** in `frontend/src/components/ui/` — use `NavButton` for toolbar buttons, `Button` for actions, `Panel` for slide-in sidebars. Prefer these over inline Tailwind strings.
- **Accessibility** — all close buttons need `aria-label`. Slide-in panels use `useFocusTrap`. Animations respect `prefers-reduced-motion`. Target WCAG AA 4.5:1 contrast for text on `--bg`.
- **Real-time** — SSE events flow `Nebula stream → useNebulaStream → Zustand nebulaStore → components`. The canvas pulses and NebulaDrawer both read from the same store.

```bash
# Run backend tests
cd backend && pytest

# Run a specific test file
pytest tests/test_galaxy_merge.py

# Integration tests (requires running services)
SKIP_INTEGRATION=0 pytest tests/test_brain_integration.py

# Apply database migrations
cd backend && alembic upgrade head
```

### Tech Stack

**Backend:** Python 3.11+, FastAPI, SQLAlchemy (async + asyncpg), PostgreSQL, ChromaDB 0.5, Redis 7, APScheduler, Alembic (6 migrations), graphifyy  
**MCP Server:** Python 3.11+, FastMCP, httpx  
**Frontend:** React 18, Vite, TypeScript, Tailwind CSS 3, Zustand, TanStack Query, D3.js 7, Recharts  
**Infrastructure:** Docker Compose — 7 services (API, MCP, frontend, PostgreSQL, Redis, ChromaDB, Ollama)

---

## Import Formats

`orion memory import` auto-detects the source:

| Format | Detection | Behavior |
|--------|-----------|----------|
| **Obsidian** | `.obsidian/` directory | Parses `[[wikilinks]]` as entity relationships. Top-level folders become Planets, subfolders become Biomes. |
| **CLAUDE.md** | `CLAUDE.md` at root | Each rule → high-confidence Galaxy-gravity stardust |
| **GBrain** | Frontmatter with `cognitive_mode` | Maps cognitive metadata to stardust fields |
| **Plain** | Default | Markdown with YAML frontmatter, paragraph chunking (~500 token chunks) |

Files uploaded via the Inbox UI are parsed and routed automatically — each chunk goes to the Planet containing the most semantically similar existing content.

---

## API Reference

Full OpenAPI docs at `http://localhost:8000/docs` when running.

Key endpoint groups:

| Prefix | Description |
|--------|-------------|
| `/api/v1/auth` | Register, login, logout, profile, API key |
| `/api/v1/brain` | Orient, think, recall, calibrate, health, know, graph query, find path, context, write, entity get, status |
| `/api/v1/galaxy` | Galaxy status, strength, Sun, invite, join |
| `/api/v1/planets` | Planet CRUD |
| `/api/v1/biomes` | Biome CRUD, lifecycle management, graph, entities |
| `/api/v1/stardust` | Knowledge record CRUD, quick-capture |
| `/api/v1/search` | Semantic search with RRF fusion |
| `/api/v1/entities` | Entity lookup and profiles |
| `/api/v1/graph` | Neighborhood, paths, hubs, unlinked mentions, full graph |
| `/api/v1/contradictions` | List, resolve, dismiss |
| `/api/v1/agents` | Agent identities, expertise, sessions, health, model switches |
| `/api/v1/sun` | Read, update, working context, evolution log, lessons |
| `/api/v1/nebula` | Activity log, SSE stream, dashboard |
| `/api/v1/synthesize` | Knowledge synthesis with LLM |
| `/api/v1/ask` | Natural language knowledge queries |
| `/api/v1/onboarding` | Galaxy creation, import, templates |
| `/api/v1/inbox` | File upload and ingestion history |
| `/api/v1/routing` | Routing log, manual re-routing, accuracy stats |
| `/api/v1/admin` | Active agents, planet health, bridges, strength history (owner/admin only) |
| `/api/v1/model-profiles` | LLM model profile CRUD |
| `/api/v1/cache` | Cache TTL config and stats |

---
