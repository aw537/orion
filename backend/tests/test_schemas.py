"""Unit tests for Pydantic schema validation."""
import pytest
from datetime import datetime, timezone
from app.schemas.stardust import (
    StardustCreate, StardustResponse, StardustUpdate, WriteReceipt,
    ConflictInfo, SearchRecord, SearchResponse, RetrievalMetadata,
    ContextBundle, EntityResponse, PaginatedResponse,
)
from app.schemas.galaxy import GalaxyResponse, PlanetSummary, SunSectionUpdate, GalaxyStatusResponse
from app.schemas.planet import PlanetCreate, PlanetResponse
from app.schemas.biome import BiomeCreate, BiomeResponse, BiomeLifecycleUpdate, GraphNode, GraphEdge
from app.schemas.nebula import NebulaEvent, OnboardingRequest, OnboardingResponse


class TestStardustCreate:
    def test_minimal(self):
        s = StardustCreate(content="test")
        assert s.content == "test"
        assert s.region == "contextual"
        assert s.gravity == "BIOME"
        assert s.context_tags == []

    def test_full(self):
        s = StardustCreate(content="test", planet="Eng", biome="Backend", region="analytical", context_tags=["a"], gravity="PLANET")
        assert s.region == "analytical"
        assert s.gravity == "PLANET"


class TestStardustUpdate:
    def test_all_none(self):
        u = StardustUpdate()
        assert u.content is None
        assert u.context_tags is None

    def test_partial(self):
        u = StardustUpdate(content="new content")
        assert u.content == "new content"
        assert u.gravity is None


class TestWriteReceipt:
    def test_success(self):
        r = WriteReceipt(status="success", stardust_id="s1", biome_id="b1", planet_id="p1")
        assert r.contradiction_check == "clean"
        assert r.chroma_indexed is False
        assert r.contradiction is None

    def test_with_conflict(self):
        conflict = ConflictInfo(conflict_id="c1", conflict_type="FACTUAL", existing_record_id="s0")
        r = WriteReceipt(status="written_with_conflict", stardust_id="s1", biome_id="b1", planet_id="p1", contradiction=conflict)
        assert r.contradiction.conflict_id == "c1"
        assert r.contradiction.recommended_action == "COEXIST"


class TestSearchRecord:
    def test_valid(self):
        r = SearchRecord(id="s1", content="test", region="analytical", biome_name="B", planet_name="P", confidence=0.8, valid_from=datetime.now(timezone.utc), valid_until=None, context_tags=["a"], source_agent="agent", access_count=5)
        assert r.confidence == 0.8


class TestRetrievalMetadata:
    def test_defaults(self):
        m = RetrievalMetadata()
        assert m.cache_hits == 0
        assert m.sources_checked == []
        assert m.retrieval_latency_ms == 0


class TestContextBundle:
    def test_minimal(self):
        b = ContextBundle(bundle_id="b1", generated_at=datetime.now(timezone.utc))
        assert b.sun_context == {}
        assert b.planet_context == {}


class TestPaginatedResponse:
    def test_defaults(self):
        p = PaginatedResponse()
        assert p.items == []
        assert p.total == 0
        assert p.limit == 50


class TestPlanetSummary:
    def test_valid(self):
        p = PlanetSummary(id="p1", name="Engineering", stardust_count=100, health_status="healthy")
        assert p.active_biomes == []


class TestGalaxyStatusResponse:
    def test_valid(self):
        g = GalaxyStatusResponse(galaxy_id="g1", galaxy_name="My Galaxy", strength_score=42.0, total_stardust=100, total_entities=50, planets=[])
        assert g.contradiction_count_unresolved == 0
        assert g.active_session_agents == 0


class TestPlanetCreate:
    def test_defaults(self):
        p = PlanetCreate(name="Test")
        assert p.color == "#6D28D9"
        assert p.description is None


class TestBiomeCreate:
    def test_minimal(self):
        b = BiomeCreate(name="Backend")
        assert b.description is None


class TestBiomeLifecycleUpdate:
    def test_valid(self):
        u = BiomeLifecycleUpdate(lifecycle_state="ACTIVE")
        assert u.lifecycle_state == "ACTIVE"


class TestGraphNode:
    def test_defaults(self):
        n = GraphNode(id="n1", label="test", type="stardust")
        assert n.size == 1.0
        assert n.color is None
        assert n.metadata == {}


class TestGraphEdge:
    def test_valid(self):
        e = GraphEdge(source="n1", target="n2", type="entity_link")
        assert e.type == "entity_link"


class TestNebulaEvent:
    def test_valid(self):
        e = NebulaEvent(event_id=1, action_type="WRITE", initiated_by="agent", timestamp=datetime.now(timezone.utc))
        assert e.planet_id is None
        assert e.metadata == {}


class TestOnboardingRequest:
    def test_defaults(self):
        r = OnboardingRequest(role="Developer")
        assert r.first_biome_name == "General"
        assert r.import_path is None


class TestOnboardingResponse:
    def test_valid(self):
        r = OnboardingResponse(galaxy_id="g1", planets=["Engineering", "Personal"], first_biome_id="b1")
        assert r.import_started is False


class TestEntityResponse:
    def test_valid(self):
        e = EntityResponse(id="e1", name="FastAPI", entity_type="tool", tier=1, profile={}, mention_count=5, first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc))
        assert e.tier == 1


class TestSunSectionUpdate:
    def test_valid(self):
        u = SunSectionUpdate(content='["value1", "value2"]')
        assert u.content == '["value1", "value2"]'
