"""Tests for Sun lessons feature — self-correcting agent loop."""
import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _setup_galaxy():
    """Marker — each test uses the shared client fixture which has a fresh DB."""
    pass


class TestLessonsAPI:
    """Test the REST endpoints for lessons."""

    @pytest.mark.asyncio
    async def test_append_lesson(self, client: AsyncClient):
        await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})

        resp = await client.post("/api/v1/sun/lessons", json={
            "correction": "Always use parameterized queries",
            "context": "User corrected raw SQL usage",
            "tags": ["sql", "security"],
            "agent_name": "test-agent",
            "severity": "high",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "L001"
        assert data["correction"] == "Always use parameterized queries"
        assert data["tags"] == ["sql", "security"]
        assert data["severity"] == "high"
        assert data["status"] == "active"
        assert data["agent"] == "test-agent"

    @pytest.mark.asyncio
    async def test_get_lessons_empty(self, client: AsyncClient):
        await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})

        resp = await client.get("/api/v1/sun/lessons")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_lessons_returns_appended(self, client: AsyncClient):
        await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
        await client.post("/api/v1/sun/lessons", json={"correction": "Use type hints", "tags": ["python"]})
        await client.post("/api/v1/sun/lessons", json={"correction": "Prefer composition", "tags": ["design"]})

        resp = await client.get("/api/v1/sun/lessons")
        assert resp.status_code == 200
        lessons = resp.json()
        assert len(lessons) == 2
        assert lessons[0]["correction"] == "Use type hints"
        assert lessons[1]["correction"] == "Prefer composition"

    @pytest.mark.asyncio
    async def test_get_lessons_filter_by_tags(self, client: AsyncClient):
        await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
        await client.post("/api/v1/sun/lessons", json={"correction": "SQL lesson", "tags": ["sql", "db"]})
        await client.post("/api/v1/sun/lessons", json={"correction": "Git lesson", "tags": ["git"]})
        await client.post("/api/v1/sun/lessons", json={"correction": "DB lesson", "tags": ["db"]})

        resp = await client.get("/api/v1/sun/lessons?tags=db")
        lessons = resp.json()
        assert len(lessons) == 2
        assert all("db" in l["tags"] for l in lessons)

    @pytest.mark.asyncio
    async def test_lessons_included_in_full_sun(self, client: AsyncClient):
        await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
        await client.post("/api/v1/sun/lessons", json={"correction": "Test lesson", "tags": ["test"]})

        resp = await client.get("/api/v1/sun")
        sun = resp.json()
        assert "lessons" in sun
        entries = sun["lessons"].get("entries", [])
        assert len(entries) == 1
        assert entries[0]["correction"] == "Test lesson"

    @pytest.mark.asyncio
    async def test_lessons_in_orientation(self, client: AsyncClient):
        await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
        await client.post("/api/v1/sun/lessons", json={"correction": "Never force push", "tags": ["git"], "severity": "high"})

        resp = await client.post("/api/v1/brain/orient", json={
            "agent_name": "test-agent", "model": "test-model", "agent_type": "GENERAL",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "lessons" in data
        assert len(data["lessons"]) == 1
        assert data["lessons"][0]["correction"] == "Never force push"

    @pytest.mark.asyncio
    async def test_lesson_defaults(self, client: AsyncClient):
        await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})

        resp = await client.post("/api/v1/sun/lessons", json={"correction": "Minimal lesson"})
        data = resp.json()
        assert data["severity"] == "medium"
        assert data["agent"] == "user"
        assert data["tags"] == []
        assert data["context"] == ""

    @pytest.mark.asyncio
    async def test_lessons_are_append_only(self, client: AsyncClient):
        await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
        await client.post("/api/v1/sun/lessons", json={"correction": "First", "tags": ["a"]})
        await client.post("/api/v1/sun/lessons", json={"correction": "Second", "tags": ["b"]})
        await client.post("/api/v1/sun/lessons", json={"correction": "Third", "tags": ["c"]})

        resp = await client.get("/api/v1/sun/lessons")
        lessons = resp.json()
        assert len(lessons) == 3
        assert lessons[0]["id"] == "L001"
        assert lessons[1]["id"] == "L002"
        assert lessons[2]["id"] == "L003"
