"""TDD tests for extended 5-step onboarding.

The backend OnboardingRequest already accepts name, goal, tools,
communication_style, and contradiction_preference — but the current
implementation only seeds stardust for goal and tools. These tests
verify the FULL contract: every field produces the expected records.
"""
import pytest


async def _onboard_full(client, **overrides):
    """Onboard with all 5-step fields populated."""
    payload = {
        "role": "Software Engineer",
        "first_biome_name": "Orion Backend",
        # Step 4 fields
        "name": "Andy",
        "goal": "Build a personal AI knowledge system",
        "communication_style": "direct",
        # Step 5 fields
        "tools": ["FastAPI", "PostgreSQL", "Redis"],
        "contradiction_preference": "flag_and_ask",
    }
    payload.update(overrides)
    return await client.post("/api/v1/onboarding/start", json=payload)


class TestExtendedOnboardingResponse:
    """The response should report real counts from all seeded data."""

    @pytest.mark.asyncio
    async def test_returns_stardust_count_from_goal_and_tools(self, client):
        resp = await _onboard_full(client)
        assert resp.status_code == 201
        data = resp.json()
        # goal creates 1 stardust, tools creates 1 stardust = 2 minimum
        assert data["stardust_count"] >= 2

    @pytest.mark.asyncio
    async def test_returns_entity_count_from_tools(self, client):
        resp = await _onboard_full(client)
        data = resp.json()
        # 3 tools → 3 entities
        assert data["entities_count"] >= 3

    @pytest.mark.asyncio
    async def test_sun_configured(self, client):
        resp = await _onboard_full(client)
        data = resp.json()
        assert data["sun_configured"] is True


class TestSunPersonalization:
    """Sun identity and values should reflect wizard answers."""

    @pytest.mark.asyncio
    async def test_sun_identity_has_name(self, client):
        await _onboard_full(client)
        resp = await client.get("/api/v1/sun")
        sun = resp.json()
        identity = sun.get("identity", {})
        assert identity.get("name") == "Andy"

    @pytest.mark.asyncio
    async def test_sun_identity_has_role(self, client):
        await _onboard_full(client)
        resp = await client.get("/api/v1/sun")
        sun = resp.json()
        identity = sun.get("identity", {})
        assert identity.get("role") == "Software Engineer"

    @pytest.mark.asyncio
    async def test_sun_values_communication_style(self, client):
        await _onboard_full(client)
        resp = await client.get("/api/v1/sun")
        sun = resp.json()
        values = sun.get("values", {})
        assert values.get("communication_style") == "direct"

    @pytest.mark.asyncio
    async def test_sun_values_contradiction_preference(self, client):
        await _onboard_full(client)
        resp = await client.get("/api/v1/sun")
        sun = resp.json()
        values = sun.get("values", {})
        assert values.get("contradiction_preference") == "flag_and_ask"

    @pytest.mark.asyncio
    async def test_sun_working_context_has_goal(self, client):
        await _onboard_full(client)
        resp = await client.get("/api/v1/sun")
        sun = resp.json()
        wc = sun.get("working_context", {})
        assert "Build a personal AI knowledge system" in wc.get("current_focus", "")


class TestStardustSeeding:
    """Goal and tools should create real stardust records."""

    @pytest.mark.asyncio
    async def test_goal_creates_stardust(self, client):
        resp = await _onboard_full(client)
        biome_id = resp.json()["first_biome_id"]
        resp = await client.get(f"/api/v1/biomes/{biome_id}/stardust")
        data = resp.json()
        records = data.get("items", data) if isinstance(data, dict) else data
        goal_records = [r for r in records if "Build a personal AI knowledge system" in r.get("content", "")]
        assert len(goal_records) >= 1

    @pytest.mark.asyncio
    async def test_tools_create_stardust(self, client):
        resp = await _onboard_full(client)
        biome_id = resp.json()["first_biome_id"]
        resp = await client.get(f"/api/v1/biomes/{biome_id}/stardust")
        data = resp.json()
        records = data.get("items", data) if isinstance(data, dict) else data
        tools_records = [r for r in records if "FastAPI" in r.get("content", "") and "PostgreSQL" in r.get("content", "")]
        assert len(tools_records) >= 1


class TestEntityCreation:
    """Each tool should become an Entity."""

    @pytest.mark.asyncio
    async def test_tools_create_entities(self, client):
        await _onboard_full(client)
        resp = await client.get("/api/v1/entities")
        data = resp.json()
        entities = data.get("items", data) if isinstance(data, dict) else data
        entity_names = [e["name"] for e in entities]
        assert "FastAPI" in entity_names
        assert "PostgreSQL" in entity_names
        assert "Redis" in entity_names

    @pytest.mark.asyncio
    async def test_entities_are_tool_type(self, client):
        await _onboard_full(client)
        resp = await client.get("/api/v1/entities")
        data = resp.json()
        entities = data.get("items", data) if isinstance(data, dict) else data
        tool_entities = [e for e in entities if e["name"] in ["FastAPI", "PostgreSQL", "Redis"]]
        for e in tool_entities:
            assert e["entity_type"] == "tool"


class TestMinimalOnboarding:
    """Onboarding with only required fields still works."""

    @pytest.mark.asyncio
    async def test_minimal_onboarding_succeeds(self, client):
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Developer",
            "first_biome_name": "Test",
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_minimal_has_zero_stardust(self, client):
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Developer",
            "first_biome_name": "Test",
        })
        data = resp.json()
        assert data["stardust_count"] == 0

    @pytest.mark.asyncio
    async def test_duplicate_onboarding_rejected(self, client):
        await _onboard_full(client)
        resp = await _onboard_full(client)
        assert resp.status_code == 400
