"""Integration tests for Orion critical paths."""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.models import Base
from app.database import get_db

# client fixture is provided by conftest.py


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["service"] == "orion-api"


@pytest.mark.asyncio
async def test_galaxy_empty(client):
    resp = await client.get("/api/v1/galaxy")
    assert resp.status_code == 404
    # Returns 404 when no galaxy exists (auth requires galaxy)


@pytest.mark.asyncio
async def test_onboarding_creates_galaxy(client):
    resp = await client.post("/api/v1/onboarding/start", json={
        "role": "Developer",
        "first_biome_name": "Test Project",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["galaxy_id"]
    assert "Engineering" in data["planets"]
    assert "Personal" in data["planets"]
    assert data["first_biome_id"]


@pytest.mark.asyncio
async def test_onboarding_rejects_duplicate(client):
    # First onboarding
    await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
    # Second returns existing galaxy (idempotent)
    resp = await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test2"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_planets_list(client):
    await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
    resp = await client.get("/api/v1/planets")
    assert resp.status_code == 200
    planets = resp.json()
    standard = [p for p in planets if p["planet_type"] == "standard"]
    assert len(standard) == 2
    names = {p["name"] for p in standard}
    assert names == {"Engineering", "Personal"}


@pytest.mark.asyncio
async def test_galaxy_status(client):
    await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
    resp = await client.get("/api/v1/galaxy/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["galaxy_name"]
    # onboarding creates 2 standard planets (role-based) + 1 inbox planet
    assert len(data["planets"]) == 3


@pytest.mark.asyncio
async def test_nebula_log_empty(client):
    await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
    resp = await client.get("/api/v1/nebula")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data


@pytest.mark.asyncio
async def test_nebula_dashboard(client):
    await client.post("/api/v1/onboarding/start", json={"role": "Developer", "first_biome_name": "Test"})
    resp = await client.get("/api/v1/nebula/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data


@pytest.mark.asyncio
async def test_audit_status_no_runs(client):
    resp = await client.get("/api/v1/audit/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_entity_extraction_logic():
    """Test entity extractor directly."""
    from app.extraction.entity_extractor import EntityExtractor
    extractor = EntityExtractor()
    entities = extractor.extract("John Smith decided to use FastAPI and Redis for the backend. @alice mentioned AWS.", "test-galaxy")
    names = {e.name for e in entities}
    types = {e.entity_type for e in entities}
    assert "John Smith" in names
    assert "FastAPI" in names
    assert "Redis" in names
    assert "AWS" in names
    assert "person" in types
    assert "tool" in types
    assert "organization" in types


@pytest.mark.asyncio
async def test_region_inference():
    """Test signal detector region inference."""
    from app.extraction.signal_detector import infer_region_from_content
    assert infer_region_from_content("We decided because the tradeoff analysis showed this was the reason to evaluate") == "analytical"
    assert infer_region_from_content("Step 1: install the package. Then run the process. Next execute the workflow.") == "procedural"
    assert infer_region_from_content("The weather is nice today.") == "contextual"


@pytest.mark.asyncio
async def test_markdown_chunking():
    """Test paragraph chunking."""
    from app.services.import_service import chunk_by_paragraph
    text = "Paragraph one about topic A.\n\nParagraph two about topic B.\n\nParagraph three about topic C."
    chunks = chunk_by_paragraph(text, max_tokens=20)
    assert len(chunks) >= 1
    assert all(len(c.strip()) > 0 for c in chunks)


@pytest.mark.asyncio
async def test_frontmatter_parsing():
    """Test YAML frontmatter extraction."""
    from app.services.import_service import parse_frontmatter
    content = "---\ntitle: Test\ntags: [python, backend]\n---\n\nBody content here."
    meta, body = parse_frontmatter(content)
    assert meta["title"] == "Test"
    assert "python" in meta["tags"]
    assert "Body content here." in body
