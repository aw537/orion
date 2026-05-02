"""H1 Audit Tests — verify real integration paths, not mocks.
These tests exercise the actual service code against an in-memory SQLite DB."""
import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select, text, insert
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import Base, Galaxy, Planet, Biome, Stardust, Entity, Contradiction
from app.models.brain import (
    AgentIdentity, AgentSession, SessionCalibration, StardustRelationship,
)
from app.models.nebula import InteractionLog


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False,
                                 connect_args={"check_same_thread": False})
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed(db):
    """Seed a full galaxy environment."""
    now = datetime.now(timezone.utc)
    g = Galaxy(id=str(uuid4()), name="Audit Galaxy", created_at=now,
               strength_score=50.0, total_nodes=0, schema_version="0.1.0")
    p = Planet(id=str(uuid4()), galaxy_id=g.id, name="Engineering",
               stardust_count=0, health_status="healthy")
    b = Biome(id=str(uuid4()), planet_id=p.id, galaxy_id=g.id,
              name="Backend", lifecycle_state="ACTIVE")
    agent = AgentIdentity(
        id=str(uuid4()), galaxy_id=g.id, agent_name="audit-agent",
        agent_type="GENERAL", current_model="claude-sonnet-4-20250514",
        model_family="claude", birth_date=now, expertise_profile="{}",
    )
    session = AgentSession(
        id=str(uuid4()), agent_identity_id=agent.id, galaxy_id=g.id,
        model_used="claude-sonnet-4-20250514", started_at=now,
        galaxy_strength_at_start=50.0,
    )
    db.add_all([g, p, b, agent, session])
    await db.commit()
    return {"galaxy": g, "planet": p, "biome": b, "agent": agent, "session": session}


# ═══════════════════════════════════════════════════════════════════════════
# H1.1 AUDIT — Session Summary
# ═══════════════════════════════════════════════════════════════════════════

class TestH11Audit:

    @pytest.mark.asyncio
    async def test_tier_upgrades_extracted_from_nebula(self, db):
        """Tier upgrades are extracted from ENTITY_ENRICHED events with payload."""
        env = await _seed(db)
        sid = env["session"].id
        gid = env["galaxy"].id

        # Seed a write + an entity enrichment with tier upgrade payload
        await db.execute(insert(InteractionLog).values(
            galaxy_id=gid, session_id=sid, action_type="WRITE",
            initiated_by="audit-agent", record_id=str(uuid4()),
        ))
        await db.execute(insert(InteractionLog).values(
            galaxy_id=gid, session_id=sid, action_type="ENTITY_ENRICHED",
            initiated_by="system", record_id=str(uuid4()),
            payload_after=json.dumps({
                "entity_name": "FastAPI", "previous_tier": 1, "new_tier": 2,
            }),
        ))
        await db.commit()

        from app.services.session_summary_service import session_summary_service
        from unittest.mock import patch
        # Set galaxy strength_score directly (no longer calls compute_galaxy_strength)
        from sqlalchemy import update as sql_update
        from app.models import Galaxy
        await db.execute(sql_update(Galaxy).where(Galaxy.id == gid).values(strength_score=55.0))
        await db.commit()
        summary = await session_summary_service.generate_summary(sid, gid, db)

        assert summary is not None
        assert summary.entities_enriched == 1
        assert len(summary.tier_upgrades) == 1
        assert summary.tier_upgrades[0] == ("FastAPI", 1, 2)

    @pytest.mark.asyncio
    async def test_summary_duration_is_reasonable(self, db):
        """Duration is calculated from session start to now."""
        env = await _seed(db)
        sid = env["session"].id
        gid = env["galaxy"].id

        await db.execute(insert(InteractionLog).values(
            galaxy_id=gid, session_id=sid, action_type="WRITE",
            initiated_by="audit-agent", record_id=str(uuid4()),
        ))
        await db.commit()

        from app.services.session_summary_service import session_summary_service
        summary = await session_summary_service.generate_summary(sid, gid, db)

        assert summary.duration_minutes >= 0
        assert summary.duration_minutes < 60  # test runs in seconds


# ═══════════════════════════════════════════════════════════════════════════
# H1.2 AUDIT — Structured Onboarding
# ═══════════════════════════════════════════════════════════════════════════

class TestH12Audit:

    @pytest.mark.asyncio
    async def test_decisions_have_reasoning_field_populated(self, client):
        """Architectural decisions actually store reasoning in the DB."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "test",
            "framework": "Python FastAPI",
            "architectural_decisions": [
                {"decision": "Use FastAPI", "reasoning": "Async support needed"},
            ],
            "tools": [], "reexplanation_frustrations": [], "ai_frustrations": [],
        })
        assert resp.status_code == 201

        # Query the DB directly for the analytical stardust
        from app.database import async_session
        from sqlalchemy import select
        async with async_session() as db:
            result = await db.execute(
                select(Stardust).where(
                    Stardust.region == "analytical",
                    Stardust.content == "Use FastAPI",
                )
            )
            sd = result.scalar_one_or_none()
            assert sd is not None
            assert sd.reasoning == "Async support needed"
            assert sd.confidence == 0.9
            assert sd.gravity == "PLANET"

    @pytest.mark.asyncio
    async def test_reexplanations_actually_galaxy_gravity(self, client):
        """Re-explanations are stored with GALAXY gravity and 0.95 confidence."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "test",
            "framework": "Python",
            "architectural_decisions": [],
            "tools": [],
            "reexplanation_frustrations": ["We use FastAPI not Flask"],
            "ai_frustrations": [],
        })
        assert resp.status_code == 201

        from app.database import async_session
        async with async_session() as db:
            result = await db.execute(
                select(Stardust).where(
                    Stardust.content == "We use FastAPI not Flask",
                )
            )
            sd = result.scalar_one_or_none()
            assert sd is not None
            assert sd.gravity == "GALAXY"
            assert sd.confidence == 0.95

    @pytest.mark.asyncio
    async def test_ai_frustrations_create_calibration_records(self, client):
        """AI frustrations create SessionCalibration records with knowledge_gaps."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "codebase_description": "test",
            "framework": "Python",
            "architectural_decisions": [],
            "tools": [],
            "reexplanation_frustrations": [],
            "ai_frustrations": ["Keeps suggesting Flask"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["knowledge_gaps_count"] == 1

        from app.database import async_session
        async with async_session() as db:
            result = await db.execute(
                select(SessionCalibration).where(
                    SessionCalibration.session_id == "onboarding",
                )
            )
            cal = result.scalar_one_or_none()
            assert cal is not None
            gaps = cal.knowledge_gaps if isinstance(cal.knowledge_gaps, list) else json.loads(cal.knowledge_gaps)
            assert "Keeps suggesting Flask" in gaps

    @pytest.mark.asyncio
    async def test_backward_compat_old_onboarding_still_works(self, client):
        """Old-style onboarding (no H1.2 fields) still works."""
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Software Engineer",
            "goal": "Build an API",
            "tools": ["FastAPI"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["stardust_count"] >= 2  # goal + tools
        assert data["entities_count"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# H1.3 AUDIT — MCP Activity Indicator
# ═══════════════════════════════════════════════════════════════════════════

class TestH13Audit:

    @pytest.mark.asyncio
    async def test_status_line_with_zero_records(self):
        """Status line handles zero records gracefully."""
        from app.services.session_summary_service import build_status_line
        line = build_status_line(0, "Backend", 0.0)
        assert "[orion:" in line
        assert "0 records" in line

    @pytest.mark.asyncio
    async def test_status_line_truncation_boundary(self):
        """Status line truncates biome name exactly at 80 chars."""
        from app.services.session_summary_service import build_status_line
        # A very long biome name
        long_name = "A" * 200
        line = build_status_line(999, long_name, 100.0)
        assert len(line) <= 80
        assert "…" in line  # truncation marker present

    @pytest.mark.asyncio
    async def test_confirmation_line_format(self):
        """Confirmation line has expected format."""
        from app.services.session_summary_service import build_confirmation_line
        line = build_confirmation_line("Auth Biome", "analytical", 7)
        assert line == "[orion: written to Auth Biome · analytical · 7 records today]"

    @pytest.mark.asyncio
    async def test_memory_search_has_no_indicator(self):
        """memory.search response should NOT have orion_status_line or orion_confirmation."""
        # Verify by reading the source — memory_search returns result.model_dump()
        # with no indicator injected
        import inspect
        from app.mcp.tools_memory import memory_search
        source = inspect.getsource(memory_search)
        assert "orion_status_line" not in source
        assert "orion_confirmation" not in source


# ═══════════════════════════════════════════════════════════════════════════
# H1.4 AUDIT — Contradiction Resolution
# ═══════════════════════════════════════════════════════════════════════════

class TestH14Audit:

    @pytest_asyncio.fixture
    async def contra_env(self, db):
        env = await _seed(db)
        a = Stardust(
            id=str(uuid4()), biome_id=env["biome"].id, planet_id=env["planet"].id,
            galaxy_id=env["galaxy"].id, content="Use SQLite locally",
            region="analytical", confidence=0.87,
        )
        a.context_tags = ["db"]
        b = Stardust(
            id=str(uuid4()), biome_id=env["biome"].id, planet_id=env["planet"].id,
            galaxy_id=env["galaxy"].id, content="Use PostgreSQL everywhere",
            region="analytical", confidence=0.82,
        )
        b.context_tags = ["db"]
        c = Contradiction(
            id=str(uuid4()), galaxy_id=env["galaxy"].id,
            record_a_id=a.id, record_b_id=b.id,
            conflict_type="FACTUAL", status="UNRESOLVED", region="analytical",
        )
        db.add_all([a, b, c])
        await db.commit()
        return {**env, "a": a, "b": b, "contradiction": c}

    @pytest.mark.asyncio
    async def test_supersede_creates_relationship(self, db, contra_env):
        """a_supersedes_b creates a SUPERSEDES StardustRelationship."""
        env = contra_env
        from app.services.contradiction_service import contradiction_service
        await contradiction_service.resolve_contradiction(
            env["contradiction"].id, "a_supersedes_b", None,
            env["galaxy"].id, "user", db,
        )
        rels = (await db.execute(
            select(StardustRelationship).where(
                StardustRelationship.relationship_type == "SUPERSEDES",
            )
        )).scalars().all()
        assert len(rels) == 1
        assert rels[0].source_stardust_id == env["a"].id
        assert rels[0].target_stardust_id == env["b"].id

    @pytest.mark.asyncio
    async def test_coexist_tags_are_bidirectional(self, db, contra_env):
        """coexist adds coexists_with tag to BOTH records."""
        env = contra_env
        from app.services.contradiction_service import contradiction_service
        await contradiction_service.resolve_contradiction(
            env["contradiction"].id, "coexist", None,
            env["galaxy"].id, "user", db,
        )
        await db.refresh(env["a"])
        await db.refresh(env["b"])
        assert f"coexists_with:{env['b'].id}" in env["a"].context_tags
        assert f"coexists_with:{env['a'].id}" in env["b"].context_tags

    @pytest.mark.asyncio
    async def test_synthesize_new_record_inherits_biome_planet(self, db, contra_env):
        """Synthesized record inherits biome_id and planet_id from record A."""
        env = contra_env
        from app.services.contradiction_service import contradiction_service
        result = await contradiction_service.resolve_contradiction(
            env["contradiction"].id, "synthesize",
            "Use SQLite locally, PostgreSQL in cloud.",
            env["galaxy"].id, "user", db,
        )
        new_sd = await db.get(Stardust, result.new_stardust_id)
        assert new_sd is not None
        assert new_sd.biome_id == env["biome"].id
        assert new_sd.planet_id == env["planet"].id
        assert new_sd.confidence == 0.9
        assert new_sd.gravity == "PLANET"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_contradiction_raises(self, db, contra_env):
        """Resolving a nonexistent contradiction raises ValueError."""
        from app.services.contradiction_service import contradiction_service
        with pytest.raises(ValueError, match="not found"):
            await contradiction_service.resolve_contradiction(
                "nonexistent", "coexist", None, "gid", "user", db,
            )

    @pytest.mark.asyncio
    async def test_resolve_invalid_type_raises(self, db, contra_env):
        """Invalid resolution_type raises ValueError."""
        env = contra_env
        from app.services.contradiction_service import contradiction_service
        with pytest.raises(ValueError, match="Unknown resolution_type"):
            await contradiction_service.resolve_contradiction(
                env["contradiction"].id, "invalid_type", None,
                env["galaxy"].id, "user", db,
            )

    @pytest.mark.asyncio
    async def test_resolved_contradiction_has_timestamp_and_reviewer(self, db, contra_env):
        """After resolution, contradiction has resolved_at, resolved_by, human_reviewed."""
        env = contra_env
        from app.services.contradiction_service import contradiction_service
        await contradiction_service.resolve_contradiction(
            env["contradiction"].id, "coexist", None,
            env["galaxy"].id, "user", db,
        )
        await db.refresh(env["contradiction"])
        assert env["contradiction"].resolved_at is not None
        assert env["contradiction"].resolved_by == "user"
        assert env["contradiction"].human_reviewed == 1


# ═══════════════════════════════════════════════════════════════════════════
# H1.5 AUDIT — Active Synthesis
# ═══════════════════════════════════════════════════════════════════════════

class TestH15Audit:

    @pytest.mark.asyncio
    async def test_synthesis_prompt_includes_contradictions_when_present(self):
        """When contradictions exist, they appear in the prompt."""
        from app.services.synthesis_service import synthesis_service
        prompt = synthesis_service._build_prompt(
            "FastAPI", "1. [analytical] Use FastAPI\n   Confidence: 0.9",
            include_open_questions=True, max_tokens=1000,
            contradictions=["'Use SQLite' vs 'Use PostgreSQL'"],
        )
        assert "CONTRADICTIONS" in prompt
        assert "Use SQLite" in prompt

    @pytest.mark.asyncio
    async def test_synthesis_prompt_excludes_contradictions_when_empty(self):
        """When no contradictions, CONTRADICTIONS section not in prompt."""
        from app.services.synthesis_service import synthesis_service
        prompt = synthesis_service._build_prompt(
            "FastAPI", "records", include_open_questions=True,
            max_tokens=1000, contradictions=[],
        )
        assert "Known contradictions:" not in prompt

    @pytest.mark.asyncio
    async def test_parse_response_extracts_all_sections(self):
        """Parser correctly extracts all sections from LLM output."""
        from app.services.synthesis_service import synthesis_service
        raw = (
            "CURRENT_UNDERSTANDING:\nFastAPI is the primary framework.\n\n"
            "KEY_DECISIONS:\n• Use async handlers\n• Use Pydantic models\n\n"
            "OPEN_QUESTIONS:\n• Connection pooling?\n\n"
            "CONTRADICTIONS:\n• SQLite vs PostgreSQL scope\n\n"
            "CONFIDENCE: 0.85 — High confidence."
        )
        from unittest.mock import MagicMock
        mock_records = [MagicMock(valid_from=datetime.now(timezone.utc))]
        result = synthesis_service._parse_response(raw, "FastAPI", mock_records, [])

        assert "FastAPI is the primary framework" in result.current_understanding
        assert len(result.key_decisions) == 2
        assert "Use async handlers" in result.key_decisions[0]
        assert len(result.open_questions) == 1
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_parse_response_handles_empty_llm_output(self):
        """Parser handles empty LLM response gracefully."""
        from app.services.synthesis_service import synthesis_service
        result = synthesis_service._parse_response("", "test", [], [])
        assert result.current_understanding == "Synthesis generated."
        assert result.confidence == 0.5  # default
        assert result.key_decisions == []

    @pytest.mark.asyncio
    async def test_cache_key_deterministic(self):
        """Same inputs produce same cache key."""
        from app.services.synthesis_service import synthesis_service
        k1 = synthesis_service._hash("FastAPI", "p1", "b1")
        k2 = synthesis_service._hash("FastAPI", "p1", "b1")
        k3 = synthesis_service._hash("FastAPI", "p1", "b2")
        assert k1 == k2
        assert k1 != k3

    @pytest.mark.asyncio
    async def test_brain_synthesize_registered_in_mcp(self):
        """brain.synthesize is registered as an MCP tool."""
        import inspect
        from app.mcp import server
        source = inspect.getsource(server)
        assert 'name="brain.synthesize"' in source
