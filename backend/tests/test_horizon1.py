"""Tests for Horizon 1 features — TDD: tests written before implementation."""
import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import text, insert
from sqlalchemy.ext.asyncio import AsyncSession

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import (
    Base, Galaxy, Planet, Biome, Stardust, Entity, Contradiction,
)
from app.models.brain import (
    AgentIdentity, AgentSession, AgentExpertise,
    StardustRelationship,
)
from app.models.nebula import InteractionLog


# ── Shared fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False,
                                 connect_args={"check_same_thread": False})
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def galaxy_env(db):
    """Seed a full galaxy environment for testing."""
    now = datetime.now(timezone.utc)
    galaxy = Galaxy(id=str(uuid4()), name="Test Galaxy", created_at=now,
                    strength_score=50.0, total_nodes=0, schema_version="0.1.0")
    db.add(galaxy)

    planet = Planet(id=str(uuid4()), galaxy_id=galaxy.id, name="Engineering",
                    stardust_count=0, health_status="healthy")
    db.add(planet)

    biome = Biome(id=str(uuid4()), planet_id=planet.id, galaxy_id=galaxy.id,
                  name="Backend", lifecycle_state="ACTIVE")
    db.add(biome)

    agent = AgentIdentity(
        id=str(uuid4()), galaxy_id=galaxy.id, agent_name="test-agent",
        agent_type="GENERAL", current_model="claude-sonnet-4-20250514",
        model_family="claude", birth_date=now, expertise_profile="{}",
    )
    db.add(agent)

    session = AgentSession(
        id=str(uuid4()), agent_identity_id=agent.id, galaxy_id=galaxy.id,
        model_used="claude-sonnet-4-20250514", started_at=now,
    )
    db.add(session)
    await db.commit()

    return {
        "galaxy": galaxy, "planet": planet, "biome": biome,
        "agent": agent, "session": session, "now": now,
    }


# ═══════════════════════════════════════════════════════════════════════════
# H1.1 — Session Summary Service
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionSummaryService:
    """Session summary generates after sessions with writes, shows correct stats."""

    @pytest.mark.asyncio
    async def test_summary_with_writes(self, db, galaxy_env):
        """Summary generated when session has at least one write."""
        env = galaxy_env
        sid = env["session"].id
        gid = env["galaxy"].id

        # Seed interaction_log with WRITE events
        for i in range(3):
            await db.execute(insert(InteractionLog).values(
                galaxy_id=gid, session_id=sid, action_type="WRITE",
                initiated_by="test-agent", record_id=str(uuid4()),
            ))
        await db.commit()

        from app.services.session_summary_service import session_summary_service
        summary = await session_summary_service.generate_summary(sid, gid, db)

        assert summary is not None
        assert summary.records_written == 3
        assert summary.agent_name == "test-agent"

    @pytest.mark.asyncio
    async def test_no_summary_when_zero_writes(self, db, galaxy_env):
        """No summary when session has zero writes."""
        env = galaxy_env
        sid = env["session"].id
        gid = env["galaxy"].id

        # Only READ events
        await db.execute(insert(InteractionLog).values(
            galaxy_id=gid, session_id=sid, action_type="READ",
            initiated_by="test-agent",
        ))
        await db.commit()

        from app.services.session_summary_service import session_summary_service
        summary = await session_summary_service.generate_summary(sid, gid, db)

        assert summary is None

    @pytest.mark.asyncio
    async def test_strength_delta(self, db, galaxy_env):
        """Summary shows correct galaxy strength before/after delta."""
        env = galaxy_env
        sid = env["session"].id
        gid = env["galaxy"].id

        # Set galaxy_strength_at_start on the session
        env["session"].galaxy_strength_at_start = 45.0
        await db.commit()

        # Seed a write
        await db.execute(insert(InteractionLog).values(
            galaxy_id=gid, session_id=sid, action_type="WRITE",
            initiated_by="test-agent", record_id=str(uuid4()),
        ))
        await db.commit()

        from app.services.session_summary_service import session_summary_service
        # Set galaxy strength_score directly (no longer calls compute_galaxy_strength)
        from sqlalchemy import update as sql_update
        from app.models import Galaxy
        await db.execute(sql_update(Galaxy).where(Galaxy.id == gid).values(strength_score=48.5))
        await db.commit()
        summary = await session_summary_service.generate_summary(sid, gid, db)

        assert summary.strength_before == 45.0
        assert summary.strength_after == 48.5
        assert summary.strength_delta == 3.5

    @pytest.mark.asyncio
    async def test_topic_extraction(self, db, galaxy_env):
        """Top topics extracted from context_tags of written stardust."""
        env = galaxy_env
        sid = env["session"].id
        gid = env["galaxy"].id
        biome_id = env["biome"].id
        planet_id = env["planet"].id

        # Create stardust with tags and link via interaction_log
        for tags in [["fastapi", "auth"], ["fastapi", "redis"], ["auth"]]:
            sd_id = str(uuid4())
            sd = Stardust(
                id=sd_id, biome_id=biome_id, planet_id=planet_id,
                galaxy_id=gid, content="test", region="contextual",
            )
            sd.context_tags = tags
            db.add(sd)
            await db.execute(insert(InteractionLog).values(
                galaxy_id=gid, session_id=sid, action_type="WRITE",
                initiated_by="test-agent", record_id=sd_id,
            ))
        await db.commit()

        from app.services.session_summary_service import session_summary_service
        summary = await session_summary_service.generate_summary(sid, gid, db)

        assert summary.top_topics[0] == "fastapi"  # most frequent
        assert "auth" in summary.top_topics

    @pytest.mark.asyncio
    async def test_nonexistent_session_returns_none(self, db, galaxy_env):
        """Nonexistent session ID returns None."""
        from app.services.session_summary_service import session_summary_service
        summary = await session_summary_service.generate_summary("fake-id", "fake-gid", db)
        assert summary is None

    @pytest.mark.asyncio
    async def test_galaxy_strength_at_start_column_exists(self, db, galaxy_env):
        """AgentSession model has galaxy_strength_at_start column."""
        env = galaxy_env
        env["session"].galaxy_strength_at_start = 72.3
        await db.commit()
        await db.refresh(env["session"])
        assert env["session"].galaxy_strength_at_start == 72.3


# ═══════════════════════════════════════════════════════════════════════════
# H1.3 — MCP Activity Indicator
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPActivityIndicator:
    """Status lines appear on correct tool responses, absent on others."""

    @pytest.mark.asyncio
    async def test_orient_has_status_line(self):
        """brain.orient response includes orion_status_line."""
        with patch("app.mcp.tools_brain._get_galaxy_id", return_value="gid"):
            from app.mcp.tools_brain import brain_orient
            with patch("app.mcp.tools_brain.async_session") as mock_sess:
                mock_db = AsyncMock()
                mock_sess.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_sess.return_value.__aexit__ = AsyncMock(return_value=False)

                with patch("app.services.agent_identity_service.agent_identity_service.get_or_create_identity") as mock_id:
                    mock_identity = MagicMock()
                    mock_identity.id = "aid"
                    mock_identity.agent_name = "test"
                    mock_identity.total_sessions = 0
                    mock_id.return_value = mock_identity

                    with patch("app.services.orientation_service.orientation_service.build_orientation") as mock_orient:
                        mock_orient.return_value = {
                            "session_id": "sid",
                            "orion_status_line": "[orion: 5 records · Backend · 73.4/100]",
                        }
                        result = await brain_orient("test", "claude-sonnet-4-20250514")

        # The orientation response should contain the status line
        orient_data = result.get("tool_result", result)
        assert "orion_status_line" in orient_data

    @pytest.mark.asyncio
    async def test_status_line_max_80_chars(self):
        """Status line must be ≤80 characters."""
        from app.services.session_summary_service import build_status_line
        line = build_status_line(
            records_retrieved=5,
            biome_name="A Very Long Biome Name That Exceeds Normal Length Expectations",
            galaxy_strength=73.4,
        )
        assert len(line) <= 80

    @pytest.mark.asyncio
    async def test_write_receipt_has_confirmation(self):
        """memory.write and brain.think receipts include orion_confirmation."""
        from app.services.session_summary_service import build_confirmation_line
        line = build_confirmation_line(
            biome_name="Backend",
            region="analytical",
            total_records_today=12,
        )
        assert "[orion:" in line
        assert "Backend" in line
        assert "12" in line


# ═══════════════════════════════════════════════════════════════════════════
# H1.2 — Structured Onboarding Interview
# ═══════════════════════════════════════════════════════════════════════════

class TestStructuredOnboarding:
    """Eight-step onboarding creates real stardust, entities, and knowledge gaps."""

    @pytest.mark.asyncio
    async def test_decisions_create_analytical_stardust(self, client):
        """Architectural decisions create Analytical Stardust with reasoning."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "AI knowledge system",
            "framework": "Python FastAPI with PostgreSQL",
            "architectural_decisions": [
                {"decision": "Use FastAPI over Flask", "reasoning": "Async support"},
            ],
            "tools": ["FastAPI"],
            "reexplanation_frustrations": [],
            "ai_frustrations": [],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["stardust_count"] >= 3  # framework + decision + tools

        # Verify the decision stardust is analytical
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        # Use the client's DB — check via another API call
        galaxy_id = data["galaxy_id"]
        search = await client.get(f"/api/v1/search?q=FastAPI+over+Flask&galaxy_id={galaxy_id}")
        if search.status_code == 200:
            records = search.json().get("records", [])
            analytical = [r for r in records if r.get("region") == "analytical"]
            assert len(analytical) >= 1

    @pytest.mark.asyncio
    async def test_reexplanations_get_galaxy_gravity(self, client):
        """Re-explanation frustrations create Stardust with GALAXY gravity."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "test",
            "framework": "Python",
            "architectural_decisions": [],
            "tools": [],
            "reexplanation_frustrations": [
                "We use FastAPI not Flask",
                "Redis is only for caching",
            ],
            "ai_frustrations": [],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["stardust_count"] >= 4  # framework + desc + 2 reexplanations

    @pytest.mark.asyncio
    async def test_tools_create_entities(self, client):
        """Tools create Entity records at tier 1."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "test",
            "framework": "Python",
            "architectural_decisions": [],
            "tools": ["FastAPI", "PostgreSQL", "Redis"],
            "reexplanation_frustrations": [],
            "ai_frustrations": [],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["entities_count"] >= 3

    @pytest.mark.asyncio
    async def test_ai_frustrations_logged_as_gaps(self, client):
        """AI frustrations logged as knowledge gaps."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "test",
            "framework": "Python",
            "architectural_decisions": [],
            "tools": [],
            "reexplanation_frustrations": [],
            "ai_frustrations": ["Keeps suggesting Flask patterns"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data.get("knowledge_gaps_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_completion_shows_real_counts(self, client):
        """Completion screen shows real counts, not placeholders."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "AI system",
            "framework": "Python FastAPI",
            "architectural_decisions": [
                {"decision": "Use SQLite locally", "reasoning": "Zero config"},
                {"decision": "Use Alembic", "reasoning": "Forward-only migrations"},
            ],
            "tools": ["FastAPI", "SQLite", "Alembic"],
            "reexplanation_frustrations": ["We use FastAPI not Flask"],
            "ai_frustrations": ["Suggests Django patterns"],
        })
        assert resp.status_code == 201
        data = resp.json()
        # Should have: 2 from codebase (desc + framework), 2 decisions,
        # 1 tools record, 1 reexplanation = 6+ stardust
        assert data["stardust_count"] >= 6
        assert data["entities_count"] >= 3
        assert data.get("knowledge_gaps_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_galaxy_has_10_plus_records(self, client):
        """Galaxy has >10 records before user arrives at Galaxy view."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "A personal AI knowledge architecture system",
            "framework": "Python FastAPI with PostgreSQL and Redis",
            "architectural_decisions": [
                {"decision": "FastAPI over Flask", "reasoning": "Async support"},
                {"decision": "PostgreSQL everywhere", "reasoning": "Schema consistency"},
                {"decision": "Alembic for migrations", "reasoning": "Forward-only"},
                {"decision": "Redis for caching only", "reasoning": "Not primary DB"},
                {"decision": "Docker Compose for local", "reasoning": "Reproducibility"},
            ],
            "tools": ["FastAPI", "PostgreSQL", "Redis", "Docker", "Alembic"],
            "reexplanation_frustrations": [
                "We use FastAPI not Flask",
                "Redis is only for caching",
                "Auth uses JWT with 15-min expiry",
            ],
            "ai_frustrations": ["Suggests Flask patterns", "Ignores our auth setup"],
        })
        assert resp.status_code == 201
        data = resp.json()
        # 2 codebase + 5 decisions + 1 tools + 3 reexplanations = 11+
        assert data["stardust_count"] >= 10


# ═══════════════════════════════════════════════════════════════════════════
# H1.4 — Contradiction Resolution Workflow
# ═══════════════════════════════════════════════════════════════════════════

class TestContradictionResolution:
    """All four resolution types persist correctly."""

    @pytest_asyncio.fixture
    async def contradiction_env(self, db, galaxy_env):
        """Create two contradicting stardust records and a contradiction."""
        env = galaxy_env
        record_a = Stardust(
            id=str(uuid4()), biome_id=env["biome"].id, planet_id=env["planet"].id,
            galaxy_id=env["galaxy"].id, content="Use SQLite for local dev",
            region="analytical", confidence=0.87,
        )
        record_a.context_tags = ["database"]
        record_b = Stardust(
            id=str(uuid4()), biome_id=env["biome"].id, planet_id=env["planet"].id,
            galaxy_id=env["galaxy"].id, content="Use PostgreSQL everywhere",
            region="analytical", confidence=0.82,
        )
        record_b.context_tags = ["database"]
        db.add_all([record_a, record_b])

        contradiction = Contradiction(
            id=str(uuid4()), galaxy_id=env["galaxy"].id,
            record_a_id=record_a.id, record_b_id=record_b.id,
            conflict_type="FACTUAL", status="UNRESOLVED",
            region="analytical",
        )
        db.add(contradiction)
        await db.commit()

        return {**env, "record_a": record_a, "record_b": record_b,
                "contradiction": contradiction}

    @pytest.mark.asyncio
    async def test_a_supersedes_b(self, db, contradiction_env):
        """a_supersedes_b sets valid_until on record B and boosts A."""
        env = contradiction_env
        from app.services.contradiction_service import contradiction_service

        result = await contradiction_service.resolve_contradiction(
            contradiction_id=env["contradiction"].id,
            resolution_type="a_supersedes_b",
            synthesis_content=None,
            galaxy_id=env["galaxy"].id,
            resolved_by="user",
            db=db,
        )

        assert result.status == "DEPRECATED"
        await db.refresh(env["record_b"])
        assert env["record_b"].valid_until is not None
        await db.refresh(env["record_a"])
        assert env["record_a"].confidence > 0.87

    @pytest.mark.asyncio
    async def test_b_supersedes_a(self, db, contradiction_env):
        """b_supersedes_a sets valid_until on record A."""
        env = contradiction_env
        from app.services.contradiction_service import contradiction_service

        result = await contradiction_service.resolve_contradiction(
            contradiction_id=env["contradiction"].id,
            resolution_type="b_supersedes_a",
            synthesis_content=None,
            galaxy_id=env["galaxy"].id,
            resolved_by="user",
            db=db,
        )

        assert result.status == "DEPRECATED"
        await db.refresh(env["record_a"])
        assert env["record_a"].valid_until is not None

    @pytest.mark.asyncio
    async def test_coexist(self, db, contradiction_env):
        """coexist sets status to COEXISTING and adds context_tags."""
        env = contradiction_env
        from app.services.contradiction_service import contradiction_service

        result = await contradiction_service.resolve_contradiction(
            contradiction_id=env["contradiction"].id,
            resolution_type="coexist",
            synthesis_content=None,
            galaxy_id=env["galaxy"].id,
            resolved_by="user",
            db=db,
        )

        assert result.status == "COEXISTING"
        await db.refresh(env["record_a"])
        assert f"coexists_with:{env['record_b'].id}" in env["record_a"].context_tags

    @pytest.mark.asyncio
    async def test_synthesize(self, db, contradiction_env):
        """synthesize creates new Stardust with DERIVED_FROM relationships."""
        env = contradiction_env
        from app.services.contradiction_service import contradiction_service

        result = await contradiction_service.resolve_contradiction(
            contradiction_id=env["contradiction"].id,
            resolution_type="synthesize",
            synthesis_content="Use SQLite locally, PostgreSQL in cloud and CI/CD.",
            galaxy_id=env["galaxy"].id,
            resolved_by="user",
            db=db,
        )

        assert result.status == "MERGED"
        assert result.new_stardust_id is not None

        # Both originals should have valid_until set
        await db.refresh(env["record_a"])
        await db.refresh(env["record_b"])
        assert env["record_a"].valid_until is not None
        assert env["record_b"].valid_until is not None

        # DERIVED_FROM relationships should exist
        from sqlalchemy import select
        rels = (await db.execute(
            select(StardustRelationship).where(
                StardustRelationship.relationship_type == "DERIVED_FROM"
            )
        )).scalars().all()
        assert len(rels) == 2

    @pytest.mark.asyncio
    async def test_synthesize_requires_content(self, db, contradiction_env):
        """synthesize without synthesis_content raises error."""
        env = contradiction_env
        from app.services.contradiction_service import contradiction_service

        with pytest.raises(ValueError, match="synthesis_content"):
            await contradiction_service.resolve_contradiction(
                contradiction_id=env["contradiction"].id,
                resolution_type="synthesize",
                synthesis_content=None,
                galaxy_id=env["galaxy"].id,
                resolved_by="user",
                db=db,
            )

    @pytest.mark.asyncio
    async def test_list_contradictions_endpoint(self, client):
        """GET /api/v1/contradictions returns unresolved contradictions."""
        # First create a galaxy via onboarding
        await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "test", "framework": "Python",
            "architectural_decisions": [], "tools": [],
            "reexplanation_frustrations": [], "ai_frustrations": [],
        })
        resp = await client.get("/api/v1/contradictions")
        assert resp.status_code == 200
        assert "contradictions" in resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# H1.5 — Active Synthesis (brain.synthesize)
# ═══════════════════════════════════════════════════════════════════════════

class TestActiveSynthesis:
    """brain.synthesize returns structured synthesis, caches in Redis."""

    @pytest.mark.asyncio
    async def test_synthesis_returns_structured_result(self, db, galaxy_env):
        """Synthesis returns all required sections."""
        env = galaxy_env
        # Seed some stardust
        for i in range(5):
            sd = Stardust(
                id=str(uuid4()), biome_id=env["biome"].id,
                planet_id=env["planet"].id, galaxy_id=env["galaxy"].id,
                content=f"FastAPI decision {i}: use async handlers",
                region="analytical", confidence=0.8,
            )
            sd.context_tags = ["fastapi"]
            db.add(sd)
        await db.commit()

        from app.services.synthesis_service import synthesis_service

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss
        mock_redis.setex = AsyncMock()

        with patch("app.services.synthesis_service.search") as mock_search:
            from app.schemas.stardust import SearchResponse, SearchRecord, RetrievalMetadata
            mock_search.return_value = SearchResponse(
                records=[SearchRecord(
                    id=str(uuid4()), content=f"FastAPI decision {i}",
                    region="analytical", biome_name="Backend",
                    planet_name="Engineering", confidence=0.8,
                    valid_from=datetime.now(timezone.utc), valid_until=None,
                    context_tags=["fastapi"], access_count=0, source_agent="test",
                ) for i in range(5)],
                retrieval_metadata=RetrievalMetadata(
                    sources_checked=[], cache_hits=0,
                    total_records_considered=5, records_returned=5,
                    confidence_range=[0.8, 0.8], retrieval_latency_ms=10,
                ),
            )

            with patch("app.services.synthesis_service.llm_complete") as mock_llm:
                mock_llm.return_value = (
                    "CURRENT_UNDERSTANDING:\nFastAPI is the primary framework.\n\n"
                    "KEY_DECISIONS:\n• Use async handlers for concurrency\n\n"
                    "OPEN_QUESTIONS:\n• Connection pooling strategy\n\n"
                    "CONFIDENCE: 0.85 — High confidence based on 5 records."
                )

                result = await synthesis_service.synthesize(
                    topic="FastAPI architecture",
                    galaxy_id=env["galaxy"].id,
                    planet_id=None, biome_id=None,
                    include_open_questions=True,
                    include_contradictions=True,
                    max_tokens=1000,
                    db=db, redis=mock_redis,
                )

        assert result.topic == "FastAPI architecture"
        assert result.current_understanding is not None
        assert len(result.current_understanding) > 0
        assert result.record_count == 5
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_synthesis_cache_hit(self, db, galaxy_env):
        """Cached synthesis returned without LLM call."""
        env = galaxy_env
        from app.services.synthesis_service import synthesis_service

        cached_data = json.dumps({
            "topic": "FastAPI",
            "current_understanding": "Cached understanding",
            "key_decisions": [],
            "open_questions": [],
            "contradictions": [],
            "confidence": 0.9,
            "record_count": 3,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        })

        mock_redis = AsyncMock()
        mock_redis.get.return_value = cached_data

        result = await synthesis_service.synthesize(
            topic="FastAPI", galaxy_id=env["galaxy"].id,
            planet_id=None, biome_id=None,
            include_open_questions=True, include_contradictions=True,
            max_tokens=1000, db=db, redis=mock_redis,
        )

        assert result.current_understanding == "Cached understanding"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_synthesis_empty_topic(self, db, galaxy_env):
        """Synthesis with no matching records returns empty result."""
        env = galaxy_env
        from app.services.synthesis_service import synthesis_service

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch("app.services.synthesis_service.search") as mock_search:
            from app.schemas.stardust import SearchResponse, RetrievalMetadata
            mock_search.return_value = SearchResponse(
                records=[],
                retrieval_metadata=RetrievalMetadata(
                    sources_checked=[], cache_hits=0,
                    total_records_considered=0, records_returned=0,
                    confidence_range=[], retrieval_latency_ms=5,
                ),
            )

            result = await synthesis_service.synthesize(
                topic="nonexistent topic", galaxy_id=env["galaxy"].id,
                planet_id=None, biome_id=None,
                include_open_questions=True, include_contradictions=True,
                max_tokens=1000, db=db, redis=mock_redis,
            )

        assert result.record_count == 0
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_synthesis_rest_endpoint(self, client):
        """POST /api/v1/synthesize returns synthesis result."""
        # Create galaxy first
        await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "test", "framework": "Python",
            "architectural_decisions": [], "tools": [],
            "reexplanation_frustrations": [], "ai_frustrations": [],
        })

        with patch("app.services.synthesis_service.synthesis_service.synthesize") as mock_synth:
            mock_synth.return_value = MagicMock(
                topic="test", current_understanding="Test synthesis",
                key_decisions=[], open_questions=[], contradictions=[],
                confidence=0.8, record_count=3,
                last_updated=datetime.now(timezone.utc).isoformat(),
                model_dump=lambda **kw: {
                    "topic": "test", "current_understanding": "Test synthesis",
                    "key_decisions": [], "open_questions": [], "contradictions": [],
                    "confidence": 0.8, "record_count": 3, "last_updated": None,
                },
            )
            resp = await client.post("/api/v1/synthesize", json={
                "topic": "test topic",
            })

        assert resp.status_code == 200
