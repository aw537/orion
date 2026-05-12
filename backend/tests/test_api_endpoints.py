"""Tests for untested API endpoints: agents, graph, model-switches, sun, cache, entities."""
import pytest


# ── Helper ──────────────────────────────────────────────────────────────────

async def _onboard(client):
    """Create a galaxy via onboarding, return response data."""
    resp = await client.post("/api/v1/onboarding/start", json={
        "role": "Developer", "first_biome_name": "Test Project",
    })
    assert resp.status_code == 200
    return resp.json()


# ── Agents endpoints ────────────────────────────────────────────────────────

class TestAgentsAPI:
    @pytest.mark.asyncio
    async def test_list_agents_empty(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_agents_no_galaxy(self, client):
        # No galaxy → 404 (auth requires galaxy)
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_agent_no_galaxy(self, client):
        resp = await client.get("/api/v1/agents/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/agents/nonexistent")
        assert resp.status_code == 200
        assert "not found" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_agent_expertise_no_galaxy(self, client):
        resp = await client.get("/api/v1/agents/test/expertise")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_agent_expertise_not_found(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/agents/nonexistent/expertise")
        assert resp.status_code == 200
        assert "not found" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_agent_sessions_no_galaxy(self, client):
        resp = await client.get("/api/v1/agents/test/sessions")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_agent_sessions_not_found(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/agents/nonexistent/sessions")
        assert resp.status_code == 200
        assert "not found" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_agent_health_no_galaxy(self, client):
        resp = await client.get("/api/v1/agents/test/health")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_agent_health_not_found(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/agents/nonexistent/health")
        assert resp.status_code == 200
        assert "not found" in resp.json()["error"]


# ── Graph endpoints ─────────────────────────────────────────────────────────

class TestGraphAPI:
    @pytest.mark.asyncio
    async def test_neighborhood_no_galaxy(self, client):
        resp = await client.get("/api/v1/graph/entity/fake-id/neighborhood")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_path_no_galaxy(self, client):
        resp = await client.get("/api/v1/graph/path", params={"source": "a", "target": "b"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_hubs_no_galaxy(self, client):
        resp = await client.get("/api/v1/graph/hubs")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unlinked_no_galaxy(self, client):
        resp = await client.get("/api/v1/graph/unlinked-mentions")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_link_post(self, client):
        resp = await client.post("/api/v1/graph/link", json={
            "entity_id": "fake-entity", "stardust_id": "fake-stardust",
        })
        assert resp.status_code == 404  # no galaxy

    @pytest.mark.asyncio
    async def test_path_with_galaxy_no_entities(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/graph/path", params={"source": "a", "target": "b"})
        data = resp.json()
        # No entities → no path found
        assert data.get("path") is None or data.get("nodes") is not None

    @pytest.mark.asyncio
    async def test_hubs_with_galaxy_empty(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/graph/hubs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── Model switches endpoints ───────────────────────────────────────────────

class TestModelSwitchesAPI:
    @pytest.mark.asyncio
    async def test_list_switches_no_galaxy(self, client):
        resp = await client.get("/api/v1/model-switches")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_switches_empty(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/model-switches")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_latest_switches_no_galaxy(self, client):
        resp = await client.get("/api/v1/model-switches/latest")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_latest_switches_empty(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/model-switches/latest")
        assert resp.status_code == 200
        assert resp.json() == []


# ── Galaxy Sun endpoint ─────────────────────────────────────────────────────

class TestGalaxySunAPI:
    @pytest.mark.asyncio
    async def test_sun_no_galaxy(self, client):
        resp = await client.get("/api/v1/galaxy/sun")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sun_with_galaxy(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/galaxy/sun")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Onboarding creates sun sections
        if data:
            assert "section_key" in data[0]


# ── Sun CRUD endpoints ──────────────────────────────────────────────────────

class TestSunAPI:
    @pytest.mark.asyncio
    async def test_get_sun_full_no_galaxy(self, client):
        resp = await client.get("/api/v1/sun")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_sun_section_no_galaxy(self, client):
        resp = await client.get("/api/v1/sun/identity")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_put_sun_section_no_galaxy(self, client):
        resp = await client.put("/api/v1/sun/identity", json={
            "content": {"name": "test"}, "changed_by": "test",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sun_crud_with_galaxy(self, client):
        await _onboard(client)
        # Read full sun
        resp = await client.get("/api/v1/sun")
        assert resp.status_code == 200

        # Read specific section
        resp = await client.get("/api/v1/sun/identity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["section_key"] == "identity"

        # Update section
        resp = await client.put("/api/v1/sun/identity", json={
            "content": {"name": "Updated Name", "role": "Tester"},
            "changed_by": "test", "summary": "test update",
        })
        assert resp.status_code == 200

        # Verify update
        resp = await client.get("/api/v1/sun/identity")
        content = resp.json()["content"]
        assert content["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_sun_nonexistent_section(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/sun/nonexistent")
        assert resp.status_code == 404


# ── Cache endpoints ─────────────────────────────────────────────────────────

class TestCacheAPI:
    @pytest.mark.asyncio
    async def test_ttl_config(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/cache/ttl-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "defaults" in data
        assert "overrides" in data
        assert data["defaults"]["analytical"] == 28800

    @pytest.mark.asyncio
    async def test_cache_stats(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "analytical" in data


# ── Entities endpoints ──────────────────────────────────────────────────────

class TestEntitiesAPI:
    @pytest.mark.asyncio
    async def test_list_entities_no_galaxy(self, client):
        resp = await client.get("/api/v1/entities")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_entities_with_galaxy(self, client):
        await _onboard(client)
        resp = await client.get("/api/v1/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, client):
        resp = await client.get("/api/v1/entities/nonexistent-id")
        assert resp.status_code == 404


# ── Stardust DELETE endpoint ─────────────────────────────────────────────────

class TestStardustDeleteEndpoint:
    async def _create_stardust(self, client) -> str:
        """Onboard and write one stardust record; return its ID."""
        data = await _onboard(client)
        biome_id = data["first_biome_id"]
        resp = await client.post(f"/api/v1/biomes/{biome_id}/stardust", json={
            "content": "test stardust for deletion", "region": "contextual",
        })
        assert resp.status_code == 201
        return resp.json()["stardust_id"]

    @pytest.mark.asyncio
    async def test_delete_stardust_success(self, client):
        stardust_id = await self._create_stardust(client)
        resp = await client.delete(f"/api/v1/stardust/{stardust_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        assert resp.json()["deleted_id"] == stardust_id

    @pytest.mark.asyncio
    async def test_delete_stardust_not_found(self, client):
        await _onboard(client)
        resp = await client.delete("/api/v1/stardust/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_stardust_no_galaxy(self, client):
        resp = await client.delete("/api/v1/stardust/some-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_stardust_then_get_returns_404(self, client):
        stardust_id = await self._create_stardust(client)
        await client.delete(f"/api/v1/stardust/{stardust_id}")
        get_resp = await client.get(f"/api/v1/stardust/{stardust_id}")
        assert get_resp.status_code == 404
