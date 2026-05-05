# Orion — Persistent Memory & Brain for AI Agents

https://orion-six-chi.vercel.app/

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

Open `http://localhost:3000` and complete the onboarding wizard (6 steps, all skippable):

1. **Role** — your role determines the default Planet structure
2. **Import source** — local folder, Obsidian vault, Git repo, or start empty
3. **Name your first Biome** — name your first project context
4. **About you** — name, communication style, current goal
5. **Steering document** — import a CLAUDE.md or custom agent rules file
6. **Tools & preferences** — technologies you use, contradiction handling

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

Orion is three independent services that communicate over HTTP:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend    │     │  MCP Server │     │  REST API   │
│  :3000      │────▶│  :8787      │────▶│  :8000      │
│  React UI   │     │  20 tools   │     │  97 endpoints│
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          │                    │                    │
                    ┌─────┴─────┐      ┌──────┴──────┐     ┌──────┴──────┐
                    │ PostgreSQL│      │    Redis    │     │  ChromaDB   │
                    │  :5432    │      │   :6379    │     │  (vectors)  │
                    └───────────┘      └────────────┘     └─────────────┘
```

**The MCP server is a standalone HTTP client of the REST API.** It has zero direct dependencies on the backend — it only needs the API URL. This means:

- All Orion features work through the REST API alone, without MCP
- The MCP server can run anywhere — locally, at the edge, or as a hosted service
- AI tool extensions are thin wrappers around the MCP package

### Services

| URL | Service | Description |
|-----|---------|-------------|
| `http://localhost:3000` | Frontend | Galaxy visualization, knowledge graph, agent panels |
| `http://localhost:8000` | REST API | 97 endpoints, OpenAPI docs at `/docs` |
| `http://localhost:8787` | MCP Server | 20 tools for AI agents |

### Project Structure

```
orion/
├── backend/     # FastAPI REST API — models, services, database
├── frontend/    # React UI — Galaxy Canvas, knowledge graph, dashboards
│   └── src/
│       ├── views/        # Page-level components (GalaxyView, DashboardView, etc.)
│       ├── components/   # Feature components (galaxy/, search/, inbox/, ui/)
│       │   └── ui/       # Shared design system: Button, NavButton, Panel, Input, Pill, Tooltip
│       ├── hooks/        # Custom hooks (useFocusTrap, useNebulaStream)
│       ├── api/          # API client and react-query hooks
│       └── index.css     # Design tokens (CSS custom properties — single source of truth)
├── mcp/         # Standalone MCP server — calls backend via HTTP
└── docker-compose.yml
```

---

## MCP Tools (what your AI agent can use)

**Memory tools** — for any AI tool, zero config:

| Tool | What it does |
|------|-------------|
| `memory.write` | Store knowledge. Auto-routes to the right Planet if not specified. |
| `memory.search` | Semantic search across your Galaxy. |
| `memory.context` | Structured context bundle sized to a token budget. |
| `memory.status` | Galaxy health, planets, biomes, strength score. |
| `memory.entity_get` | Entity profile with relationships and timeline. |

**Brain tools** — for agents with persistent identity:

| Tool | What it does |
|------|-------------|
| `brain.orient` | Call at session start. Returns identity, context, knowledge state, protocol. Detects model switches. |
| `brain.think` | Store understanding with auto-routing, contradiction detection, relationship extraction, expertise tracking. |
| `brain.recall` | Graph-enhanced retrieval weighted by cognitive context. |
| `brain.ask` | Natural language questions about your Galaxy's knowledge ("Who knows about auth?", "What decisions were made about the database?"). |
| `brain.synthesize` | Synthesized understanding of a topic with confidence and open questions. |
| `brain.calibrate` | End-of-session feedback. Teaches the brain what was useful. |
| `brain.health` | Cognitive health: freshness, coverage gaps, stale beliefs. |
| `brain.know` | Quick concept lookup with graph neighborhood. |
| `brain.graph_query` | Traverse the knowledge graph from an entity. |
| `brain.find_path` | Shortest path between two concepts. |
| `brain.graph_full` | Full knowledge graph — all entities and edges. |

**Sun tools** — Galaxy steering document:

| Tool | What it does |
|------|-------------|
| `sun.read` | Read the Sun (identity, values, agent protocol, working context, steering doc). |
| `sun.update` | Update a Sun section. Changes logged to evolution log. |
| `sun.working_context` | Quick-update current focus, blockers, decisions. |

**Session lifecycle:**

| Tool | What it does |
|------|-------------|
| `orion_session_end` | End the current session and return usage stats. |

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
  -d '{"agent_name": "my-agent", "model": "gpt-4"}'

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
├── Sun (steering document — identity, values, agent protocol, working context, steering doc)
├── Agent Identities (persistent AI agents with expertise profiles)
├── Knowledge Graph (typed entity relationships)
└── Planets (knowledge domains — Engineering, Personal, Research)
    └── Biomes (project contexts — "Orion Backend", "Auth Refactor")
        ├── Stardust (atomic knowledge records with confidence + reasoning)
        └── Entities (people, tools, concepts — auto-extracted)
```

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

### Galaxy Merge

Two established Galaxies can merge into one:

```
POST /api/v1/galaxy/merge/propose     → propose merge
POST /api/v1/galaxy/merge/{id}/accept → accept
POST /api/v1/galaxy/merge/{id}/execute → execute
```

The merge negotiates Sun sections, reconciles duplicate entities, creates Gravity Bridges between Planets, and migrates all data.

---

## Authentication

**Local development (default):** Auth is bypassed. Set `ORION_AUTH_DISABLED=true` in `.env` for zero-friction single-user mode.

**Multi-user / production:** Auth is JWT-based.

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
orion tui                           # TUI dashboard

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
orion brain switches <agent-name>

# Knowledge graph
orion graph query <entity> [-d depth]
orion graph path <entity-a> <entity-b>
orion graph hubs [-n limit]

# Sun
orion sun show
orion sun read [-s section]
orion sun edit working-context

# Other
orion init                          # create Galaxy (onboarding wizard)
orion audit [--run]                 # view/trigger weekly audit
orion connect claude                # MCP connection instructions
```

### TUI Keybindings

`G` Galaxy · `S` Search · `D` Dashboard · `U` Sun · `B` Brain · `N` New stardust · `?` Help · `Q` Quit

---

## Configuration

All config via `.env`. Defaults work with zero changes for local use.

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `ollama` | `ollama` (local, free) or `google` |
| `LLM_PROVIDER` | `ollama` | `ollama`, `anthropic`, or `openai` |
| `ORION_AUTH_DISABLED` | `false` | Set `true` for local single-user (no login required) |
| `ORION_LOCAL_TOKEN` | — | Optional bearer token for API access |
| `ORION_API_URL` | `http://localhost:8000` | Backend URL (used by MCP server) |
| `POSTGRES_PASSWORD` | `orion_dev` | PostgreSQL password (Docker) |
| `GOOGLE_API_KEY` | — | For Google embeddings |
| `ANTHROPIC_API_KEY` | — | For Anthropic LLM |
| `OPENAI_API_KEY` | — | For OpenAI LLM |

### Running the MCP server standalone

The MCP server can run independently, pointing to any Orion backend:

```bash
cd mcp
pip install .
ORION_API_URL=http://your-orion-server:8000 orion-mcp
```

### Local development without Docker

```bash
# Backend (uses SQLite by default)
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

```bash
# Run backend tests (576 tests, ~7s)
cd backend && pytest

# Run a specific test file
pytest tests/test_galaxy_merge.py

# Integration tests (requires running services)
SKIP_INTEGRATION=0 pytest tests/test_brain_integration.py

# Apply database migrations
cd backend && alembic upgrade head
```

### Tech Stack

**Backend:** Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL / SQLite, ChromaDB, Redis 7, APScheduler, Alembic (2 migrations)
**MCP Server:** Python 3.12, FastMCP, httpx (HTTP client to backend)
**Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Zustand, TanStack Query, D3.js
**Infrastructure:** Docker Compose — 7 services (API, MCP, frontend, PostgreSQL, Redis, ChromaDB, Ollama)

---

## How It Works

### Agent Identity

When an agent calls `brain.orient`, Orion creates or retrieves a persistent identity. The same agent reconnecting after months gets the same identity with all accumulated expertise. The model can change — the brain persists.

### Model Switch Continuity

When an agent reconnects with a different model, Orion detects the switch, assesses continuity, and generates a transition brief:

> "You are taking over from claude-opus-4-5. This agent has operated in this Galaxy for 47 sessions. Here are recent decisions, expertise, and open threads."

### Knowledge Graph

Entities and relationships build automatically from every `brain.think`. The graph supports neighborhood traversal, path finding, hub detection, and transitive inference.

### Weekly Audit

Runs automatically (Sunday 2 AM) or manually via `orion audit --run`:
- Deduplication (>95% cosine similarity)
- Contradiction detection and classification
- Confidence decay on stale records
- Transitive relationship inference
- Biome lifecycle management

### Weekly Digest

Sends a weekly summary (Monday 8 AM) with activity metrics to users who have it enabled.

---

## Import Formats

`orion memory import` auto-detects the source:

| Format | Detection | Behavior |
|--------|-----------|----------|
| **Obsidian** | `.obsidian/` directory | Parses `[[wikilinks]]` as entity relationships |
| **CLAUDE.md** | `CLAUDE.md` at root | Each rule → high-confidence Galaxy-gravity stardust |
| **GBrain** | Frontmatter with `cognitive_mode` | Maps cognitive metadata to stardust fields |
| **Plain** | Default | Markdown with YAML frontmatter, paragraph chunking |

---

## API Reference

Full OpenAPI docs at `http://localhost:8000/docs` when running.

Key endpoint groups:

| Prefix | Endpoints | Description |
|--------|-----------|-------------|
| `/api/v1/auth` | 4 | Register, login, logout, profile |
| `/api/v1/brain` | 12 | Orient, think, recall, calibrate, health, know, graph query, find path, context, write, entity get, status |
| `/api/v1/galaxy` | 13 | Galaxy status, Sun, strength, invite, join, merge |
| `/api/v1/planets` | 5 | CRUD, protocol overrides |
| `/api/v1/biomes` | 6 | CRUD, lifecycle management |
| `/api/v1/stardust` | 3 | Knowledge records |
| `/api/v1/agents` | 5 | Agent identities, expertise, sessions, health |
| `/api/v1/graph` | 6 | Neighborhood, paths, hubs, unlinked mentions |
| `/api/v1/admin` | 5 | Active agents, planet health, contradictions, bridges, strength (owner/admin only) |
| `/api/v1/ask` | 1 | Natural language knowledge queries |
| `/api/v1/search` | 1 | Semantic search |
| `/api/v1/synthesize` | 2 | Knowledge synthesis |

---
