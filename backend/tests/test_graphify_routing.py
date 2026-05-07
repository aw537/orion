"""Tests for Graphify semantic Planet routing: adapter, engine, should_run_graphify, inbox."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.adapters.graphify_adapter import GraphifyAdapter, GraphifyAnalysis, _EMPTY
from app.services.planet_assignment_engine import (
    PlanetAssignmentEngine, PlanetAssignment, should_run_graphify,
    GRAPHIFY_MIN_CONFIDENCE, ENTITY_MIN_CONFIDENCE, KEYWORD_MIN_CONFIDENCE,
)
from app.models import Base, Galaxy, Planet, Biome, Entity, Stardust, RoutingLog
from app.models.brain import EntityBacklink

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(TEST_DB_URL, echo=False, connect_args={"check_same_thread": False})
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def galaxy_with_planets(db):
    """Galaxy with Engineering (has description) + Personal planets + one biome."""
    gid = str(uuid4())
    db.add(Galaxy(id=gid, name="Test", created_at=datetime.now(timezone.utc),
                  strength_score=0.5, total_nodes=0, schema_version="0.1.0"))
    eng = Planet(id=str(uuid4()), galaxy_id=gid, name="Engineering",
                 description="code architecture api backend frontend deployment infrastructure",
                 stardust_count=0, health_status="healthy")
    personal = Planet(id=str(uuid4()), galaxy_id=gid, name="Personal",
                      description="goals habits journal reflection personal growth",
                      stardust_count=0, health_status="healthy")
    db.add_all([eng, personal])
    biome = Biome(id=str(uuid4()), planet_id=eng.id, galaxy_id=gid,
                  name="Backend", lifecycle_state="ACTIVE")
    db.add(biome)
    await db.commit()
    return {"galaxy_id": gid, "eng": eng, "personal": personal, "biome": biome}


# ═══════════════════════════════════════════════════════════════════════════════
# should_run_graphify
# ═══════════════════════════════════════════════════════════════════════════════

class TestShouldRunGraphify:
    def test_short_prose_returns_false(self):
        assert should_run_graphify("A short note about something.") is False

    def test_long_prose_returns_true(self):
        content = " ".join(["word"] * 501)
        assert should_run_graphify(content) is True

    def test_code_content_returns_true(self):
        content = "\n".join([
            "import os", "import sys", "",
            "def main():", "    pass", "",
            "def helper():", "    pass", "",
            "class Foo:", "    pass", "",
            "class Bar:", "    pass",
        ])
        assert should_run_graphify(content) is True

    def test_code_blocks_in_markdown_returns_true(self):
        content = "Some text\n```python\nprint('hello')\n```\nMore text\n```js\nconsole.log('hi')\n```"
        assert should_run_graphify(content) is True

    def test_source_file_extension_returns_true(self):
        assert should_run_graphify("x = 1", filename="main.py") is True
        assert should_run_graphify("x = 1", filename="app.ts") is True

    def test_non_source_extension_returns_false(self):
        assert should_run_graphify("short note", filename="notes.txt") is False

    def test_no_filename_short_content_returns_false(self):
        assert should_run_graphify("Just a thought.") is False


# ═══════════════════════════════════════════════════════════════════════════════
# GraphifyAdapter
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphifyAdapter:
    def test_graphify_not_installed_returns_empty(self):
        adapter = GraphifyAdapter()
        with patch.dict("sys.modules", {"graphifyy": None}):
            result = adapter._run_sync("some content", None, True)
        assert result.graphify_ran is False
        assert result.primary_cluster == "unknown"

    def test_parse_valid_graph_data(self):
        adapter = GraphifyAdapter()
        data = {
            "nodes": [
                {"id": "n1", "label": "FastAPI", "community_label": "api_layer", "confidence": 0.9},
                {"id": "n2", "label": "SQLAlchemy", "community_label": "api_layer", "confidence": 0.85},
                {"id": "n3", "label": "Redis", "community_label": "caching", "confidence": 0.8},
            ],
            "edges": [
                {"source": "n1", "target": "n2", "type": "uses"},
                {"source": "n1", "target": "n3", "type": "connects_to"},
            ],
            "communities": {
                "0": {"label": "api_layer", "size": 2, "hub_nodes": ["FastAPI", "SQLAlchemy"]},
                "1": {"label": "caching", "size": 1, "hub_nodes": ["Redis"]},
            },
            "metadata": {"content_type": "code", "languages_detected": ["python"]},
        }
        result = adapter._parse(data, "test content")
        assert result.graphify_ran is True
        assert result.primary_cluster == "api_layer"
        assert result.cluster_confidence > 0
        assert "caching" in result.secondary_clusters
        assert "FastAPI" in result.extracted_concepts
        assert result.content_type == "code"
        assert "python" in result.languages_detected
        assert len(result.extracted_relationships) == 2

    def test_parse_empty_nodes_returns_unknown(self):
        adapter = GraphifyAdapter()
        result = adapter._parse({"nodes": [], "edges": []}, "")
        assert result.primary_cluster == "unknown"
        assert result.cluster_confidence == 0.0
        assert result.graphify_ran is True

    @pytest.mark.asyncio
    async def test_caching_returns_same_result(self):
        adapter = GraphifyAdapter()
        mock_result = GraphifyAnalysis(
            primary_cluster="test", cluster_confidence=0.9, graphify_ran=True
        )
        with patch.object(adapter, "_run_sync", return_value=mock_result) as mock_run:
            r1 = await adapter.analyze("same content")
            r2 = await adapter.analyze("same content")
        assert r1 is r2
        mock_run.assert_called_once()  # only called once due to cache

    @pytest.mark.asyncio
    async def test_different_content_not_cached(self):
        adapter = GraphifyAdapter()
        mock_result = GraphifyAnalysis(primary_cluster="t", cluster_confidence=0.5, graphify_ran=True)
        with patch.object(adapter, "_run_sync", return_value=mock_result) as mock_run:
            await adapter.analyze("content A")
            await adapter.analyze("content B")
        assert mock_run.call_count == 2

    def test_infer_ext_python(self):
        assert GraphifyAdapter._infer_ext("def foo():\n    import os", None) == ".py"

    def test_infer_ext_js(self):
        assert GraphifyAdapter._infer_ext("const x = 1;", None) == ".js"

    def test_infer_ext_from_filename(self):
        assert GraphifyAdapter._infer_ext("anything", "main.go") == ".go"

    def test_infer_ext_default_md(self):
        assert GraphifyAdapter._infer_ext("just prose", None) == ".md"


# ═══════════════════════════════════════════════════════════════════════════════
# PlanetAssignmentEngine — caller suggestion (Strategy 4)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCallerSuggestionStrategy:
    @pytest.mark.asyncio
    async def test_caller_planet_used_as_fallback(self, db, galaxy_with_planets):
        g = galaxy_with_planets
        engine = PlanetAssignmentEngine()
        result = await engine.assign(
            content="short note", galaxy_id=g["galaxy_id"],
            caller_planet="Engineering", caller_biome=None,
            filename=None, db=db,
        )
        assert result.method == "caller_context"
        assert result.planet.name == "Engineering"
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_caller_planet_with_biome(self, db, galaxy_with_planets):
        g = galaxy_with_planets
        engine = PlanetAssignmentEngine()
        result = await engine.assign(
            content="short note", galaxy_id=g["galaxy_id"],
            caller_planet="Engineering", caller_biome="Backend",
            filename=None, db=db,
        )
        assert result.method == "caller_context"
        assert result.biome is not None
        assert result.biome.name == "Backend"

    @pytest.mark.asyncio
    async def test_nonexistent_caller_planet_falls_to_inbox(self, db, galaxy_with_planets):
        g = galaxy_with_planets
        engine = PlanetAssignmentEngine()
        result = await engine.assign(
            content="short note", galaxy_id=g["galaxy_id"],
            caller_planet="Nonexistent", caller_biome=None,
            filename=None, db=db,
        )
        assert result.method == "inbox_fallback"
        assert result.confidence == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# PlanetAssignmentEngine — inbox fallback (Strategy 5)
# ═══════════════════════════════════════════════════════════════════════════════

class TestInboxFallback:
    @pytest.mark.asyncio
    async def test_no_caller_no_match_goes_to_inbox(self, db, galaxy_with_planets):
        g = galaxy_with_planets
        engine = PlanetAssignmentEngine()
        result = await engine.assign(
            content="xyzzy", galaxy_id=g["galaxy_id"],
            caller_planet=None, caller_biome=None,
            filename=None, db=db,
        )
        assert result.method == "inbox_fallback"
        assert result.confidence == 0.0
        assert result.biome is not None
        assert result.biome.is_inbox is True

    @pytest.mark.asyncio
    async def test_inbox_created_once(self, db, galaxy_with_planets):
        g = galaxy_with_planets
        engine = PlanetAssignmentEngine()
        r1 = await engine.assign(content="a", galaxy_id=g["galaxy_id"],
                                  caller_planet=None, caller_biome=None, filename=None, db=db)
        r2 = await engine.assign(content="b", galaxy_id=g["galaxy_id"],
                                  caller_planet=None, caller_biome=None, filename=None, db=db)
        assert r1.biome.id == r2.biome.id  # same inbox reused

    @pytest.mark.asyncio
    async def test_empty_galaxy_creates_inbox_planet(self, db):
        gid = str(uuid4())
        db.add(Galaxy(id=gid, name="Empty", created_at=datetime.now(timezone.utc),
                      strength_score=0.0, total_nodes=0, schema_version="0.1.0"))
        await db.commit()
        engine = PlanetAssignmentEngine()
        result = await engine.assign(content="test", galaxy_id=gid,
                                      caller_planet=None, caller_biome=None, filename=None, db=db)
        assert result.method == "inbox_fallback"
        assert result.planet.name == "Inbox"
        assert result.biome.is_inbox is True


# ═══════════════════════════════════════════════════════════════════════════════
# PlanetAssignmentEngine — keyword strategy (Strategy 3)
# ═══════════════════════════════════════════════════════════════════════════════

class TestKeywordStrategy:
    def test_keyword_match_returns_best_planet(self):
        engine = PlanetAssignmentEngine()
        eng = MagicMock(spec=Planet)
        eng.name = "Engineering"
        eng.description = "code architecture api backend frontend deployment infrastructure"
        eng.id = "eng-id"
        personal = MagicMock(spec=Planet)
        personal.name = "Personal"
        personal.description = "goals habits journal reflection personal growth"
        personal.id = "pers-id"

        # Need heavy overlap: 6 of 7 description words to get score above threshold
        result = engine._strategy_keyword(
            "code architecture api backend frontend deployment infrastructure refactor",
            [eng, personal],
        )
        assert result is not None
        assert result.planet.name == "Engineering"
        assert result.method == "keyword_match"

    def test_keyword_no_match_returns_none(self):
        engine = PlanetAssignmentEngine()
        p = MagicMock(spec=Planet)
        p.name = "Engineering"
        p.description = "code architecture api"
        p.id = "id"
        result = engine._strategy_keyword("xyzzy foobar baz", [p])
        assert result is None

    def test_keyword_no_description_skipped(self):
        engine = PlanetAssignmentEngine()
        p = MagicMock(spec=Planet)
        p.name = "Empty"
        p.description = None
        p.id = "id"
        result = engine._strategy_keyword("anything here", [p])
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# PlanetAssignmentEngine — graphify strategy (Strategy 1)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphifyStrategy:
    @pytest.mark.asyncio
    async def test_unknown_cluster_returns_none(self, db, galaxy_with_planets):
        engine = PlanetAssignmentEngine()
        analysis = GraphifyAnalysis(primary_cluster="unknown", cluster_confidence=0.9)
        planets = await engine._get_planets(galaxy_with_planets["galaxy_id"], db)
        result = await engine._strategy_graphify(analysis, planets, db)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_cluster_returns_none(self, db, galaxy_with_planets):
        engine = PlanetAssignmentEngine()
        analysis = GraphifyAnalysis(primary_cluster="", cluster_confidence=0.9)
        planets = await engine._get_planets(galaxy_with_planets["galaxy_id"], db)
        result = await engine._strategy_graphify(analysis, planets, db)
        assert result is None

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_none(self, db, galaxy_with_planets):
        engine = PlanetAssignmentEngine()
        analysis = GraphifyAnalysis(primary_cluster="api_layer", cluster_confidence=0.9)
        planets = await engine._get_planets(galaxy_with_planets["galaxy_id"], db)
        with patch("app.services.planet_assignment_engine.get_embedding_provider") as mock_prov:
            mock_prov.return_value.embed = AsyncMock(side_effect=Exception("no embeddings"))
            result = await engine._strategy_graphify(analysis, planets, db)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# PlanetAssignmentEngine — assign() integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestAssignIntegration:
    @pytest.mark.asyncio
    async def test_assign_always_returns_assignment(self, db, galaxy_with_planets):
        """assign() must never raise — always returns a PlanetAssignment."""
        g = galaxy_with_planets
        engine = PlanetAssignmentEngine()
        for content in ["", "x", "a normal sentence", " ".join(["word"] * 100)]:
            result = await engine.assign(
                content=content, galaxy_id=g["galaxy_id"],
                caller_planet=None, caller_biome=None, filename=None, db=db,
            )
            assert isinstance(result, PlanetAssignment)
            assert result.planet is not None
            assert result.method in (
                "graphify_cluster", "entity_routing", "keyword_match",
                "caller_context", "inbox_fallback",
            )

    @pytest.mark.asyncio
    async def test_override_caller_set_when_engine_disagrees(self, db, galaxy_with_planets):
        """When caller says Personal but keyword match says Engineering, override_caller is True."""
        g = galaxy_with_planets
        engine = PlanetAssignmentEngine()
        # Content with strong Engineering keywords
        content = "refactor the api backend code architecture deployment infrastructure"
        result = await engine.assign(
            content=content, galaxy_id=g["galaxy_id"],
            caller_planet="Personal", caller_biome=None, filename=None, db=db,
        )
        if result.method == "keyword_match":
            assert result.override_caller is True
            assert result.planet.name == "Engineering"

    @pytest.mark.asyncio
    async def test_explicit_planet_still_works(self, db, galaxy_with_planets):
        """Explicit planet with no better match uses caller_context."""
        g = galaxy_with_planets
        engine = PlanetAssignmentEngine()
        result = await engine.assign(
            content="random gibberish xyzzy", galaxy_id=g["galaxy_id"],
            caller_planet="Personal", caller_biome=None, filename=None, db=db,
        )
        assert result.method == "caller_context"
        assert result.planet.name == "Personal"


# ═══════════════════════════════════════════════════════════════════════════════
# RoutingLog model
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoutingLogModel:
    @pytest.mark.asyncio
    async def test_routing_log_created(self, db, galaxy_with_planets):
        from sqlalchemy import insert, select
        g = galaxy_with_planets
        stardust_id = str(uuid4())
        db.add(Stardust(
            id=stardust_id, biome_id=g["biome"].id, planet_id=g["eng"].id,
            galaxy_id=g["galaxy_id"], content="test",
            _context_tags=[], supersedes=None,
        ))
        await db.flush()
        db.add(RoutingLog(
            galaxy_id=g["galaxy_id"], stardust_id=stardust_id,
            assigned_planet_id=g["eng"].id, routing_method="caller_suggestion",
            confidence=0.5, reasoning="test",
        ))
        await db.commit()
        row = (await db.execute(
            select(RoutingLog).where(RoutingLog.stardust_id == stardust_id)
        )).scalar_one()
        assert row.routing_method == "caller_suggestion"
        assert row.confidence == 0.5
        assert row.corrected_planet_id is None

    @pytest.mark.asyncio
    async def test_routing_log_correction(self, db, galaxy_with_planets):
        from sqlalchemy import select
        g = galaxy_with_planets
        stardust_id = str(uuid4())
        db.add(Stardust(
            id=stardust_id, biome_id=g["biome"].id, planet_id=g["eng"].id,
            galaxy_id=g["galaxy_id"], content="test",
            _context_tags=[], supersedes=None,
        ))
        await db.flush()
        log = RoutingLog(
            galaxy_id=g["galaxy_id"], stardust_id=stardust_id,
            assigned_planet_id=g["eng"].id, routing_method="inbox_fallback",
            confidence=0.0, reasoning="low confidence",
        )
        db.add(log)
        await db.commit()
        # Simulate correction
        log.corrected_planet_id = g["personal"].id
        log.corrected_by = "user"
        log.corrected_at = datetime.now(timezone.utc)
        await db.commit()
        row = (await db.execute(
            select(RoutingLog).where(RoutingLog.stardust_id == stardust_id)
        )).scalar_one()
        assert row.corrected_planet_id == g["personal"].id
        assert row.corrected_by == "user"


# ═══════════════════════════════════════════════════════════════════════════════
# Biome.is_inbox
# ═══════════════════════════════════════════════════════════════════════════════

class TestBiomeIsInbox:
    @pytest.mark.asyncio
    async def test_default_is_inbox_false(self, db, galaxy_with_planets):
        from sqlalchemy import select
        g = galaxy_with_planets
        biome = (await db.execute(select(Biome).where(Biome.id == g["biome"].id))).scalar_one()
        assert biome.is_inbox is False

    @pytest.mark.asyncio
    async def test_inbox_biome_created_with_flag(self, db, galaxy_with_planets):
        g = galaxy_with_planets
        inbox = Biome(
            id=str(uuid4()), planet_id=g["eng"].id, galaxy_id=g["galaxy_id"],
            name="Inbox", is_inbox=True, lifecycle_state="SEED",
        )
        db.add(inbox)
        await db.commit()
        from sqlalchemy import select
        row = (await db.execute(select(Biome).where(Biome.is_inbox == True))).scalar_one()
        assert row.name == "Inbox"
