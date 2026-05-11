# Release Preparation

## Features to Remove

### Galaxy Merging
- Remove `backend/app/services/merge_service.py`
- Remove `backend/app/api/` merge-related routes
- Remove any frontend UI that exposes merge actions (MergePanel component)
- Remove `GravityBridge` model usage tied to merge flows (keep model if used elsewhere, otherwise drop)

### Dashboard (Nebula)
- Remove `backend/app/api/nebula.py` dashboard endpoint (`GET /api/v1/nebula/dashboard`)
- Remove nebula log/stream endpoints if the dashboard is the only consumer — or keep stream for internal use and just hide UI
- Remove `NebulaDrawer` / dashboard UI in frontend
- Remove `useNebulaStream` hook if the only purpose was powering the dashboard
- Keep `nebula_service.log_event(...)` calls in backend — those interaction logs are used by other services

---

## Bug Fixes — Priority Order

### P0 — Fix Before Any Release (Security)

- [ ] **C2 — Unauthenticated onboarding endpoints**
  `backend/app/api/onboarding.py` lines 134, 453, 470
  Add `Depends(get_current_user)` to `/onboarding/start`, `/onboarding/import`, `/onboarding/import-files`.

- [ ] **C3 — Unauthenticated SSE stream leaks activity**
  `backend/app/api/nebula.py:164`
  Add auth dependency to `nebula_stream`. (May become moot if dashboard is removed — verify.)

- [ ] **C1 — Arbitrary file read via `reimport_steering_doc`**
  `backend/app/services/sun_service.py:326`
  Validate `resolved.startswith(allowed_prefix)` (e.g. `/vault` or `/app/content`) before opening.

- [ ] **H1 — IDOR on stardust GET/PUT**
  `backend/app/api/stardust.py` lines 85, 96
  Add `Depends(get_galaxy_for_user)` and assert `stardust.galaxy_id == galaxy.id`.

- [ ] **H2 — IDOR on biome endpoints (unauthenticated)**
  `backend/app/api/biomes.py` lines 72-112, `stardust.py` lines 72-76
  Add auth + galaxy scoping to `GET /biomes/{id}/stardust`, `/biomes/{id}/graph`, `/biomes/{id}/entities`.

- [ ] **B1 — IDOR on `GET /contradictions/{id}` — no auth or galaxy scoping**
  `backend/app/api/contradictions.py:30`
  Add `galaxy: Galaxy = Depends(get_galaxy_for_user)` and assert `c.galaxy_id == galaxy.id`. The `/resolve` endpoint on the same resource already scopes correctly; the read endpoint does not.

- [ ] **H3 — Role injection on Galaxy invite**
  `backend/app/api/galaxy.py` lines 79-82
  Validate `InviteRequest.role` against `Literal["member", "viewer"]`.

- [ ] **H7 — Registration race condition — duplicate owners**
  `backend/app/auth/router.py` lines 62-68
  Make the owner-check + insert atomic with `SELECT ... FOR UPDATE` or a unique DB constraint.

- [ ] **H8 — API exposed on 0.0.0.0 with auth disabled by default**
  `docker-compose.yml:14`
  Change `"8000:8000"` to `"127.0.0.1:8000:8000"`.

- [ ] **H9 — Frontend exposed on all interfaces**
  `docker-compose.yml:42`
  Change `"3000:3000"` to `"127.0.0.1:3000:3000"`.

- [ ] **M2 — MCP server binds to `0.0.0.0` with no authentication**
  `mcp/orion_mcp/server.py:22`
  Default to `host="127.0.0.1"`; require `API_TOKEN` to be set before starting. Any host on the local network can currently invoke `stardust.delete`, `memory.write`, and `sun.update`.

- [ ] **Bug 19 — Galaxy join invite race condition**
  `backend/app/api/galaxy.py` lines 95-110
  Make invite token lookup + mark-used atomic (row-level lock or optimistic update).

- [ ] **Arch 6 — Frontend sends no auth tokens**
  `frontend/src/api/client.ts`
  Wire up auth token from storage into `Authorization` header. (Blocking if auth is ever enabled.)

---

### P1 — Fix Before Stable (Data Integrity & Correctness)

- [ ] **H4 — Audit lock is per-process (multi-worker corruption)**
  `backend/app/services/audit_service.py:12`
  Replace `asyncio.Lock()` with a database advisory lock or Redis distributed lock.

- [ ] **H5 — O(N²) co-chunk pairs — OOM on large imports**
  `backend/app/services/import_service.py:383-386`
  Cap pairs per file or switch to a sampled/windowed approach.

- [ ] **H6 — Wikilink Cartesian product explosion**
  `backend/app/services/import_service.py:245-255`
  Cap edges per wikilink reference (e.g. top-k by relevance score, not all×all).

- [ ] **Bug 2 — `_check_contradiction` embeds on every write (O(N) embedding calls)**
  `backend/app/services/stardust_service.py:50-75`
  Cache embeddings in Redis alongside content; use stored vectors for comparison.

- [ ] **B2 — `context_service` JSON parse crashes on malformed SunSection content**
  `backend/app/services/context_service.py:46`
  Wrap `json.loads(s.content)` in `try/except json.JSONDecodeError` and fall back to `{}`. A single corrupted record currently crashes the entire context fetch for that galaxy.

- [ ] **M1 — `_create_task` silently drops session lifecycle events**
  `mcp/orion_mcp/session.py:14-20`
  When called with no running event loop, `SESSION_START` / `SESSION_END` events are silently discarded with no warning. Log a `WARNING` instead of `pass`, or use `asyncio.run()` as a fallback.

- [ ] **Bug 3 — InboxView upload index bug (wrong item updated)**
  `frontend/src/views/InboxView.tsx:30-36`
  Match by file reference (`u.file === file`) instead of array index `idx`.

- [ ] **Bug 6 — LIKE wildcard injection in fulltext fallback**
  `backend/app/services/search_service.py:130-140`
  Escape `%` and `_` in query terms before passing to `ilike()`.

- [ ] **Bug 9 — Redis `KEYS` blocks server**
  `backend/app/services/stardust_service.py:212`
  Replace `redis.keys(...)` with `SCAN` async iteration.

- [ ] **Bug 10 — N+1 Redis calls in `get_all_cached_stardust`**
  `backend/app/storage/redis_client.py:52-57`
  Use `MGET` instead of individual `GET` per stardust ID.

- [ ] **Bug 16 — Agents API returns 200 with error body**
  `backend/app/api/agents.py`
  Raise `HTTPException(404)` instead of returning `{"error": ...}` with status 200.

- [ ] **Bug 17 — `graph/rebuild-edges` is O(N²) with no rate limit**
  `backend/app/api/graph.py:107-170`
  Delegate to a background task; add a per-galaxy rate limit / lock.

- [ ] **Bug 18 — Inbox upload: sync 10MB processing, no rate limit**
  `backend/app/api/inbox.py:62-63`
  Delegate to background task; add per-user upload rate limiting.

- [ ] **Bug 20 — Signal detector counts substrings, not words**
  `backend/app/extraction/signal_detector.py:10-25`
  Use word-boundary regex (`\b`) instead of `str.count`.

- [ ] **F1 — OnboardingView keyboard handler fires inside inputs**
  `frontend/src/views/OnboardingView.tsx:155-161`
  Check `e.target instanceof HTMLInputElement` before handling navigation keys.

- [ ] **F2 — Stale closure in OnboardingView — submits stale data**
  `frontend/src/views/OnboardingView.tsx:155-161`
  Add `handleFinish` (and its deps) to the `useEffect` dependency array.

- [ ] **F3 — 7 components silently swallow errors**
  `CreatePlanetModal, DetailView, StardustDetail, SunPanel, KnowledgeGraphView, SunView, InboxView`
  Show user-facing error toasts; in SunView, don't reset edit state before the mutation resolves.

- [ ] **F5 — D3 graph rebuilt on every keystroke**
  `frontend/src/views/KnowledgeGraphView.tsx:72-145`
  Debounce `searchQuery` (300ms) before passing it to the D3 `useEffect`.

- [ ] **Arch 3 — `embed_batch` is sequential for Ollama**
  `backend/app/storage/embedding_router.py:31`
  Replace list comprehension with `asyncio.gather` + concurrency semaphore.

- [ ] **Arch 11 — Owner recovery token stored in plaintext**
  `backend/app/config.py:28`
  Hash the token before comparing; never log or expose raw value.

---

### P2 — Quality of Life (Polish Before Release)

- [ ] **B3 — `resolution_type` accepts arbitrary strings**
  `backend/app/api/contradictions.py:13`
  Use `Literal["a_supersedes_b", "b_supersedes_a", "coexist", "synthesize"]` instead of bare `str`.

- [ ] **F-Search — `SearchModal` stateful regex breaks multi-match highlighting**
  `frontend/src/components/search/SearchModal.tsx:51`
  `RegExp.test()` with the `g` flag advances `lastIndex`, causing alternating parts to be misclassified. Replace `re.test(part)` with `new RegExp(re.source, 'i').test(part)`.

- [ ] **F-Onboard — Step buttons allow skipping validation**
  `frontend/src/views/OnboardingView.tsx:174-182`
  Users can click any step indicator and jump forward, bypassing required fields. Disable steps ahead of the current validated step.

- [ ] **Bug 4 — `confidence_decay` resets `last_accessed`**
  `backend/app/services/audit_service.py:200-210`
  Add a separate `last_decayed_at` column instead of stomping `last_accessed`.

- [ ] **Bug 11 — ChromaDB URL parsing breaks with HTTPS / paths**
  `backend/app/storage/chroma_client.py:14-15`
  Use `urllib.parse.urlparse` instead of manual string splitting.

- [ ] **Bug 12 — MCP client race condition on close**
  `mcp/orion_mcp/client.py:14-20`
  Guard `_get_client()` with a lock so the closed→None transition is atomic.

- [ ] **Bug 13 — No content-length limit on `memory.write`**
  `mcp/orion_mcp/server.py:37-42`
  Add a max-length check (e.g. 50KB) before writing.

- [ ] **Bug 14 — Confidence not validated (0.0–1.0 range)**
  `mcp/orion_mcp/server.py:72-76`
  Clamp or reject confidence values outside [0.0, 1.0].

- [ ] **Bug 21 — Relationship extractor regex explosion with many entities**
  `backend/app/extraction/relationship_extractor.py:55-60`
  Compile patterns once per entity batch; cap alternation size or split into chunks.

- [ ] **Bug 22 — Decision regex can catastrophically backtrack**
  `backend/app/extraction/patterns.py:18`
  Add atomic grouping or possessive quantifiers; test with long lines lacking periods.

- [ ] **Bug 23 — MCP session tracker race on concurrent agent starts**
  `mcp/orion_mcp/session.py:47-55`
  Use a lock around `_find_by_agent()` + `touch()` to prevent duplicate session creation.

- [ ] **Bug 24 — Permission denial reveals user role**
  `backend/app/auth/permissions.py:42`
  Return a generic "Access denied" message without including the role.

- [ ] **Bug 25 — Onboarding path error reveals filesystem structure**
  `backend/app/api/onboarding.py:261`
  Return a generic "Invalid path" message instead of echoing the path back.

- [ ] **B6 — `search_service` `valid_from` parsing can throw `ValueError`**
  `backend/app/services/search_service.py`
  Wrap `datetime.fromisoformat(meta["valid_from"])` in `try/except ValueError` with a fallback.

- [ ] **M3 — `brain.diff` not tracked in session stats**
  `mcp/orion_mcp/session.py:140-149`
  Add `"brain.diff"` to `_READ_TOOLS`; it currently never increments read/write counters.

- [ ] **M4 — Session logging failures swallowed at DEBUG level**
  `mcp/orion_mcp/session.py:120-121, 136-137`
  Upgrade `logger.debug()` to `logger.warning()` for session lifecycle failures so they're visible in production.

- [ ] **M5 — MCP health endpoint always returns 200**
  `mcp/orion_mcp/server.py:375-378`
  Probe the backend `GET /health` and return 503 if unreachable, so load balancers can route correctly.

- [ ] **F4 — 4 modals missing focus trapping**
  `SearchModal, SynthesisPanel, AskBar, CreatePlanetModal`
  Add `useFocusTrap` (already used in MergePanel, ContradictionPanel, AgentPanel).

- [ ] **F6 — GalaxyCanvas agent health fetch leaks on unmount**
  `frontend/src/components/galaxy/GalaxyCanvas.tsx:52-60`
  Add `AbortController`; cancel in-flight requests on unmount.

- [ ] **F7 — SettingsView has no loading/error state**
  `frontend/src/views/SettingsView.tsx:10-12`
  Show a spinner while loading and an error message on failure.

- [ ] **F8 — Icon-only close buttons missing `aria-label`**
  `NebulaDrawer, SunPanel, AgentPanel`
  Add `aria-label="Close"` to SVG X buttons.

- [ ] **Arch 4 — ChromaDB port mismatch between docker-compose and config default**
  `docker-compose.yml` vs `backend/app/config.py`
  Align config default (`8001`) with ChromaDB's actual default (`8000`), or document explicitly.

- [ ] **Arch 9 — Backend Dockerfile installs dev deps in production**
  `backend/Dockerfile:5`
  Change `pip install -e ".[dev]"` to `pip install .`.

- [ ] **Arch 10 — MCP server runs as root**
  `mcp/Dockerfile`
  Add a non-root user and `USER` directive.

- [ ] **Arch 12 — API keys in plain env vars in docker-compose**
  `docker-compose.yml:23-25`
  Document use of Docker secrets or a `.env` file excluded from version control.

---

### P3 — Low Priority / Cleanup

- [ ] **B4 — `EntityExtractor` doesn't deduplicate entities across types**
  `backend/app/extraction/entity_extractor.py`
  Dedup key is `(name.lower(), entity_type)` — the same real-world entity can produce two graph nodes if extracted under different types. Consider using `name.lower()` alone as the key.

- [ ] **B5 — `get_or_create_inbox_planet` race condition**
  `backend/app/api/inbox.py`
  Two concurrent uploads can both pass the existence check and insert duplicate inbox planets. Add a unique constraint on `(galaxy_id, name)` or use `INSERT ... ON CONFLICT DO NOTHING`.

- [ ] **B7 — Token estimation uses flat 4-chars-per-token ratio**
  `backend/app/services/context_service.py:18`
  Modern tokenizers vary 2–5 chars/token; at extremes this makes context budgets off by 2×.

- [ ] **B8 — `_infer_family()` is order-dependent for ambiguous model names**
  `backend/app/services/agent_identity_service.py:129`
  A model named `"claude-gpt-hybrid"` returns `"claude"` because it appears first in the loop. No warning is emitted.

- [ ] **B9 — `biome.cache_ttl_seconds` has no bounds validation**
  Clamp to `[60, 2592000]` in the biome create/update endpoint; `0` or `-1` causes undefined cache behavior.

- [ ] **Bug 1 — Rate limiter in-memory dict has no lock**
  `backend/app/main.py:50-63`
  Acceptable risk for a single-worker local app; migrate to Redis-backed limiter for multi-worker.

- [ ] **Bug 5 — `context_tags` JSON deserialization dual-path (dead prod code)**
  `backend/app/models/stardust.py:35-44`
  Acceptable as-is; document the SQLite test / Postgres prod divergence.

- [ ] **Bug 8 — `_session_prune_loop` uses deferred import**
  `backend/app/main.py:73-82`
  Low risk; refactor the import to top-level when touching that file for another reason.

- [ ] **Bug 15 — `stardust.delete` confirm check is MCP-only**
  `mcp/orion_mcp/server.py:195-199`
  Add matching confirm guard to the REST endpoint, or document the asymmetry.

- [ ] **Arch 1 — No Alembic migrations for brain models**
  `backend/alembic/versions/`
  Audit which tables are Alembic-managed vs `create_all()`; unify under Alembic.

- [ ] **Arch 2 — Unbounded SSE reconnect with no backoff**
  `frontend/src/hooks/useNebulaStream.ts`
  Add exponential backoff (may become moot if dashboard is removed).

- [ ] **Arch 5 — `get_settings()` lru_cache never invalidated**
  `backend/app/config.py`
  Non-issue in production; document `get_settings.cache_clear()` for test setup.

- [ ] **Arch 7 — Redis has no authentication**
  `docker-compose.yml:60-66`
  Acceptable for a local-only deployment; add `--requirepass` if ever network-exposed.

- [ ] **Arch 8 — No TLS between services**
  `docker-compose.yml`
  Acceptable for localhost; required if ever deployed beyond a single machine.

- [ ] **Data integrity — Missing FK constraints (11 models)**
  `InteractionLog, Contradiction, SessionCalibration, Subagent, GravityBridge, StrengthHistory, SubagentSession, GraphPathCache, ModelSwitchLog, Stardust (contradiction_id), RoutingLog`
  Add FK constraints in a migration; won't break existing data.

- [ ] **Data integrity — 5 models use Integer for booleans**
  `TransitionOrientation.used, InteractionLog.cache_hit, InteractionLog.personal_data, Contradiction.human_reviewed, ModelProfile.is_builtin`
  Migrate columns to `Boolean` type.

- [ ] **Dead code — `REGION_REASONING_PROMPTS`, `_EPHEMERAL_SECRET`, `StardustRelationship`, `Subagent` model, `SubagentSession` model**
  Remove or document intent.
