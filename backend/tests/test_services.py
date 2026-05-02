"""Unit tests for Orion backend services."""
import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.galaxy import Base, Galaxy
from app.models.planet import Planet
from app.models.biome import Biome
from app.models.stardust import Stardust
from app.models.entity import Entity, EntityStardust
from app.models.nebula import InteractionLog
from app.models.contradiction import Contradiction
from app.models.profiles import StrengthHistory, ModelProfile
from app.models.brain import (
    AgentIdentity, AgentSession, AgentExpertise,
    EntityRelationship, EntityBacklink, GraphPathCache,
    StardustRelationship, KnowledgeIntegrationLog,
    SessionCalibration, ModelSwitchLog, TransitionOrientation,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def galaxy(db):
    g = Galaxy(id="gal-1", name="Test Galaxy", created_at=datetime.now(timezone.utc) - timedelta(days=30))
    p = Planet(id="pl-1", galaxy_id="gal-1", name="Engineering")
    b = Biome(id="bi-1", planet_id="pl-1", galaxy_id="gal-1", name="Backend",
              last_active_at=datetime.now(timezone.utc))
    db.add_all([g, p, b])
    await db.commit()
    return g


def _make_stardust(id, galaxy_id="gal-1", content="test", confidence=0.7, **kw):
    return Stardust(id=id, biome_id=kw.get("biome_id", "bi-1"), planet_id=kw.get("planet_id", "pl-1"),
                    galaxy_id=galaxy_id, content=content, confidence=confidence,
                    created_at=kw.get("created_at", datetime.now(timezone.utc)),
                    access_count=kw.get("access_count", 0),
                    last_accessed=kw.get("last_accessed"), reasoning=kw.get("reasoning"),
                    supersedes=kw.get("supersedes"), reinforcement_sources=kw.get("reinforcement_sources", 1))


def _make_entity(id, galaxy_id="gal-1", name="TestEntity", tier=2, **kw):
    return Entity(id=id, galaxy_id=galaxy_id, name=name, entity_type=kw.get("entity_type", "tool"),
                  tier=tier, mention_count=kw.get("mention_count", 1))


def _make_identity(id="aid-1", galaxy_id="gal-1", agent_name="test-agent", model="claude-sonnet-4-6", **kw):
    return AgentIdentity(id=id, galaxy_id=galaxy_id, agent_name=agent_name, agent_type="GENERAL",
                         model_family="claude", current_model=model,
                         birth_date=kw.get("birth_date", datetime.now(timezone.utc) - timedelta(days=60)),
                         total_sessions=kw.get("total_sessions", 5),
                         total_reads=kw.get("total_reads", 100), total_writes=kw.get("total_writes", 50),
                         expertise_profile="{}", retrieval_quality_score=kw.get("retrieval_quality_score", 0.7))


# ── GraphService Tests ──────────────────────────────────────────────────────

class TestGraphService:
    @pytest.fixture
    def svc(self):
        from app.services.graph_service import GraphService
        return GraphService()

    @pytest.mark.asyncio
    async def test_upsert_relationship_new(self, svc, db, galaxy):
        rel = await svc.upsert_relationship("e1", "e2", "USES", 0.8, "s1", "gal-1", db)
        assert rel.source_entity_id == "e1"
        assert rel.relationship_type == "USES"
        assert rel.strength == 1
        ids = rel.source_stardust_ids if isinstance(rel.source_stardust_ids, list) else json.loads(rel.source_stardust_ids)
        assert ids == ["s1"]

    @pytest.mark.asyncio
    async def test_upsert_relationship_existing(self, svc, db, galaxy):
        await svc.upsert_relationship("e1", "e2", "USES", 0.8, "s1", "gal-1", db)
        rel = await svc.upsert_relationship("e1", "e2", "USES", 0.9, "s2", "gal-1", db)
        assert rel.strength == 2
        ids = rel.source_stardust_ids if isinstance(rel.source_stardust_ids, list) else json.loads(rel.source_stardust_ids)
        assert "s2" in ids

    @pytest.mark.asyncio
    async def test_update_backlinks_new(self, svc, db, galaxy):
        sd = _make_stardust("sd-1")
        e = _make_entity("e1", name="FastAPI")
        db.add_all([sd, e])
        await db.flush()
        await svc.update_backlinks(sd, [e], db)
        from sqlalchemy import select
        bl = (await db.execute(select(EntityBacklink).where(EntityBacklink.entity_id == "e1"))).scalar_one()
        assert bl.mention_count == 1

    @pytest.mark.asyncio
    async def test_update_backlinks_increments(self, svc, db, galaxy):
        sd = _make_stardust("sd-1")
        e = _make_entity("e1", name="FastAPI")
        db.add_all([sd, e])
        await db.flush()
        await svc.update_backlinks(sd, [e], db)
        await svc.update_backlinks(sd, [e], db)
        from sqlalchemy import select
        bl = (await db.execute(select(EntityBacklink).where(EntityBacklink.entity_id == "e1"))).scalar_one()
        assert bl.mention_count == 2

    @pytest.mark.asyncio
    async def test_find_path_self(self, svc, db, galaxy):
        result = await svc.find_path("e1", "e1", "gal-1", db)
        assert result == {"nodes": ["e1"], "relationship_types": [], "length": 0}

    @pytest.mark.asyncio
    async def test_find_path_found(self, svc, db, galaxy):
        db.add(EntityRelationship(id="r1", galaxy_id="gal-1", source_entity_id="e1",
               target_entity_id="e2", relationship_type="USES", confidence=0.8,
               source_stardust_ids="[]", strength=1))
        await db.flush()
        result = await svc.find_path("e1", "e2", "gal-1", db)
        assert result["length"] == 1
        assert result["nodes"] == ["e1", "e2"]

    @pytest.mark.asyncio
    async def test_find_path_not_found(self, svc, db, galaxy):
        result = await svc.find_path("e1", "e999", "gal-1", db)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_entity_neighborhood(self, svc, db, galaxy):
        e1, e2 = _make_entity("e1", name="A"), _make_entity("e2", name="B")
        db.add_all([e1, e2, EntityRelationship(id="r1", galaxy_id="gal-1", source_entity_id="e1",
                    target_entity_id="e2", relationship_type="USES", confidence=0.9,
                    source_stardust_ids="[]", strength=1)])
        await db.flush()
        result = await svc.get_entity_neighborhood("e1", 1, "gal-1", db)
        assert len(result["entities"]) == 2
        assert len(result["edges"]) == 1

    @pytest.mark.asyncio
    async def test_get_hub_entities(self, svc, db, galaxy):
        e1 = _make_entity("e1", name="Hub")
        e2 = _make_entity("e2", name="Leaf")
        e3 = _make_entity("e3", name="Isolated")
        db.add_all([e1, e2, e3,
            EntityRelationship(id="r1", galaxy_id="gal-1", source_entity_id="e1",
                               target_entity_id="e2", relationship_type="USES",
                               confidence=0.8, source_stardust_ids="[]", strength=1),
            EntityRelationship(id="r2", galaxy_id="gal-1", source_entity_id="e1",
                               target_entity_id="e3", relationship_type="DEPENDS_ON",
                               confidence=0.8, source_stardust_ids="[]", strength=1)])
        await db.flush()
        hubs = await svc.get_hub_entities("gal-1", 5, db)
        assert hubs[0]["name"] == "Hub"
        assert hubs[0]["degree"] >= 2

    @pytest.mark.asyncio
    async def test_find_unlinked_mentions(self, svc, db, galaxy):
        e = _make_entity("e1", name="FastAPI", tier=2)
        sd = _make_stardust("sd-1", content="We use FastAPI for the backend")
        db.add_all([e, sd])
        await db.flush()
        suggestions = await svc.find_unlinked_mentions("gal-1", db)
        assert len(suggestions) == 1
        assert suggestions[0]["entity_name"] == "FastAPI"

    @pytest.mark.asyncio
    async def test_link_entity_stardust(self, svc, db, galaxy):
        bl = await svc.link_entity_stardust("e1", "sd-1", db)
        assert bl.entity_id == "e1"
        assert bl.stardust_id == "sd-1"

    @pytest.mark.asyncio
    async def test_link_all_unlinked(self, svc, db, galaxy):
        e = _make_entity("e1", name="Redis")
        sd1 = _make_stardust("sd-1", content="Redis is used for caching")
        sd2 = _make_stardust("sd-2", content="Redis handles sessions")
        db.add_all([e, sd1, sd2])
        await db.flush()
        count = await svc.link_all_unlinked("e1", "gal-1", db)
        assert count == 2


# ── KnowledgeIntegrationEngine Tests ────────────────────────────────────────

class TestKnowledgeIntegrationEngine:
    @pytest.fixture
    def engine(self):
        from app.services.knowledge_integration_engine import KnowledgeIntegrationEngine
        return KnowledgeIntegrationEngine()

    @pytest.mark.asyncio
    @patch("app.services.knowledge_integration_engine.nebula_service.log_event", new_callable=AsyncMock)
    async def test_integrate_no_supersession(self, mock_nebula, engine, db, galaxy):
        sd = _make_stardust("sd-1", content="FastAPI is great")
        db.add(sd)
        await db.flush()
        result = await engine.integrate(sd, "gal-1", db)
        assert result["supersessions_processed"] == 0
        assert result["relationships_extracted"] == 0

    @pytest.mark.asyncio
    @patch("app.services.knowledge_integration_engine.nebula_service.log_event", new_callable=AsyncMock)
    async def test_integrate_with_supersession(self, mock_nebula, engine, db, galaxy):
        old = _make_stardust("sd-old", content="Old knowledge")
        new = _make_stardust("sd-new", content="New knowledge", supersedes=json.dumps(["sd-old"]))
        db.add_all([old, new])
        await db.flush()
        result = await engine.integrate(new, "gal-1", db)
        assert result["supersessions_processed"] == 1
        await db.refresh(old)
        assert old.valid_until is not None
        tags = old._context_tags if isinstance(old._context_tags, list) else json.loads(old._context_tags)
        assert "superseded_by:sd-new" in tags

    @pytest.mark.asyncio
    @patch("app.services.knowledge_integration_engine.nebula_service.log_event", new_callable=AsyncMock)
    async def test_integrate_extracts_relationships(self, mock_nebula, engine, db, galaxy):
        e1 = _make_entity("e1", name="FastAPI")
        e2 = _make_entity("e2", name="PostgreSQL")
        sd = _make_stardust("sd-1", content="FastAPI uses PostgreSQL for storage")
        db.add_all([e1, e2, sd, EntityStardust(entity_id="e1", stardust_id="sd-1"),
                     EntityStardust(entity_id="e2", stardust_id="sd-1")])
        await db.flush()
        result = await engine.integrate(sd, "gal-1", db)
        assert result["relationships_extracted"] >= 1

    @pytest.mark.asyncio
    @patch("app.services.knowledge_integration_engine.nebula_service.log_event", new_callable=AsyncMock)
    async def test_integrate_creates_log(self, mock_nebula, engine, db, galaxy):
        sd = _make_stardust("sd-1", content="test")
        db.add(sd)
        await db.flush()
        await engine.integrate(sd, "gal-1", db)
        from sqlalchemy import select
        log = (await db.execute(select(KnowledgeIntegrationLog))).scalar_one()
        assert log.stardust_id == "sd-1"

    @pytest.mark.asyncio
    @patch("app.services.knowledge_integration_engine.nebula_service.log_event", new_callable=AsyncMock)
    async def test_integrate_updates_backlinks(self, mock_nebula, engine, db, galaxy):
        e1 = _make_entity("e1", name="Redis")
        sd = _make_stardust("sd-1", content="Redis caching")
        db.add_all([e1, sd, EntityStardust(entity_id="e1", stardust_id="sd-1")])
        await db.flush()
        await engine.integrate(sd, "gal-1", db)
        from sqlalchemy import select
        bl = (await db.execute(select(EntityBacklink).where(EntityBacklink.entity_id == "e1"))).scalar_one_or_none()
        assert bl is not None


# ── CalibrationService Tests ────────────────────────────────────────────────

class TestCalibrationService:
    @pytest.fixture
    def svc(self):
        from app.services.calibration_service import CalibrationService
        return CalibrationService()

    @pytest.mark.asyncio
    @patch("app.services.calibration_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_confidence_boost(self, mock_nebula, svc, db, galaxy):
        sd = _make_stardust("sd-1", confidence=0.5)
        identity = _make_identity()
        db.add_all([sd, identity])
        await db.commit()
        result = await svc.process_calibration("sess-1", "aid-1", "gal-1",
                                                records_used=["sd-1"], records_retrieved_unused=[],
                                                knowledge_gaps=[], session_outcome="good",
                                                knowledge_quality_score=0.8, db=db)
        assert result["records_boosted"] == 1
        await db.refresh(sd)
        assert sd.confidence == pytest.approx(0.52)

    @pytest.mark.asyncio
    @patch("app.services.calibration_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_confidence_decay(self, mock_nebula, svc, db, galaxy):
        sd = _make_stardust("sd-1", confidence=0.5)
        identity = _make_identity()
        db.add_all([sd, identity])
        await db.commit()
        result = await svc.process_calibration("sess-1", "aid-1", "gal-1",
                                                records_used=[], records_retrieved_unused=["sd-1"],
                                                knowledge_gaps=[], session_outcome=None,
                                                knowledge_quality_score=None, db=db)
        assert result["records_decayed"] == 1
        await db.refresh(sd)
        assert sd.confidence == pytest.approx(0.495)

    @pytest.mark.asyncio
    @patch("app.services.calibration_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_gaps_logged(self, mock_nebula, svc, db, galaxy):
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        result = await svc.process_calibration("sess-1", "aid-1", "gal-1",
                                                records_used=[], records_retrieved_unused=[],
                                                knowledge_gaps=["gap1", "gap2"], session_outcome=None,
                                                knowledge_quality_score=None, db=db)
        assert result["gaps_logged"] == 2

    @pytest.mark.asyncio
    @patch("app.services.calibration_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_ema_quality_update(self, mock_nebula, svc, db, galaxy):
        identity = _make_identity(retrieval_quality_score=0.6)
        db.add(identity)
        await db.commit()
        await svc.process_calibration("sess-1", "aid-1", "gal-1",
                                       records_used=[], records_retrieved_unused=[],
                                       knowledge_gaps=[], session_outcome=None,
                                       knowledge_quality_score=0.9, db=db)
        await db.refresh(identity)
        assert identity.retrieval_quality_score == pytest.approx(0.1 * 0.9 + 0.9 * 0.6)

    @pytest.mark.asyncio
    @patch("app.services.calibration_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_ema_first_value(self, mock_nebula, svc, db, galaxy):
        identity = _make_identity(retrieval_quality_score=0.0)
        db.add(identity)
        await db.commit()
        await svc.process_calibration("sess-1", "aid-1", "gal-1",
                                       records_used=[], records_retrieved_unused=[],
                                       knowledge_gaps=[], session_outcome=None,
                                       knowledge_quality_score=0.8, db=db)
        await db.refresh(identity)
        assert identity.retrieval_quality_score == pytest.approx(0.8)


# ── AgentIdentityService Tests ──────────────────────────────────────────────

class TestAgentIdentityService:
    @pytest.fixture
    def svc(self):
        from app.services.agent_identity_service import AgentIdentityService
        return AgentIdentityService()

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, svc, db, galaxy):
        identity = await svc.get_or_create_identity("gal-1", "new-agent", "claude-sonnet-4-6", db=db)
        assert identity.agent_name == "new-agent"
        assert identity.model_family == "claude"

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, svc, db, galaxy):
        await svc.get_or_create_identity("gal-1", "agent-x", "claude-sonnet-4-6", db=db)
        identity = await svc.get_or_create_identity("gal-1", "agent-x", "gpt-4o", db=db)
        assert identity.current_model == "gpt-4o"
        assert identity.model_family == "gpt"

    @pytest.mark.asyncio
    async def test_start_session(self, svc, db, galaxy):
        identity = _make_identity(total_sessions=0)
        db.add(identity)
        await db.commit()
        session = await svc.start_session(identity, "gal-1", db)
        assert session.agent_identity_id == "aid-1"
        assert identity.total_sessions == 1

    @pytest.mark.asyncio
    async def test_end_session(self, svc, db, galaxy):
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        session = await svc.start_session(identity, "gal-1", db)
        await svc.end_session(session.id, db)
        await db.refresh(session)
        assert session.ended_at is not None

    @pytest.mark.asyncio
    async def test_update_and_get_expertise(self, svc, db, galaxy):
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        await svc.update_expertise("aid-1", ["python", "fastapi"], db)
        expertise = await svc.get_expertise("aid-1", db)
        domains = {e["domain"] for e in expertise}
        assert "python" in domains
        assert "fastapi" in domains

    @pytest.mark.asyncio
    async def test_update_expertise_increments(self, svc, db, galaxy):
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        # First call creates the expertise record
        await svc.update_expertise("aid-1", ["python"], db)
        # Second call: patch datetime.now to return naive datetime matching SQLite storage
        naive_now = datetime(2025, 6, 1, 12, 0, 0)
        from sqlalchemy import select as sel
        exp = (await db.execute(sel(AgentExpertise).where(AgentExpertise.domain == "python"))).scalar_one()
        exp.last_demonstrated = naive_now - timedelta(days=1)  # naive, recent
        await db.commit()
        with patch("app.services.agent_identity_service.datetime") as mock_dt:
            mock_dt.now.return_value = naive_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await svc.update_expertise("aid-1", ["python"], db)
        expertise = await svc.get_expertise("aid-1", db)
        py = [e for e in expertise if e["domain"] == "python"][0]
        assert py["evidence_count"] == 2


# ── OrientationService Tests ────────────────────────────────────────────────

class TestOrientationService:
    @pytest.fixture
    def svc(self):
        from app.services.orientation_service import OrientationService
        return OrientationService()

    @pytest.mark.asyncio
    @patch("app.services.orientation_service.context_service.build_context", new_callable=AsyncMock)
    @patch("app.services.orientation_service.sun_service.get_full_sun", new_callable=AsyncMock)
    async def test_build_orientation_5_layers(self, mock_sun, mock_ctx, svc, db, galaxy):
        mock_sun.return_value = {"identity": {"name": "Test"}, "values": {}, "working_context": {},
                                  "agent_protocol": {"write_rules": [], "read_rules": [],
                                                     "uncertainty_handling": "", "session_start_instruction": "",
                                                     "session_end_instruction": ""}}
        mock_bundle = MagicMock()
        mock_bundle.model_dump.return_value = {"records": []}
        mock_ctx.return_value = mock_bundle
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        result = await svc.build_orientation(identity, "gal-1", None, None, None, db)
        assert "agent_identity" in result
        assert "galaxy_identity" in result
        assert "current_context" in result
        assert "knowledge_state" in result
        assert "operating_protocol" in result
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_get_model_profile_found(self, svc, db, galaxy):
        db.add(ModelProfile(id="mp-1", model_id="claude-sonnet-4-6", display_name="Sonnet",
                            context_window_tokens=200000, optimal_context_tokens=8000))
        await db.commit()
        profile = await svc._get_model_profile("claude-sonnet-4-6", db)
        assert profile is not None
        assert profile.optimal_context_tokens == 8000

    @pytest.mark.asyncio
    async def test_get_model_profile_fallback(self, svc, db, galaxy):
        db.add(ModelProfile(id="mp-u", model_id="__unknown__", display_name="Unknown",
                            context_window_tokens=4000, optimal_context_tokens=2000))
        await db.commit()
        profile = await svc._get_model_profile("nonexistent-model", db)
        assert profile.model_id == "__unknown__"

    @pytest.mark.asyncio
    @patch("app.services.orientation_service.context_service.build_context", new_callable=AsyncMock)
    @patch("app.services.orientation_service.sun_service.get_full_sun", new_callable=AsyncMock)
    async def test_transition_brief_included(self, mock_sun, mock_ctx, svc, db, galaxy):
        mock_sun.return_value = {"identity": {}, "values": {}, "working_context": {},
                                  "agent_protocol": {"write_rules": [], "read_rules": [],
                                                     "uncertainty_handling": "", "session_start_instruction": "",
                                                     "session_end_instruction": ""}}
        mock_bundle = MagicMock()
        mock_bundle.model_dump.return_value = {}
        mock_ctx.return_value = mock_bundle
        identity = _make_identity()
        db.add(identity)
        brief_content = json.dumps({"transition_notice": "You are taking over"})
        db.add(TransitionOrientation(id="to-1", model_switch_id="ms-1", agent_identity_id="aid-1",
                                      from_model="old", to_model="new", orientation_content=brief_content, used=0))
        await db.commit()
        result = await svc.build_orientation(identity, "gal-1", None, None, None, db)
        assert result["transition_brief"] is not None
        assert "taking over" in result["transition_brief"]["transition_notice"]


# ── BrainHealthService Tests ────────────────────────────────────────────────

class TestBrainHealthService:
    @pytest.fixture
    def svc(self):
        from app.services.brain_health_service import BrainHealthService
        return BrainHealthService()

    @pytest.mark.asyncio
    async def test_empty_galaxy(self, svc, db, galaxy):
        identity = _make_identity(retrieval_quality_score=0.0)
        db.add(identity)
        await db.commit()
        result = await svc.get_brain_health(identity, "gal-1", db)
        assert result["total_knowledge_items"] == 0
        assert result["knowledge_freshness"] == 0.0
        assert "overall_health" in result

    @pytest.mark.asyncio
    async def test_with_knowledge(self, svc, db, galaxy):
        identity = _make_identity(retrieval_quality_score=0.8)
        sd = _make_stardust("sd-1", content="Recent knowledge", created_at=datetime.now(timezone.utc))
        db.add_all([identity, sd])
        await db.commit()
        result = await svc.get_brain_health(identity, "gal-1", db)
        assert result["total_knowledge_items"] == 1
        assert result["knowledge_freshness"] == 1.0

    @pytest.mark.asyncio
    async def test_stale_beliefs_detected(self, svc, db, galaxy):
        identity = _make_identity(retrieval_quality_score=0.5)
        sd = _make_stardust("sd-1", content="Old belief", confidence=0.9,
                            last_accessed=datetime.now(timezone.utc) - timedelta(days=60))
        db.add_all([identity, sd])
        await db.commit()
        result = await svc.get_brain_health(identity, "gal-1", db)
        assert len(result["stale_beliefs"]) == 1

    @pytest.mark.asyncio
    async def test_recommendations_low_freshness(self, svc, db, galaxy):
        identity = _make_identity(retrieval_quality_score=0.8)
        sd = _make_stardust("sd-1", content="Old", created_at=datetime.now(timezone.utc) - timedelta(days=90))
        db.add_all([identity, sd])
        await db.commit()
        result = await svc.get_brain_health(identity, "gal-1", db)
        assert any("stale" in r.lower() for r in result["recommended_enrichment"])

    @pytest.mark.asyncio
    async def test_coverage_gaps_from_calibration(self, svc, db, galaxy):
        identity = _make_identity()
        cal = SessionCalibration(id="cal-1", session_id="s1", agent_identity_id="aid-1",
                                  galaxy_id="gal-1", knowledge_gaps=json.dumps(["docker", "k8s"]))
        db.add_all([identity, cal])
        await db.commit()
        result = await svc.get_brain_health(identity, "gal-1", db)
        assert "docker" in result["coverage_gaps"]


# ── GalaxyService Tests ─────────────────────────────────────────────────────

class TestGalaxyService:
    @pytest.mark.asyncio
    @patch("app.services.galaxy_service.get_redis", new_callable=AsyncMock)
    async def test_compute_galaxy_strength_empty(self, mock_redis, db, galaxy):
        mock_redis.return_value = AsyncMock(setex=AsyncMock())
        from app.services.galaxy_service import compute_galaxy_strength
        result = await compute_galaxy_strength("gal-1", db)
        assert result["score"] >= 0
        assert result["grade"] in ("A", "B", "C", "D", "F")
        assert "dimensions" in result
        assert len(result["dimensions"]) == 5

    @pytest.mark.asyncio
    @patch("app.services.galaxy_service.get_redis", new_callable=AsyncMock)
    async def test_compute_galaxy_strength_with_data(self, mock_redis, db, galaxy):
        mock_redis.return_value = AsyncMock(setex=AsyncMock())
        from app.services.galaxy_service import compute_galaxy_strength
        for i in range(5):
            db.add(_make_stardust(f"sd-{i}", content=f"Knowledge {i}"))
        await db.commit()
        result = await compute_galaxy_strength("gal-1", db)
        assert result["score"] > 0

    @pytest.mark.asyncio
    @patch("app.services.galaxy_service.get_redis", new_callable=AsyncMock)
    async def test_compute_galaxy_strength_nonexistent(self, mock_redis, db):
        mock_redis.return_value = AsyncMock(setex=AsyncMock())
        from app.services.galaxy_service import compute_galaxy_strength
        result = await compute_galaxy_strength("nonexistent", db)
        assert result["score"] == 0
        assert result["grade"] == "F"

    @pytest.mark.asyncio
    @patch("app.services.galaxy_service.get_redis", new_callable=AsyncMock)
    async def test_get_galaxy_strength_cache_hit(self, mock_redis):
        cached = json.dumps({"score": 75.0, "grade": "C"})
        mock_redis.return_value = AsyncMock(get=AsyncMock(return_value=cached))
        from app.services.galaxy_service import get_galaxy_strength
        # Need a db but won't be used due to cache hit
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await get_galaxy_strength("gal-1", session)
        await engine.dispose()
        assert result["score"] == 75.0

    @pytest.mark.asyncio
    async def test_score_to_grade(self):
        from app.services.galaxy_service import score_to_grade
        assert score_to_grade(95) == "A"
        assert score_to_grade(85) == "B"
        assert score_to_grade(75) == "C"
        assert score_to_grade(65) == "D"
        assert score_to_grade(50) == "F"


# ── NebulaService Tests ─────────────────────────────────────────────────────

class TestNebulaService:
    @pytest.mark.asyncio
    async def test_log_event(self, db, galaxy):
        from app.services import nebula_service
        event_id = await nebula_service.log_event(
            galaxy_id="gal-1", action_type="TEST_EVENT", initiated_by="test", db=db)
        assert event_id is not None
        from sqlalchemy import select
        log = (await db.execute(select(InteractionLog).where(InteractionLog.id == event_id))).scalar_one()
        assert log.action_type == "TEST_EVENT"

    @pytest.mark.asyncio
    async def test_log_event_with_all_fields(self, db, galaxy):
        from app.services import nebula_service
        event_id = await nebula_service.log_event(
            galaxy_id="gal-1", action_type="WRITE", initiated_by="agent",
            planet_id="pl-1", biome_id="bi-1", region="analytical",
            record_id="sd-1", confidence_delta=0.02, latency_ms=150,
            cache_hit=True, session_id="sess-1", db=db)
        from sqlalchemy import select
        log = (await db.execute(select(InteractionLog).where(InteractionLog.id == event_id))).scalar_one()
        assert log.cache_hit == 1
        assert log.latency_ms == 150

    @pytest.mark.asyncio
    async def test_log_event_cache_hit_false(self, db, galaxy):
        from app.services import nebula_service
        event_id = await nebula_service.log_event(
            galaxy_id="gal-1", action_type="READ", initiated_by="test", cache_hit=False, db=db)
        from sqlalchemy import select
        log = (await db.execute(select(InteractionLog).where(InteractionLog.id == event_id))).scalar_one()
        assert log.cache_hit == 0


# ── ModelSwitchService Tests ────────────────────────────────────────────────

class TestModelSwitchService:
    @pytest.fixture
    def svc(self):
        from app.services.model_switch_service import ModelSwitchService
        return ModelSwitchService()

    @pytest.mark.asyncio
    @patch("app.services.model_switch_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_handle_switch_same_family(self, mock_nebula, svc, db, galaxy):
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        result = await svc.handle_switch(identity, "claude-sonnet-4-6", "claude-opus-4-6", "gal-1", db)
        assert result["continuity_score"] == 0.95

    @pytest.mark.asyncio
    @patch("app.services.model_switch_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_handle_switch_cross_family(self, mock_nebula, svc, db, galaxy):
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        result = await svc.handle_switch(identity, "claude-sonnet-4-6", "gpt-4o", "gal-1", db)
        assert result["continuity_score"] == 0.7

    @pytest.mark.asyncio
    @patch("app.services.model_switch_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_handle_switch_creates_transition(self, mock_nebula, svc, db, galaxy):
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        result = await svc.handle_switch(identity, "claude-sonnet-4-6", "gpt-4o", "gal-1", db)
        assert "transition_orientation_id" in result
        from sqlalchemy import select
        t = (await db.execute(select(TransitionOrientation).where(
            TransitionOrientation.id == result["transition_orientation_id"]))).scalar_one()
        content = json.loads(t.orientation_content)
        assert "transition_notice" in content

    @pytest.mark.asyncio
    @patch("app.services.model_switch_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_generate_transition_brief(self, mock_nebula, svc, db, galaxy):
        identity = _make_identity(total_sessions=10)
        db.add(identity)
        await db.commit()
        brief = await svc._generate_transition_brief(identity, "claude-sonnet-4-6", "gpt-4o", "gal-1", db)
        assert "transition_notice" in brief
        assert "10 sessions" in brief["transition_notice"]
        assert "operating_note" in brief

    @pytest.mark.asyncio
    @patch("app.services.model_switch_service.nebula_service.log_event", new_callable=AsyncMock)
    async def test_handle_switch_logs_to_db(self, mock_nebula, svc, db, galaxy):
        identity = _make_identity()
        db.add(identity)
        await db.commit()
        result = await svc.handle_switch(identity, "old-model", "new-model", "gal-1", db)
        from sqlalchemy import select
        log = (await db.execute(select(ModelSwitchLog).where(ModelSwitchLog.id == result["switch_id"]))).scalar_one()
        assert log.previous_model == "old-model"
        assert log.new_model == "new-model"
