"""Unit tests for MCP tool functions (memory.*, brain.*, sun.*)."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def NO_GALAXY_FOR(mod):
    return patch(f"app.mcp.{mod}._get_galaxy_id", new_callable=AsyncMock, return_value=None)

def HAS_GALAXY_FOR(mod):
    return patch(f"app.mcp.{mod}._get_galaxy_id", new_callable=AsyncMock, return_value="gal-1")

# Convenience aliases
NO_GALAXY = NO_GALAXY_FOR("tools_memory")
HAS_GALAXY = HAS_GALAXY_FOR("tools_memory")
NO_GALAXY_BRAIN = NO_GALAXY_FOR("tools_brain")
HAS_GALAXY_BRAIN = HAS_GALAXY_FOR("tools_brain")
NO_GALAXY_SUN = NO_GALAXY_FOR("tools_sun")
HAS_GALAXY_SUN = HAS_GALAXY_FOR("tools_sun")

def _mock_receipt(**overrides):
    defaults = dict(
        status="ok", stardust_id="sd-1", biome_id="bio-1", planet_id="pl-1",
        layer="cache", cache_ttl_seconds=28800, nebula_event_id=None,
        contradiction_check="clean", promotion_eligible=False, chroma_indexed=False,
        contradiction=None,
    )
    defaults.update(overrides)
    m = MagicMock()
    m.model_dump.return_value = defaults
    return m

def _mock_search_response(records=None):
    m = MagicMock()
    m.model_dump.return_value = {"records": records or [], "retrieval_metadata": {}}
    return m

def _mock_context_bundle():
    m = MagicMock()
    m.model_dump.return_value = {"bundle_id": "b-1", "generated_at": "2026-01-01T00:00:00Z", "sun_context": {}, "planet_context": {}, "biome_context": {}, "retrieval_metadata": {}}
    return m


# ===================================================================
# _get_galaxy_id utility
# ===================================================================
class TestGetGalaxyId:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_galaxy(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("app.mcp.utils.async_session", return_value=mock_session):
            from app.mcp.utils import get_galaxy_id
            assert await get_galaxy_id() is None

    @pytest.mark.asyncio
    async def test_returns_id_when_galaxy_exists(self):
        galaxy = MagicMock(id="gal-42")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = galaxy
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("app.mcp.utils.async_session", return_value=mock_session):
            from app.mcp.utils import get_galaxy_id
            assert await get_galaxy_id() == "gal-42"


# ===================================================================
# memory.* tools
# ===================================================================
class TestMemoryWrite:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY:
            from app.mcp.tools_memory import memory_write
            result = await memory_write("test", "Engineering")
            assert result == {"status": "error", "message": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_happy_path(self):
        receipt = _mock_receipt()
        mock_planet = MagicMock(id="pl-1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_planet
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY, \
             patch("app.mcp.tools_memory.stardust_service.write_stardust", new_callable=AsyncMock, return_value=receipt), \
             patch("app.mcp.tools_memory.async_session", return_value=mock_session), \
             patch("app.mcp.tools_memory.stardust_service.run_async_tasks", new_callable=AsyncMock):
            from app.mcp.tools_memory import memory_write
            result = await memory_write("content", "Engineering")
            assert result["status"] == "ok"
            assert result["stardust_id"] == "sd-1"


class TestMemorySearch:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY:
            from app.mcp.tools_memory import memory_search
            result = await memory_search("query")
            assert result["records"] == []
            assert "error" in result["retrieval_metadata"]

    @pytest.mark.asyncio
    async def test_happy_path(self):
        with HAS_GALAXY, \
             patch("app.mcp.tools_memory.search_service.search", new_callable=AsyncMock, return_value=_mock_search_response()):
            from app.mcp.tools_memory import memory_search
            result = await memory_search("query")
            assert "records" in result

    @pytest.mark.asyncio
    async def test_with_filters(self):
        with HAS_GALAXY, \
             patch("app.mcp.tools_memory.search_service.search", new_callable=AsyncMock, return_value=_mock_search_response()) as mock_search:
            from app.mcp.tools_memory import memory_search
            await memory_search("q", planet="Eng", biome="backend", region="analytical", limit=3)
            mock_search.assert_called_once_with("q", "gal-1", planet_name="Eng", biome_name="backend", region="analytical", limit=3)


class TestMemoryContext:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY:
            from app.mcp.tools_memory import memory_context
            result = await memory_context()
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_happy_path(self):
        with HAS_GALAXY, \
             patch("app.mcp.tools_memory.context_service.build_context", new_callable=AsyncMock, return_value=_mock_context_bundle()):
            from app.mcp.tools_memory import memory_context
            result = await memory_context(planet="Eng", max_tokens=2000)
            assert "bundle_id" in result


class TestMemoryStatus:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("app.mcp.tools_memory.async_session", return_value=mock_session):
            from app.mcp.tools_memory import memory_status
            result = await memory_status()
            assert result == {"error": "No galaxy found"}


class TestMemoryEntityGet:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY:
            from app.mcp.tools_memory import memory_entity_get
            result = await memory_entity_get("FastAPI")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_entity_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY, \
             patch("app.mcp.tools_memory.async_session", return_value=mock_session):
            from app.mcp.tools_memory import memory_entity_get
            result = await memory_entity_get("NonExistent")
            assert "not found" in result["error"]


# ===================================================================
# brain.* tools
# ===================================================================
class TestBrainOrient:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_BRAIN:
            from app.mcp.tools_brain import brain_orient
            result = await brain_orient("agent-1", "claude-sonnet-4")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_happy_path(self):
        mock_identity = MagicMock(id="aid-1", total_sessions=0)
        orientation = {"identity": {}, "galaxy": {}, "context": {}}
        mock_db = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_BRAIN, \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session), \
             patch("app.services.agent_identity_service.agent_identity_service.get_or_create_identity", new_callable=AsyncMock, return_value=mock_identity), \
             patch("app.services.orientation_service.orientation_service.build_orientation", new_callable=AsyncMock, return_value=orientation):
            from app.mcp.tools_brain import brain_orient
            result = await brain_orient("agent-1", "claude-sonnet-4")
            assert "identity" in result


class TestBrainThink:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_BRAIN:
            from app.mcp.tools_brain import brain_think
            result = await brain_think("insight", "Engineering")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_happy_path(self):
        receipt = _mock_receipt()
        mock_planet = MagicMock(id="pl-1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_planet
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_BRAIN, \
             patch("app.services.stardust_service.write_stardust", new_callable=AsyncMock, return_value=receipt), \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session), \
             patch("app.services.stardust_service.run_async_tasks", new_callable=AsyncMock):
            from app.mcp.tools_brain import brain_think
            result = await brain_think("insight", "Engineering", reasoning="because X")
            assert result["stardust_id"] == "sd-1"
            assert result["reasoning_stored"] is True

    @pytest.mark.asyncio
    async def test_with_supersedes(self):
        receipt = _mock_receipt()
        mock_planet = MagicMock(id="pl-1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_planet
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_BRAIN, \
             patch("app.services.stardust_service.write_stardust", new_callable=AsyncMock, return_value=receipt), \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session), \
             patch("app.services.stardust_service.run_async_tasks", new_callable=AsyncMock):
            from app.mcp.tools_brain import brain_think
            result = await brain_think("new insight", "Eng", supersedes=["sd-old-1", "sd-old-2"])
            assert result["supersedes_count"] == 2


class TestBrainRecall:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_BRAIN:
            from app.mcp.tools_brain import brain_recall
            result = await brain_recall("query")
            assert result["records"] == []
            assert "error" in result["retrieval_metadata"]

    @pytest.mark.asyncio
    async def test_happy_path(self):
        with HAS_GALAXY_BRAIN, \
             patch("app.services.search_service.search", new_callable=AsyncMock, return_value=_mock_search_response()):
            from app.mcp.tools_brain import brain_recall
            result = await brain_recall("query", cognitive_mode="analytical")
            assert "records" in result
            assert result["cognitive_mode"] == "analytical"

    @pytest.mark.asyncio
    async def test_context_window_prepended(self):
        with HAS_GALAXY_BRAIN, \
             patch("app.services.search_service.search", new_callable=AsyncMock, return_value=_mock_search_response()) as mock_search:
            from app.mcp.tools_brain import brain_recall
            result = await brain_recall("query", context_window="refactoring auth")
            mock_search.assert_called_once()
            assert mock_search.call_args[0][0] == "refactoring auth query"
            assert result["context_window_used"] is True


class TestBrainCalibrate:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_BRAIN:
            from app.mcp.tools_brain import brain_calibrate
            result = await brain_calibrate("sess-1", ["sd-1"])
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_session_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_BRAIN, \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session):
            from app.mcp.tools_brain import brain_calibrate
            result = await brain_calibrate("bad-sess", ["sd-1"])
            assert "not found" in result["error"]


class TestBrainHealth:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_BRAIN:
            from app.mcp.tools_brain import brain_health
            result = await brain_health("agent-1")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_BRAIN, \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session):
            from app.mcp.tools_brain import brain_health
            result = await brain_health("unknown-agent")
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_happy_path(self):
        mock_identity = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_identity
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        health_report = {"overall_score": 0.85, "freshness": 0.9}
        with HAS_GALAXY_BRAIN, \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session), \
             patch("app.services.brain_health_service.brain_health_service.get_brain_health", new_callable=AsyncMock, return_value=health_report):
            from app.mcp.tools_brain import brain_health
            result = await brain_health("agent-1")
            assert result["overall_score"] == 0.85


class TestBrainKnow:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_BRAIN:
            from app.mcp.tools_brain import brain_know
            result = await brain_know("FastAPI")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_concept_not_entity(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_BRAIN, \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session), \
             patch("app.services.search_service.search", new_callable=AsyncMock, return_value=_mock_search_response()):
            from app.mcp.tools_brain import brain_know
            result = await brain_know("unknown-concept")
            assert result["entity"] is None
            assert result["concept"] == "unknown-concept"


class TestBrainGraphQuery:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_BRAIN:
            from app.mcp.tools_brain import brain_graph_query
            result = await brain_graph_query("FastAPI")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_entity_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_BRAIN, \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session):
            from app.mcp.tools_brain import brain_graph_query
            result = await brain_graph_query("Nope")
            assert "not found" in result["error"]


class TestBrainFindPath:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_BRAIN:
            from app.mcp.tools_brain import brain_find_path
            result = await brain_find_path("A", "B")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_source_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_BRAIN, \
             patch("app.mcp.tools_brain.async_session", return_value=mock_session):
            from app.mcp.tools_brain import brain_find_path
            result = await brain_find_path("Missing", "Also Missing")
            assert "not found" in result["error"]


# ===================================================================
# sun.* tools
# ===================================================================
class TestSunRead:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_SUN:
            from app.mcp.tools_sun import sun_read
            result = await sun_read()
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_full_sun(self):
        full = {"identity": {}, "working_context": {}, "agent_protocol": {}}
        with HAS_GALAXY_SUN, \
             patch("app.mcp.tools_sun.sun_service.get_full_sun", new_callable=AsyncMock, return_value=full):
            from app.mcp.tools_sun import sun_read
            result = await sun_read()
            assert "identity" in result

    @pytest.mark.asyncio
    async def test_specific_section(self):
        section_data = {"content": {"name": "Orion"}}
        mock_db = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_SUN, \
             patch("app.mcp.tools_sun.async_session", return_value=mock_session), \
             patch("app.mcp.tools_sun.sun_service.get_section", new_callable=AsyncMock, return_value=section_data):
            from app.mcp.tools_sun import sun_read
            result = await sun_read(section="identity")
            assert result == section_data

    @pytest.mark.asyncio
    async def test_section_not_found(self):
        mock_db = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_SUN, \
             patch("app.mcp.tools_sun.async_session", return_value=mock_session), \
             patch("app.mcp.tools_sun.sun_service.get_section", new_callable=AsyncMock, return_value=None):
            from app.mcp.tools_sun import sun_read
            result = await sun_read(section="nonexistent")
            assert "not found" in result["error"]


class TestSunUpdate:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_SUN:
            from app.mcp.tools_sun import sun_update
            result = await sun_update("identity", {"name": "X"}, "update name")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_happy_path(self):
        update_result = {"status": "ok", "section": "identity"}
        mock_db = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_SUN, \
             patch("app.mcp.tools_sun.async_session", return_value=mock_session), \
             patch("app.mcp.tools_sun.sun_service.update_section", new_callable=AsyncMock, return_value=update_result) as mock_update:
            from app.mcp.tools_sun import sun_update
            result = await sun_update("identity", {"name": "X"}, "update name")
            assert result["status"] == "ok"
            mock_update.assert_called_once_with("gal-1", "identity", {"name": "X"}, "agent", "update name", mock_db)


class TestSunWorkingContext:
    @pytest.mark.asyncio
    async def test_no_galaxy(self):
        with NO_GALAXY_SUN:
            from app.mcp.tools_sun import sun_working_context
            result = await sun_working_context(current_focus="testing")
            assert result == {"error": "No galaxy found"}

    @pytest.mark.asyncio
    async def test_section_missing(self):
        mock_db = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_SUN, \
             patch("app.mcp.tools_sun.async_session", return_value=mock_session), \
             patch("app.mcp.tools_sun.sun_service.get_section", new_callable=AsyncMock, return_value=None):
            from app.mcp.tools_sun import sun_working_context
            result = await sun_working_context(current_focus="testing")
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_updates_focus(self):
        existing = {"content": {"current_focus": "old", "blockers": [], "hot_biomes": []}}
        update_result = {"status": "ok"}
        mock_db = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with HAS_GALAXY_SUN, \
             patch("app.mcp.tools_sun.async_session", return_value=mock_session), \
             patch("app.mcp.tools_sun.sun_service.get_section", new_callable=AsyncMock, return_value=existing), \
             patch("app.mcp.tools_sun.sun_service.update_section", new_callable=AsyncMock, return_value=update_result) as mock_update:
            from app.mcp.tools_sun import sun_working_context
            result = await sun_working_context(current_focus="new focus", add_blocker="blocked on X")
            assert result["status"] == "ok"
            call_content = mock_update.call_args[0][2]
            assert call_content["current_focus"] == "new focus"
            assert "blocked on X" in call_content["blockers"]
