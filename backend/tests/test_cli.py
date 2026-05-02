"""Unit tests for the Orion CLI — all commands tested via Click's CliRunner."""
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from app.cli import cli

runner = CliRunner()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or json.dumps(json_data or {})
    return resp


GALAXY_STATUS = {
    "galaxy_id": "g1", "galaxy_name": "Dev Galaxy", "strength_score": 42.5,
    "total_stardust": 100, "total_entities": 30, "contradiction_count_unresolved": 2,
    "planets": [
        {"id": "p1", "name": "Engineering", "stardust_count": 80, "active_biomes": ["Backend", "Frontend"]},
        {"id": "p2", "name": "Personal", "stardust_count": 20, "active_biomes": []},
    ],
}

PLANETS = [
    {"id": "p1", "name": "Engineering", "galaxy_id": "g1", "description": "Tech stuff", "color": "#6D28D9", "created_at": "2026-01-01T00:00:00", "stardust_count": 80, "health_status": "healthy"},
    {"id": "p2", "name": "Personal", "galaxy_id": "g1", "description": None, "color": "#0EA5E9", "created_at": "2026-01-01T00:00:00", "stardust_count": 20, "health_status": "healthy"},
]

PLANET_DETAIL = {
    **PLANETS[0],
    "biomes": [
        {"id": "b1", "name": "Backend", "lifecycle_state": "ACTIVE", "stardust_count": 50},
        {"id": "b2", "name": "Frontend", "lifecycle_state": "SEED", "stardust_count": 10},
    ],
}

BIOMES = [
    {"id": "b1", "planet_id": "p1", "galaxy_id": "g1", "name": "Backend", "description": None, "lifecycle_state": "ACTIVE", "created_at": "2026-01-01T00:00:00", "last_active_at": "2026-04-27T00:00:00", "stardust_count": 50, "cache_ttl_seconds": 28800},
    {"id": "b2", "planet_id": "p1", "galaxy_id": "g1", "name": "Frontend", "description": None, "lifecycle_state": "SEED", "created_at": "2026-01-01T00:00:00", "last_active_at": None, "stardust_count": 10, "cache_ttl_seconds": 28800},
]

STARDUST_LIST = {
    "items": [
        {"id": "s1", "biome_id": "b1", "planet_id": "p1", "galaxy_id": "g1", "content": "FastAPI is great for building APIs", "region": "analytical", "gravity": "BIOME", "confidence": 0.8, "valid_from": "2026-01-01T00:00:00", "valid_until": None, "context_tags": ["python", "api"], "contradiction_id": None, "reinforcement_sources": 1, "source_agent": "cli", "chroma_id": None, "created_at": "2026-01-01T00:00:00", "last_accessed": None, "access_count": 3},
    ],
    "total": 1, "offset": 0, "limit": 20,
}

STARDUST_SINGLE = STARDUST_LIST["items"][0]

SEARCH_RESULTS = {
    "records": [
        {"id": "s1", "content": "FastAPI is great", "region": "analytical", "biome_name": "Backend", "planet_name": "Engineering", "confidence": 0.85, "valid_from": "2026-01-01T00:00:00", "valid_until": None, "context_tags": ["python"], "source_agent": "cli", "access_count": 2},
    ],
    "retrieval_metadata": {"sources_checked": ["redis_cache", "chroma_analytical"], "cache_hits": 0, "total_records_considered": 5, "records_returned": 1, "confidence_range": [0.85, 0.85], "contradiction_flags": 0, "retrieval_latency_ms": 42},
}

ENTITIES_LIST = {
    "items": [
        {"id": "e1", "name": "FastAPI", "entity_type": "TOOL", "tier": 2, "profile": {}, "mention_count": 5, "first_seen": "2026-01-01T00:00:00", "last_seen": "2026-04-27T00:00:00"},
    ],
    "total": 1, "offset": 0, "limit": 20,
}

ENTITY_PROFILE = {
    "entity": {"id": "e1", "name": "FastAPI", "entity_type": "TOOL", "tier": 2, "profile": {"desc": "web framework"}, "mention_count": 5, "first_seen": "2026-01-01T00:00:00", "last_seen": "2026-04-27T00:00:00"},
    "related_stardust": [{"id": "s1", "content": "FastAPI is great", "region": "analytical", "biome_name": "Backend", "planet_name": "Engineering", "confidence": 0.8, "valid_from": "2026-01-01T00:00:00", "valid_until": None, "context_tags": [], "source_agent": "cli", "access_count": 2}],
    "timeline": [{"event_date": "2026-04-27T00:00:00", "event_type": "mention", "event_content": "FastAPI is great"}],
    "relationship_types": ["mentioned_in"],
}

NEBULA_LOG = {
    "events": [
        {"event_id": 1, "action_type": "WRITE", "planet_id": "p1", "biome_id": "b1", "record_id": "s1", "initiated_by": "cli", "timestamp": "2026-04-27T12:00:00", "metadata": {}},
        {"event_id": 2, "action_type": "READ", "planet_id": None, "biome_id": None, "record_id": None, "initiated_by": "search", "timestamp": "2026-04-27T12:01:00", "metadata": {}},
    ],
    "total": 2, "offset": 0, "limit": 20,
}

NEBULA_DASHBOARD = {"total_events": 50, "events_by_type": {"WRITE": 30, "READ": 15, "ENTITY_EXTRACTED": 5}, "events_last_24h": 8, "top_agents": [], "top_biomes": []}

SUN_SECTIONS = {"values": {"principles": ["Accuracy over speed"], "communication_style": "direct"}, "agent_protocol": {"write_rules": ["Read Sun on session start"], "session_start_instruction": "Call orion_context"}, "identity": {"name": "Test User", "role": "Developer"}, "working_context": {"current_focus": "Testing", "hot_biomes": [], "blockers": []}, "planet_registry": {"planets": []}, "evolution_log": {"entries": []}}


# ── Root ────────────────────────────────────────────────────────────────────

class TestRootGroup:
    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Orion" in result.output
        for cmd in ["start", "stop", "status", "planet", "biome", "stardust", "entity", "nebula", "sun", "search", "write", "context"]:
            assert cmd in result.output

    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


# ── Lifecycle commands ──────────────────────────────────────────────────────

class TestStart:
    @patch("app.cli._wait_and_launch_tui")
    @patch("app.cli.subprocess.run")
    def test_start_default(self, mock_run, mock_tui):
        result = runner.invoke(cli, ["start"])
        assert result.exit_code == 0
        assert "Starting Orion" in result.output
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "compose", "up", "-d"]
        mock_tui.assert_called_once()

    @patch("app.cli.subprocess.run")
    def test_start_detached(self, mock_run):
        result = runner.invoke(cli, ["start", "-d"])
        assert result.exit_code == 0
        assert "background" in result.output

    @patch("app.cli._wait_and_launch_tui")
    @patch("app.cli.subprocess.run")
    def test_start_with_build(self, mock_run, mock_tui):
        result = runner.invoke(cli, ["start", "--build"])
        assert "--build" in mock_run.call_args[0][0]

    @patch("app.cli.subprocess.run")
    def test_start_no_tui(self, mock_run):
        result = runner.invoke(cli, ["start", "--no-tui"])
        assert "background" in result.output


class TestStop:
    @patch("app.cli.subprocess.run")
    def test_stop(self, mock_run):
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code == 0
        assert "Stopping" in result.output
        assert mock_run.call_args[0][0] == ["docker", "compose", "down"]


class TestRestart:
    @patch("app.cli.subprocess.run")
    def test_restart(self, mock_run):
        result = runner.invoke(cli, ["restart"])
        assert result.exit_code == 0
        assert mock_run.call_args[0][0] == ["docker", "compose", "restart"]


class TestLogs:
    @patch("app.cli.subprocess.run")
    def test_logs(self, mock_run):
        result = runner.invoke(cli, ["logs"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "logs" in cmd and "-f" in cmd


# ── Status ──────────────────────────────────────────────────────────────────

class TestStatus:
    @patch("app.cli.httpx.get")
    @patch("app.cli._api")
    def test_status_healthy(self, mock_api, mock_get):
        mock_get.return_value = MagicMock(json=lambda: {"status": "ok", "degraded": []})
        mock_api.return_value = _mock_response(200, GALAXY_STATUS)
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Dev Galaxy" in result.output
        assert "42.5" in result.output
        assert "Engineering" in result.output
        assert "unresolved contradictions" in result.output

    @patch("app.cli.httpx.get")
    @patch("app.cli._api")
    def test_status_degraded(self, mock_api, mock_get):
        mock_get.return_value = MagicMock(json=lambda: {"status": "degraded", "degraded": ["redis", "ollama"]})
        mock_api.return_value = _mock_response(200, GALAXY_STATUS)
        result = runner.invoke(cli, ["status"])
        assert "Degraded" in result.output
        assert "redis" in result.output

    @patch("app.cli.httpx.get")
    def test_status_offline(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.ConnectError("refused")
        result = runner.invoke(cli, ["status"])
        assert "offline" in result.output

    @patch("app.cli.httpx.get")
    @patch("app.cli._api")
    def test_status_no_galaxy(self, mock_api, mock_get):
        mock_get.return_value = MagicMock(json=lambda: {"status": "ok"})
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["status"])
        assert "No Galaxy found" in result.output


# ── Init ────────────────────────────────────────────────────────────────────

class TestInit:
    @patch("app.cli._api")
    def test_init_success(self, mock_api):
        mock_api.return_value = _mock_response(201, {"galaxy_id": "g1", "planets": ["Engineering", "Personal"], "first_biome_id": "b1", "import_started": False})
        result = runner.invoke(cli, ["init", "--role", "Developer", "--biome", "Backend"])
        assert result.exit_code == 0
        assert "Galaxy created" in result.output

    @patch("app.cli._api")
    def test_init_already_exists(self, mock_api):
        mock_api.return_value = _mock_response(400)
        result = runner.invoke(cli, ["init", "--role", "Developer", "--biome", "Test"])
        assert "already exists" in result.output

    @patch("app.cli._api")
    def test_init_with_import(self, mock_api):
        mock_api.return_value = _mock_response(201, {"galaxy_id": "g1", "planets": ["Engineering", "Personal"], "first_biome_id": "b1", "import_started": True})
        result = runner.invoke(cli, ["init", "--role", "Developer", "--biome", "Test", "--import-path", "/tmp"])
        assert "Import started" in result.output


# ── Search ──────────────────────────────────────────────────────────────────

class TestSearch:
    @patch("app.cli._api")
    def test_search_results(self, mock_api):
        mock_api.return_value = _mock_response(200, SEARCH_RESULTS)
        result = runner.invoke(cli, ["search", "FastAPI"])
        assert result.exit_code == 0
        assert "1 results" in result.output
        assert "FastAPI is great" in result.output
        assert "Engineering" in result.output

    @patch("app.cli._api")
    def test_search_no_galaxy(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["search", "test"])
        assert "No Galaxy found" in result.output

    @patch("app.cli._api")
    def test_search_empty(self, mock_api):
        mock_api.return_value = _mock_response(200, {"records": [], "retrieval_metadata": {"retrieval_latency_ms": 5}})
        result = runner.invoke(cli, ["search", "nothing"])
        assert "0 results" in result.output

    @patch("app.cli._api")
    def test_search_json(self, mock_api):
        mock_api.return_value = _mock_response(200, SEARCH_RESULTS)
        result = runner.invoke(cli, ["search", "test", "--json"])
        parsed = json.loads(result.output)
        assert "records" in parsed

    @patch("app.cli._api")
    def test_search_with_filters(self, mock_api):
        mock_api.return_value = _mock_response(200, SEARCH_RESULTS)
        result = runner.invoke(cli, ["search", "test", "-p", "Engineering", "-r", "analytical", "-n", "3"])
        assert result.exit_code == 0
        call_kwargs = mock_api.call_args
        params = call_kwargs[1]["params"]
        assert params["planet"] == "Engineering"
        assert params["region"] == "analytical"
        assert params["limit"] == 3

    def test_search_help(self):
        result = runner.invoke(cli, ["search", "--help"])
        assert "--planet" in result.output
        assert "--region" in result.output
        assert "--json" in result.output


# ── Write ───────────────────────────────────────────────────────────────────

class TestWrite:
    @patch("app.cli._api")
    def test_write_success(self, mock_api):
        mock_api.side_effect = [
            _mock_response(200, PLANETS),
            _mock_response(200, BIOMES),
            _mock_response(201, {"status": "success", "stardust_id": "abcd1234-5678", "biome_id": "b1", "planet_id": "p1", "contradiction_check": "clean"}),
        ]
        result = runner.invoke(cli, ["write", "Test content", "-p", "Engineering"])
        assert result.exit_code == 0
        assert "Written" in result.output
        assert "abcd1234" in result.output

    @patch("app.cli._api")
    def test_write_planet_not_found(self, mock_api):
        mock_api.return_value = _mock_response(200, PLANETS)
        result = runner.invoke(cli, ["write", "Test", "-p", "NonExistent"])
        assert "not found" in result.output

    @patch("app.cli._api")
    def test_write_no_biome(self, mock_api):
        mock_api.side_effect = [_mock_response(200, PLANETS), _mock_response(200, [])]
        result = runner.invoke(cli, ["write", "Test", "-p", "Engineering"])
        assert "No biome found" in result.output

    @patch("app.cli._api")
    def test_write_with_tags(self, mock_api):
        mock_api.side_effect = [
            _mock_response(200, PLANETS),
            _mock_response(200, BIOMES),
            _mock_response(201, {"status": "success", "stardust_id": "abcd1234", "biome_id": "b1", "planet_id": "p1", "contradiction_check": "clean"}),
        ]
        result = runner.invoke(cli, ["write", "Tagged content", "-p", "Engineering", "-t", "backend,api"])
        assert result.exit_code == 0
        body = mock_api.call_args_list[2][1]["json"]
        assert body["context_tags"] == ["backend", "api"]

    @patch("app.cli._api")
    def test_write_with_options(self, mock_api):
        mock_api.side_effect = [
            _mock_response(200, PLANETS),
            _mock_response(200, BIOMES),
            _mock_response(201, {"status": "success", "stardust_id": "abcd1234", "biome_id": "b1", "planet_id": "p1", "contradiction_check": "clean"}),
        ]
        result = runner.invoke(cli, ["write", "Decision", "-p", "Engineering", "-r", "analytical", "-g", "PLANET"])
        body = mock_api.call_args_list[2][1]["json"]
        assert body["region"] == "analytical"
        assert body["gravity"] == "PLANET"

    @patch("app.cli._api")
    def test_write_api_error(self, mock_api):
        mock_api.side_effect = [_mock_response(200, PLANETS), _mock_response(200, BIOMES), _mock_response(500, text="Internal Server Error")]
        result = runner.invoke(cli, ["write", "Test", "-p", "Engineering"])
        assert "Error" in result.output

    def test_write_requires_planet(self):
        result = runner.invoke(cli, ["write", "Test content"])
        assert result.exit_code != 0


# ── Context ─────────────────────────────────────────────────────────────────

class TestContext:
    @patch("app.cli._api")
    def test_context_basic(self, mock_api):
        mock_api.side_effect = [
            _mock_response(200, SUN_SECTIONS),  # GET /galaxy/sun
            _mock_response(200, PLANETS),        # GET /planets
            _mock_response(200, BIOMES),         # GET /planets/{id}/biomes
            _mock_response(200, STARDUST_LIST),  # GET /biomes/{id}/stardust
        ]
        result = runner.invoke(cli, ["context"])
        assert result.exit_code == 0
        assert "Context Bundle" in result.output
        assert "values" in result.output

    @patch("app.cli._api")
    def test_context_no_galaxy(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["context"])
        assert "No Galaxy found" in result.output

    @patch("app.cli._api")
    def test_context_json(self, mock_api):
        mock_api.side_effect = [
            _mock_response(200, SUN_SECTIONS),
            _mock_response(200, PLANETS),
            _mock_response(200, BIOMES),
            _mock_response(200, STARDUST_LIST),
        ]
        result = runner.invoke(cli, ["context", "--json"])
        parsed = json.loads(result.output)
        assert "sun" in parsed


# ── Planet commands ─────────────────────────────────────────────────────────

class TestPlanet:
    def test_planet_help(self):
        result = runner.invoke(cli, ["planet", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output
        assert "show" in result.output

    @patch("app.cli._api")
    def test_planet_list(self, mock_api):
        mock_api.return_value = _mock_response(200, PLANETS)
        result = runner.invoke(cli, ["planet", "list"])
        assert result.exit_code == 0
        assert "Engineering" in result.output
        assert "Personal" in result.output
        assert "80" in result.output

    @patch("app.cli._api")
    def test_planet_list_empty(self, mock_api):
        mock_api.return_value = _mock_response(200, [])
        result = runner.invoke(cli, ["planet", "list"])
        assert "No planets" in result.output

    @patch("app.cli._api")
    def test_planet_list_json(self, mock_api):
        mock_api.return_value = _mock_response(200, PLANETS)
        result = runner.invoke(cli, ["planet", "list", "--json"])
        parsed = json.loads(result.output)
        assert len(parsed) == 2

    @patch("app.cli._api")
    def test_planet_create(self, mock_api):
        mock_api.return_value = _mock_response(201, {"id": "p3", "name": "Research", "galaxy_id": "g1", "description": None, "color": "#FF0000", "created_at": "2026-04-27T00:00:00", "stardust_count": 0, "health_status": "healthy"})
        result = runner.invoke(cli, ["planet", "create", "Research", "--color", "#FF0000"])
        assert result.exit_code == 0
        assert "Research" in result.output
        assert "created" in result.output

    @patch("app.cli._api")
    def test_planet_create_error(self, mock_api):
        mock_api.return_value = _mock_response(400, text="Bad request")
        result = runner.invoke(cli, ["planet", "create", "Bad"])
        assert "Error" in result.output

    @patch("app.cli._api")
    def test_planet_show(self, mock_api):
        mock_api.side_effect = [
            _mock_response(200, PLANETS),       # GET /planets (resolve name)
            _mock_response(200, PLANET_DETAIL),  # GET /planets/{id}
        ]
        result = runner.invoke(cli, ["planet", "show", "Engineering"])
        assert result.exit_code == 0
        assert "Engineering" in result.output
        assert "Backend" in result.output
        assert "Frontend" in result.output

    @patch("app.cli._api")
    def test_planet_show_not_found(self, mock_api):
        mock_api.return_value = _mock_response(200, PLANETS)
        result = runner.invoke(cli, ["planet", "show", "NonExistent"])
        assert "not found" in result.output

    @patch("app.cli._api")
    def test_planet_show_json(self, mock_api):
        mock_api.side_effect = [_mock_response(200, PLANETS), _mock_response(200, PLANET_DETAIL)]
        result = runner.invoke(cli, ["planet", "show", "Engineering", "--json"])
        parsed = json.loads(result.output)
        assert parsed["name"] == "Engineering"
        assert len(parsed["biomes"]) == 2


# ── Biome commands ──────────────────────────────────────────────────────────

class TestBiome:
    def test_biome_help(self):
        result = runner.invoke(cli, ["biome", "--help"])
        assert result.exit_code == 0
        for sub in ["list", "create", "show", "lifecycle"]:
            assert sub in result.output

    @patch("app.cli._api")
    def test_biome_list(self, mock_api):
        mock_api.side_effect = [
            _mock_response(200, PLANETS),  # _resolve_planet_id
            _mock_response(200, BIOMES),
        ]
        result = runner.invoke(cli, ["biome", "list", "-p", "Engineering"])
        assert result.exit_code == 0
        assert "Backend" in result.output
        assert "ACTIVE" in result.output

    @patch("app.cli._api")
    def test_biome_list_planet_not_found(self, mock_api):
        mock_api.return_value = _mock_response(200, PLANETS)
        result = runner.invoke(cli, ["biome", "list", "-p", "Nope"])
        assert "not found" in result.output

    @patch("app.cli._api")
    def test_biome_list_json(self, mock_api):
        mock_api.side_effect = [_mock_response(200, PLANETS), _mock_response(200, BIOMES)]
        result = runner.invoke(cli, ["biome", "list", "-p", "Engineering", "--json"])
        parsed = json.loads(result.output)
        assert len(parsed) == 2

    @patch("app.cli._api")
    def test_biome_create(self, mock_api):
        mock_api.side_effect = [
            _mock_response(200, PLANETS),
            _mock_response(201, BIOMES[0]),
        ]
        result = runner.invoke(cli, ["biome", "create", "-p", "Engineering", "Backend"])
        assert result.exit_code == 0
        assert "created" in result.output

    @patch("app.cli._api")
    def test_biome_create_planet_not_found(self, mock_api):
        mock_api.return_value = _mock_response(200, PLANETS)
        result = runner.invoke(cli, ["biome", "create", "-p", "Nope", "Test"])
        assert "not found" in result.output

    @patch("app.cli._api")
    def test_biome_show(self, mock_api):
        mock_api.return_value = _mock_response(200, BIOMES[0])
        result = runner.invoke(cli, ["biome", "show", "b1"])
        assert result.exit_code == 0
        assert "Backend" in result.output
        assert "ACTIVE" in result.output

    @patch("app.cli._api")
    def test_biome_show_not_found(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["biome", "show", "bad-id"])
        assert "not found" in result.output

    @patch("app.cli._api")
    def test_biome_show_json(self, mock_api):
        mock_api.return_value = _mock_response(200, BIOMES[0])
        result = runner.invoke(cli, ["biome", "show", "b1", "--json"])
        parsed = json.loads(result.output)
        assert parsed["name"] == "Backend"

    @patch("app.cli._api")
    def test_biome_lifecycle(self, mock_api):
        updated = {**BIOMES[0], "lifecycle_state": "MATURE"}
        mock_api.return_value = _mock_response(200, updated)
        result = runner.invoke(cli, ["biome", "lifecycle", "b1", "MATURE"])
        assert result.exit_code == 0
        assert "MATURE" in result.output

    @patch("app.cli._api")
    def test_biome_lifecycle_not_found(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["biome", "lifecycle", "bad-id", "ACTIVE"])
        assert "not found" in result.output

    def test_biome_lifecycle_invalid_state(self):
        result = runner.invoke(cli, ["biome", "lifecycle", "b1", "INVALID"])
        assert result.exit_code != 0


# ── Stardust commands ───────────────────────────────────────────────────────

class TestStardust:
    def test_stardust_help(self):
        result = runner.invoke(cli, ["stardust", "--help"])
        assert result.exit_code == 0
        for sub in ["list", "get", "update"]:
            assert sub in result.output

    @patch("app.cli._api")
    def test_stardust_list(self, mock_api):
        mock_api.return_value = _mock_response(200, STARDUST_LIST)
        result = runner.invoke(cli, ["stardust", "list", "b1"])
        assert result.exit_code == 0
        assert "FastAPI" in result.output
        assert "1/1" in result.output

    @patch("app.cli._api")
    def test_stardust_list_json(self, mock_api):
        mock_api.return_value = _mock_response(200, STARDUST_LIST)
        result = runner.invoke(cli, ["stardust", "list", "b1", "--json"])
        parsed = json.loads(result.output)
        assert parsed["total"] == 1

    @patch("app.cli._api")
    def test_stardust_list_empty(self, mock_api):
        mock_api.return_value = _mock_response(200, {"items": [], "total": 0, "offset": 0, "limit": 20})
        result = runner.invoke(cli, ["stardust", "list", "b1"])
        assert "empty" in result.output

    @patch("app.cli._api")
    def test_stardust_get(self, mock_api):
        mock_api.return_value = _mock_response(200, STARDUST_SINGLE)
        result = runner.invoke(cli, ["stardust", "get", "s1"])
        assert result.exit_code == 0
        assert "Stardust" in result.output
        assert "analytical" in result.output
        assert "FastAPI is great" in result.output
        assert "python" in result.output

    @patch("app.cli._api")
    def test_stardust_get_not_found(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["stardust", "get", "bad-id"])
        assert "not found" in result.output

    @patch("app.cli._api")
    def test_stardust_get_json(self, mock_api):
        mock_api.return_value = _mock_response(200, STARDUST_SINGLE)
        result = runner.invoke(cli, ["stardust", "get", "s1", "--json"])
        parsed = json.loads(result.output)
        assert parsed["id"] == "s1"

    @patch("app.cli._api")
    def test_stardust_update_content(self, mock_api):
        mock_api.return_value = _mock_response(200, STARDUST_SINGLE)
        result = runner.invoke(cli, ["stardust", "update", "s1", "-c", "Updated content"])
        assert result.exit_code == 0
        assert "Updated" in result.output
        body = mock_api.call_args[1]["json"]
        assert body["content"] == "Updated content"

    @patch("app.cli._api")
    def test_stardust_update_tags(self, mock_api):
        mock_api.return_value = _mock_response(200, STARDUST_SINGLE)
        result = runner.invoke(cli, ["stardust", "update", "s1", "-t", "new,tags"])
        body = mock_api.call_args[1]["json"]
        assert body["context_tags"] == ["new", "tags"]

    @patch("app.cli._api")
    def test_stardust_update_gravity(self, mock_api):
        mock_api.return_value = _mock_response(200, STARDUST_SINGLE)
        result = runner.invoke(cli, ["stardust", "update", "s1", "-g", "PLANET"])
        body = mock_api.call_args[1]["json"]
        assert body["gravity"] == "PLANET"

    def test_stardust_update_nothing(self):
        result = runner.invoke(cli, ["stardust", "update", "s1"])
        assert "Nothing to update" in result.output

    @patch("app.cli._api")
    def test_stardust_update_not_found(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["stardust", "update", "bad", "-c", "x"])
        assert "not found" in result.output


# ── Entity commands ─────────────────────────────────────────────────────────

class TestEntity:
    def test_entity_help(self):
        result = runner.invoke(cli, ["entity", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "get" in result.output

    @patch("app.cli._api")
    def test_entity_list(self, mock_api):
        mock_api.return_value = _mock_response(200, ENTITIES_LIST)
        result = runner.invoke(cli, ["entity", "list"])
        assert result.exit_code == 0
        assert "FastAPI" in result.output
        assert "TOOL" in result.output

    @patch("app.cli._api")
    def test_entity_list_with_type(self, mock_api):
        mock_api.return_value = _mock_response(200, ENTITIES_LIST)
        result = runner.invoke(cli, ["entity", "list", "--type", "TOOL"])
        assert result.exit_code == 0
        params = mock_api.call_args[1]["params"]
        assert params["entity_type"] == "TOOL"

    @patch("app.cli._api")
    def test_entity_list_json(self, mock_api):
        mock_api.return_value = _mock_response(200, ENTITIES_LIST)
        result = runner.invoke(cli, ["entity", "list", "--json"])
        parsed = json.loads(result.output)
        assert parsed["total"] == 1

    @patch("app.cli._api")
    def test_entity_list_empty(self, mock_api):
        mock_api.return_value = _mock_response(200, {"items": [], "total": 0})
        result = runner.invoke(cli, ["entity", "list"])
        assert "none" in result.output

    @patch("app.cli._api")
    def test_entity_get(self, mock_api):
        mock_api.return_value = _mock_response(200, ENTITY_PROFILE)
        result = runner.invoke(cli, ["entity", "get", "e1"])
        assert result.exit_code == 0
        assert "FastAPI" in result.output
        assert "TOOL" in result.output
        assert "mentioned_in" in result.output
        assert "Related stardust" in result.output
        assert "Timeline" in result.output

    @patch("app.cli._api")
    def test_entity_get_not_found(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["entity", "get", "bad-id"])
        assert "not found" in result.output

    @patch("app.cli._api")
    def test_entity_get_json(self, mock_api):
        mock_api.return_value = _mock_response(200, ENTITY_PROFILE)
        result = runner.invoke(cli, ["entity", "get", "e1", "--json"])
        parsed = json.loads(result.output)
        assert parsed["entity"]["name"] == "FastAPI"


# ── Nebula commands ─────────────────────────────────────────────────────────

class TestNebula:
    def test_nebula_help(self):
        result = runner.invoke(cli, ["nebula", "--help"])
        assert result.exit_code == 0
        assert "log" in result.output
        assert "dashboard" in result.output

    @patch("app.cli._api")
    def test_nebula_log(self, mock_api):
        mock_api.return_value = _mock_response(200, NEBULA_LOG)
        result = runner.invoke(cli, ["nebula", "log"])
        assert result.exit_code == 0
        assert "WRITE" in result.output
        assert "READ" in result.output
        assert "2/2" in result.output

    @patch("app.cli._api")
    def test_nebula_log_with_type(self, mock_api):
        mock_api.return_value = _mock_response(200, NEBULA_LOG)
        result = runner.invoke(cli, ["nebula", "log", "--type", "WRITE"])
        params = mock_api.call_args[1]["params"]
        assert params["action_type"] == "WRITE"

    @patch("app.cli._api")
    def test_nebula_log_json(self, mock_api):
        mock_api.return_value = _mock_response(200, NEBULA_LOG)
        result = runner.invoke(cli, ["nebula", "log", "--json"])
        parsed = json.loads(result.output)
        assert len(parsed["events"]) == 2

    @patch("app.cli._api")
    def test_nebula_log_empty(self, mock_api):
        mock_api.return_value = _mock_response(200, {"events": [], "total": 0})
        result = runner.invoke(cli, ["nebula", "log"])
        assert "none" in result.output

    @patch("app.cli._api")
    def test_nebula_dashboard(self, mock_api):
        mock_api.return_value = _mock_response(200, NEBULA_DASHBOARD)
        result = runner.invoke(cli, ["nebula", "dashboard"])
        assert result.exit_code == 0
        assert "Dashboard" in result.output
        assert "50" in result.output
        assert "WRITE" in result.output

    @patch("app.cli._api")
    def test_nebula_dashboard_json(self, mock_api):
        mock_api.return_value = _mock_response(200, NEBULA_DASHBOARD)
        result = runner.invoke(cli, ["nebula", "dashboard", "--json"])
        parsed = json.loads(result.output)
        assert parsed["total_events"] == 50


# ── Sun commands ────────────────────────────────────────────────────────────

class TestSun:
    def test_sun_help(self):
        result = runner.invoke(cli, ["sun", "--help"])
        assert result.exit_code == 0
        assert "show" in result.output
        assert "update" in result.output

    @patch("app.cli._api")
    def test_sun_show(self, mock_api):
        mock_api.return_value = _mock_response(200, SUN_SECTIONS)
        result = runner.invoke(cli, ["sun", "show"])
        assert result.exit_code == 0
        assert "Sun Sections" in result.output
        assert "values" in result.output
        assert "Accuracy over speed" in result.output

    @patch("app.cli._api")
    def test_sun_show_no_galaxy(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["sun", "show"])
        assert "No Galaxy found" in result.output

    @patch("app.cli._api")
    def test_sun_show_empty(self, mock_api):
        mock_api.return_value = _mock_response(200, {})
        result = runner.invoke(cli, ["sun", "show"])
        assert "no sections" in result.output

    @patch("app.cli._api")
    def test_sun_show_json(self, mock_api):
        mock_api.return_value = _mock_response(200, SUN_SECTIONS)
        result = runner.invoke(cli, ["sun", "show", "--json"])
        parsed = json.loads(result.output)
        assert "values" in parsed

    @patch("app.cli._api")
    def test_sun_update(self, mock_api):
        mock_api.return_value = _mock_response(200, {"id": "sun1", "section_key": "values", "content": '["New value"]', "version": 2, "updated_at": "2026-04-27T00:00:00"})
        result = runner.invoke(cli, ["sun", "update", "values", '["New value"]'])
        assert result.exit_code == 0
        assert "Updated" in result.output
        assert "v2" in result.output

    @patch("app.cli._api")
    def test_sun_update_not_found(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["sun", "update", "bad_key", "content"])
        assert "not found" in result.output


# ── Audit ───────────────────────────────────────────────────────────────────

class TestAudit:
    @patch("app.cli._api")
    def test_audit_status_no_runs(self, mock_api):
        mock_api.return_value = _mock_response(200, {"status": "no_audits_run"})
        result = runner.invoke(cli, ["audit"])
        assert "No audits have run" in result.output

    @patch("app.cli._api")
    def test_audit_status_with_data(self, mock_api):
        mock_api.return_value = _mock_response(200, {"run_at": "2026-04-27T02:00:00", "records_reviewed": 500, "duplicates_merged": 3, "contradictions_found": 1, "duration_ms": 1200})
        result = runner.invoke(cli, ["audit"])
        assert "2026-04-27" in result.output
        assert "500" in result.output

    @patch("app.cli._api")
    def test_audit_trigger(self, mock_api):
        mock_api.return_value = _mock_response(200, {"records_reviewed": 200, "duplicates_merged": 5, "contradictions_found": 2, "confidence_decays": 10, "promotions_made": 3, "duration_ms": 800})
        result = runner.invoke(cli, ["audit", "--run"])
        assert "Audit complete" in result.output
        assert "800ms" in result.output

    @patch("app.cli._api")
    def test_audit_trigger_error(self, mock_api):
        mock_api.return_value = _mock_response(500, text="Server error")
        result = runner.invoke(cli, ["audit", "--run"])
        assert "Error" in result.output


# ── Connect ─────────────────────────────────────────────────────────────────

class TestConnect:
    def test_connect_claude(self):
        result = runner.invoke(cli, ["connect", "claude"])
        assert "claude mcp add orion" in result.output

    def test_connect_cursor(self):
        result = runner.invoke(cli, ["connect", "cursor"])
        assert ".cursor/mcp.json" in result.output

    def test_connect_unknown(self):
        result = runner.invoke(cli, ["connect", "vscode"])
        assert "MCP endpoint" in result.output

    def test_connect_default(self):
        result = runner.invoke(cli, ["connect"])
        assert "claude mcp add orion" in result.output


# ── Reset ───────────────────────────────────────────────────────────────────

class TestReset:
    @patch("app.cli.subprocess.run")
    def test_reset_confirmed(self, mock_run, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "orion.db").touch()
        with patch("app.cli.PROJECT_DIR", str(tmp_path)):
            result = runner.invoke(cli, ["reset", "--yes"])
        assert result.exit_code == 0
        assert "Resetting" in result.output
        assert "Reset complete" in result.output
        assert mock_run.call_args[0][0] == ["docker", "compose", "down", "-v"]

    def test_reset_aborted(self):
        result = runner.invoke(cli, ["reset"], input="n\n")
        assert result.exit_code != 0


# ── Import ──────────────────────────────────────────────────────────────────

class TestImport:
    @patch("app.cli._api")
    def test_import_success(self, mock_api, tmp_path):
        mock_api.side_effect = [_mock_response(200, PLANETS), _mock_response(200, {"status": "import_started"})]
        result = runner.invoke(cli, ["import", str(tmp_path), "-p", "Engineering"])
        assert result.exit_code == 0
        assert "Import started" in result.output

    @patch("app.cli._api")
    def test_import_planet_not_found(self, mock_api, tmp_path):
        mock_api.return_value = _mock_response(200, PLANETS)
        result = runner.invoke(cli, ["import", str(tmp_path), "-p", "NonExistent"])
        assert "not found" in result.output

    def test_import_path_not_exists(self):
        result = runner.invoke(cli, ["import", "/nonexistent/path"])
        assert result.exit_code != 0


# ── Strength command ─────────────────────────────────────────────────────────

STRENGTH_DATA = {
    "score": 73.4, "grade": "C",
    "dimensions": {
        "volume": {"score": 91.2, "weight": 0.25, "label": "Knowledge Volume"},
        "density": {"score": 68.5, "weight": 0.20, "label": "Entity Graph Density"},
        "health": {"score": 50.0, "weight": 0.20, "label": "Contradiction Health"},
        "diversity": {"score": 72.1, "weight": 0.20, "label": "Reinforcement Diversity"},
        "coverage": {"score": 85.0, "weight": 0.15, "label": "Active Coverage"},
    },
    "trend": "+5.2 vs last week", "computed_at": "2026-04-27T00:00:00", "days_active": 47,
}


class TestStrength:
    @patch("app.cli._api")
    def test_strength(self, mock_api):
        mock_api.return_value = _mock_response(200, STRENGTH_DATA)
        result = runner.invoke(cli, ["strength"])
        assert result.exit_code == 0
        assert "73.4" in result.output
        assert "[C]" in result.output
        assert "Knowledge Volume" in result.output
        assert "+5.2 vs last week" in result.output

    @patch("app.cli._api")
    def test_strength_no_galaxy(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["strength"])
        assert "No Galaxy found" in result.output

    @patch("app.cli._api")
    def test_strength_json(self, mock_api):
        mock_api.return_value = _mock_response(200, STRENGTH_DATA)
        result = runner.invoke(cli, ["strength", "--json"])
        parsed = json.loads(result.output)
        assert parsed["score"] == 73.4
        assert parsed["grade"] == "C"
        assert "volume" in parsed["dimensions"]


# ── Capture command ─────────────────────────────────────────────────────────

class TestCapture:
    @patch("app.cli._api")
    def test_capture_success(self, mock_api):
        mock_api.return_value = _mock_response(201, {"status": "success", "stardust_id": "abcd1234", "biome_id": "b1", "planet_id": "p1", "contradiction_check": "clean"})
        result = runner.invoke(cli, ["capture", "Test note", "-p", "Engineering"])
        assert result.exit_code == 0
        assert "Captured" in result.output
        assert "abcd1234" in result.output

    @patch("app.cli._api")
    def test_capture_planet_not_found(self, mock_api):
        mock_api.return_value = _mock_response(404)
        result = runner.invoke(cli, ["capture", "Test", "-p", "NonExistent"])
        assert "not found" in result.output

    def test_capture_requires_planet(self):
        result = runner.invoke(cli, ["capture", "Test"])
        assert result.exit_code != 0

    @patch("app.cli._api")
    def test_capture_with_region(self, mock_api):
        mock_api.return_value = _mock_response(201, {"status": "success", "stardust_id": "abcd1234", "biome_id": "b1", "planet_id": "p1", "contradiction_check": "clean"})
        result = runner.invoke(cli, ["capture", "Decision note", "-p", "Engineering", "-r", "analytical"])
        body = mock_api.call_args[1]["json"]
        assert body["region"] == "analytical"


# ── Extended Init ───────────────────────────────────────────────────────────

class TestExtendedInit:
    @patch("app.cli._api")
    def test_init_with_v05_fields(self, mock_api):
        mock_api.return_value = _mock_response(201, {
            "galaxy_id": "g1", "planets": ["Engineering", "Personal"],
            "first_biome_id": "b1", "import_started": False,
            "stardust_count": 2, "entities_count": 3, "sun_configured": True,
        })
        result = runner.invoke(cli, ["init", "--role", "Developer", "--biome", "Backend",
                                     "--name", "Andy", "--goal", "Build Orion",
                                     "--tools", "FastAPI,Redis", "--style", "direct"])
        assert result.exit_code == 0
        assert "Galaxy created" in result.output
        assert "Stardust: 2" in result.output
        assert "Entities: 3" in result.output
        assert "Sun configured: ✓" in result.output
        body = mock_api.call_args[1]["json"]
        assert body["name"] == "Andy"
        assert body["goal"] == "Build Orion"
        assert body["tools"] == ["FastAPI", "Redis"]
        assert body["communication_style"] == "direct"


# ── Edge cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_unknown_command(self):
        result = runner.invoke(cli, ["foobar"])
        assert result.exit_code != 0

    def test_all_commands_have_help(self):
        commands = ["start", "stop", "restart", "status", "logs", "init",
                    "search", "write", "audit", "connect", "reset", "import",
                    "context", "strength", "capture", "tui"]
        for cmd in commands:
            result = runner.invoke(cli, [cmd, "--help"])
            assert result.exit_code == 0, f"{cmd} --help failed"

    def test_all_subcommands_have_help(self):
        subs = [
            ("planet", ["list", "create", "show"]),
            ("biome", ["list", "create", "show", "lifecycle"]),
            ("stardust", ["list", "get", "update"]),
            ("entity", ["list", "get"]),
            ("nebula", ["log", "dashboard"]),
            ("sun", ["show", "update"]),
        ]
        for group, cmds in subs:
            for cmd in cmds:
                result = runner.invoke(cli, [group, cmd, "--help"])
                assert result.exit_code == 0, f"{group} {cmd} --help failed"
                assert "Usage:" in result.output, f"{group} {cmd} missing Usage"
