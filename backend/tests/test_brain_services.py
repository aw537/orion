"""Unit tests for new brain services: relationship extractor, model switch, calibration, brain health, graph."""
import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


# ── Relationship Extractor Tests ────────────────────────────────────────────

class TestRelationshipExtractor:
    @pytest.fixture
    def extractor(self):
        from app.extraction.relationship_extractor import RelationshipExtractor
        return RelationshipExtractor()

    @pytest.fixture
    def entities(self):
        @dataclass
        class FakeEntity:
            id: str
            name: str
            entity_type: str = "tool"
        return [
            FakeEntity(id="e1", name="FastAPI"),
            FakeEntity(id="e2", name="PostgreSQL"),
            FakeEntity(id="e3", name="Redis"),
            FakeEntity(id="e4", name="Flask"),
        ]

    def test_uses_pattern(self, extractor, entities):
        rels = extractor.extract("FastAPI uses PostgreSQL for data storage", entities)
        assert len(rels) >= 1
        assert rels[0].relationship_type == "USES"
        assert rels[0].source_entity.name == "FastAPI"
        assert rels[0].target_entity.name == "PostgreSQL"

    def test_replaces_pattern(self, extractor, entities):
        rels = extractor.extract("FastAPI replaces Flask as the web framework", entities)
        types = {r.relationship_type for r in rels}
        assert "REPLACES" in types

    def test_depends_on_pattern(self, extractor, entities):
        rels = extractor.extract("FastAPI requires Redis for caching", entities)
        types = {r.relationship_type for r in rels}
        assert "DEPENDS_ON" in types

    def test_works_with_pattern(self, extractor, entities):
        rels = extractor.extract("FastAPI works with Redis for session management", entities)
        types = {r.relationship_type for r in rels}
        assert "WORKS_WITH" in types or "DEPENDS_ON" in types  # may match either

    def test_no_self_relationship(self, extractor, entities):
        rels = extractor.extract("FastAPI uses FastAPI internally", entities)
        for r in rels:
            assert r.source_entity.id != r.target_entity.id

    def test_deduplication(self, extractor, entities):
        rels = extractor.extract(
            "FastAPI uses PostgreSQL. FastAPI also uses PostgreSQL for queries.", entities
        )
        uses_rels = [r for r in rels if r.relationship_type == "USES"
                     and r.source_entity.name == "FastAPI" and r.target_entity.name == "PostgreSQL"]
        assert len(uses_rels) == 1

    def test_too_few_entities(self, extractor):
        @dataclass
        class FakeEntity:
            id: str
            name: str
            entity_type: str = "tool"
        rels = extractor.extract("FastAPI is great", [FakeEntity(id="e1", name="FastAPI")])
        assert rels == []

    def test_empty_content(self, extractor, entities):
        assert extractor.extract("", entities) == []

    def test_multiple_relationship_types(self, extractor, entities):
        rels = extractor.extract(
            "FastAPI uses PostgreSQL and FastAPI replaces Flask", entities
        )
        types = {r.relationship_type for r in rels}
        assert "USES" in types
        assert "REPLACES" in types


# ── Model Switch Service Tests ──────────────────────────────────────────────

class TestModelSwitchService:
    def test_same_family_continuity(self):
        from app.services.model_switch_service import ModelSwitchService
        svc = ModelSwitchService()
        result = svc._assess_continuity("claude-sonnet-4-6", "claude-opus-4-6")
        assert result["score"] == 0.95
        assert result["issues"] == []

    def test_cross_family_continuity(self):
        from app.services.model_switch_service import ModelSwitchService
        svc = ModelSwitchService()
        result = svc._assess_continuity("claude-sonnet-4-6", "gpt-4o")
        assert result["score"] == 0.7
        assert len(result["issues"]) > 0

    def test_family_inference(self):
        from app.services.model_switch_service import ModelSwitchService
        svc = ModelSwitchService()
        assert svc._family("claude-sonnet-4-6") == "claude"
        assert svc._family("gpt-4o") == "gpt"
        assert svc._family("llama3:70b") == "llama"
        assert svc._family("my-custom-model") == "custom"


# ── Agent Identity Service Tests ────────────────────────────────────────────

class TestAgentIdentityService:
    def test_family_inference(self):
        from app.services.agent_identity_service import AgentIdentityService
        svc = AgentIdentityService()
        assert svc._infer_family("claude-sonnet-4-6") == "claude"
        assert svc._infer_family("gpt-4o-mini") == "gpt"
        assert svc._infer_family("gemini-pro") == "gemini"
        assert svc._infer_family("mistral:latest") == "mistral"
        assert svc._infer_family("deepseek-coder") == "deepseek"
        assert svc._infer_family("qwen-72b") == "qwen"
        assert svc._infer_family("unknown-model") == "custom"


# ── Brain Health Score Tests ────────────────────────────────────────────────

class TestBrainHealthScoring:
    @pytest.mark.asyncio
    async def test_health_score_with_empty_galaxy(self):
        """Health service returns valid scores for an agent with no knowledge."""
        from app.services.brain_health_service import brain_health_service
        from app.models.brain import AgentIdentity
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.models.galaxy import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as db:
            agent = AgentIdentity(
                id="test-agent-id", galaxy_id="test-galaxy",
                agent_name="test", agent_type="GENERAL",
                current_model="claude-sonnet-4-6", model_family="claude",
                birth_date=datetime.now(timezone.utc),
                retrieval_quality_score=0.0, expertise_profile="{}",
            )
            result = await brain_health_service.get_brain_health(agent, "test-galaxy", db)

        assert 0.0 <= result["overall_health"] <= 1.0
        assert result["total_knowledge_items"] == 0
        assert result["knowledge_freshness"] == 0.0
        assert isinstance(result["coverage_gaps"], list)
        assert isinstance(result["stale_beliefs"], list)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_health_score_formula_matches(self):
        """Verify the formula: freshness*0.3 + (1-gaps/10)*0.3 + (1-stale/10)*0.2 + quality*0.2."""
        from app.services.brain_health_service import brain_health_service
        from app.models.brain import AgentIdentity
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.models.galaxy import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as db:
            agent = AgentIdentity(
                id="test-agent-id", galaxy_id="g1",
                agent_name="test", agent_type="GENERAL",
                current_model="claude-sonnet-4-6", model_family="claude",
                birth_date=datetime.now(timezone.utc),
                retrieval_quality_score=0.7, expertise_profile="{}",
            )
            result = await brain_health_service.get_brain_health(agent, "g1", db)

        # With no knowledge: freshness=0, gaps=0, stale=0, quality=0.7
        expected = 0 * 0.30 + 1.0 * 0.30 + 1.0 * 0.20 + 0.7 * 0.20
        assert result["overall_health"] == pytest.approx(expected, abs=0.01)
        await engine.dispose()


# ── Calibration Logic Tests ─────────────────────────────────────────────────

class TestCalibrationLogic:
    @pytest.mark.asyncio
    async def test_calibration_boosts_used_records(self):
        """Used records get +0.02 confidence via the real service."""
        from app.services.calibration_service import calibration_service
        from app.models.stardust import Stardust
        from app.models.brain import AgentIdentity
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.models.galaxy import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as db:
            # Seed agent identity
            agent = AgentIdentity(
                id="agent-1", galaxy_id="g1", agent_name="test",
                agent_type="GENERAL", current_model="claude-sonnet-4-6",
                model_family="claude", birth_date=datetime.now(timezone.utc),
                retrieval_quality_score=0.0, expertise_profile="{}",
            )
            db.add(agent)
            # Seed a stardust record
            sd = Stardust(
                id="sd-1", biome_id="b1", planet_id="p1", galaxy_id="g1",
                content="test", region="contextual", gravity="BIOME",
                confidence=0.5, valid_from=datetime.now(timezone.utc),
                context_tags="[]", reinforcement_sources=0,
                access_count=0, created_at=datetime.now(timezone.utc),
            )
            db.add(sd)
            await db.commit()

            result = await calibration_service.process_calibration(
                session_id="sess-1", agent_identity_id="agent-1", galaxy_id="g1",
                records_used=["sd-1"], records_retrieved_unused=[],
                knowledge_gaps=[], session_outcome="test",
                knowledge_quality_score=0.8, db=db,
            )
            assert result["records_boosted"] == 1
            assert result["records_decayed"] == 0

            await db.refresh(sd)
            assert sd.confidence == pytest.approx(0.52)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_calibration_decays_unused_records(self):
        """Unused records get -0.005 confidence via the real service."""
        from app.services.calibration_service import calibration_service
        from app.models.stardust import Stardust
        from app.models.brain import AgentIdentity
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.models.galaxy import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as db:
            agent = AgentIdentity(
                id="agent-1", galaxy_id="g1", agent_name="test",
                agent_type="GENERAL", current_model="claude-sonnet-4-6",
                model_family="claude", birth_date=datetime.now(timezone.utc),
                retrieval_quality_score=0.6, expertise_profile="{}",
            )
            db.add(agent)
            sd = Stardust(
                id="sd-1", biome_id="b1", planet_id="p1", galaxy_id="g1",
                content="test", region="contextual", gravity="BIOME",
                confidence=0.5, valid_from=datetime.now(timezone.utc),
                context_tags="[]", reinforcement_sources=0,
                access_count=0, created_at=datetime.now(timezone.utc),
            )
            db.add(sd)
            await db.commit()

            result = await calibration_service.process_calibration(
                session_id="sess-1", agent_identity_id="agent-1", galaxy_id="g1",
                records_used=[], records_retrieved_unused=["sd-1"],
                knowledge_gaps=["OAuth2"], session_outcome="test",
                knowledge_quality_score=0.9, db=db,
            )
            assert result["records_decayed"] == 1
            assert result["gaps_logged"] == 1

            await db.refresh(sd)
            assert sd.confidence == pytest.approx(0.495)

            # EMA update: 0.1 * 0.9 + 0.9 * 0.6 = 0.63
            await db.refresh(agent)
            assert agent.retrieval_quality_score == pytest.approx(0.63)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_calibration_ema_first_value(self):
        """First calibration sets quality score directly (old=0)."""
        from app.services.calibration_service import calibration_service
        from app.models.brain import AgentIdentity
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.models.galaxy import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as db:
            agent = AgentIdentity(
                id="agent-1", galaxy_id="g1", agent_name="test",
                agent_type="GENERAL", current_model="claude-sonnet-4-6",
                model_family="claude", birth_date=datetime.now(timezone.utc),
                retrieval_quality_score=0.0, expertise_profile="{}",
            )
            db.add(agent)
            await db.commit()

            await calibration_service.process_calibration(
                session_id="sess-1", agent_identity_id="agent-1", galaxy_id="g1",
                records_used=[], records_retrieved_unused=[],
                knowledge_gaps=[], session_outcome="test",
                knowledge_quality_score=0.8, db=db,
            )
            await db.refresh(agent)
            assert agent.retrieval_quality_score == pytest.approx(0.8)
        await engine.dispose()


# ── Cognitive Region Prompts Tests ──────────────────────────────────────────

class TestCognitiveRegionPrompts:
    def test_all_regions_present(self):
        from app.config import REGION_REASONING_PROMPTS
        expected = {"analytical", "procedural", "contextual", "creative", "empathetic", "critical", "strategic"}
        assert set(REGION_REASONING_PROMPTS.keys()) == expected

    def test_prompts_are_nonempty(self):
        from app.config import REGION_REASONING_PROMPTS
        for key, prompt in REGION_REASONING_PROMPTS.items():
            assert len(prompt) > 20, f"Prompt for {key} is too short"


# ── Pydantic Schema Tests ──────────────────────────────────────────────────

class TestBrainSchemas:
    def test_agent_orient_request(self):
        from app.schemas.brain import AgentOrientRequest
        req = AgentOrientRequest(agent_name="test-agent", model="claude-sonnet-4-6")
        assert req.agent_type == "GENERAL"
        assert req.max_tokens is None

    def test_brain_think_request(self):
        from app.schemas.brain import BrainThinkRequest
        req = BrainThinkRequest(content="test", planet="Engineering")
        assert req.cognitive_mode == "contextual"
        assert req.confidence == 0.7
        assert req.supersedes is None

    def test_calibration_receipt(self):
        from app.schemas.brain import CalibrationReceipt
        r = CalibrationReceipt(calibration_id="abc", records_boosted=5, records_decayed=2, gaps_logged=1)
        assert r.records_boosted == 5

    def test_graph_path_response(self):
        from app.schemas.brain import GraphPathResponse
        p = GraphPathResponse(nodes=["a", "b", "c"], relationship_types=["USES", "DEPENDS_ON"], length=2)
        assert p.length == 2
        assert len(p.nodes) == 3
