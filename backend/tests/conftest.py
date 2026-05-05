"""Shared test fixtures for Orion backend tests."""
import sys
import os
import pytest
import pytest_asyncio
from unittest.mock import patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override database URL before any app imports — tests use in-memory SQLite
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
# Enable auth bypass for all tests — tests don't need to pass tokens
os.environ["ORION_AUTH_DISABLED"] = "true"

from app.models import Base, Galaxy, Planet, Biome
from app.database import get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_SERVICE_MODULES = [
    "app.database",
    "app.services.sun_service",
    "app.services.stardust_service",
    "app.services.galaxy_service",
    "app.services.nebula_service",
    "app.services.context_service",
    "app.services.audit_service",
    "app.services.import_service",
    "app.services.search_service",
    "app.services.agent_identity_service",
    "app.services.brain_health_service",
    "app.services.calibration_service",
    "app.services.graph_service",
    "app.services.model_switch_service",
    "app.services.orientation_service",
    "app.services.knowledge_integration_engine",
    "app.services.planet_assignment_engine",
    "app.mcp.tools_brain",
    "app.mcp.tools_memory",
    "app.mcp.tools_sun",
    "app.mcp.session",
    "app.mcp.utils",
    "app.mcp.server",
    "app.api.agents",
    "app.api.graph",
    "app.api.galaxy",
    "app.api.merge",
    "app.main",
    "app.scheduler.audit_scheduler",
]


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite async session for unit tests."""
    engine = create_async_engine(TEST_DB_URL, echo=False, connect_args={"check_same_thread": False})
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_galaxy(db):
    """Create a Galaxy + 2 Planets + 1 Biome, return dict of IDs."""
    from uuid import uuid4
    from datetime import datetime, timezone

    galaxy = Galaxy(
        id=str(uuid4()), name="Test Galaxy",
        created_at=datetime.now(timezone.utc),
        strength_score=0.5, total_nodes=0, schema_version="0.1.0",
    )
    db.add(galaxy)

    eng = Planet(
        id=str(uuid4()), galaxy_id=galaxy.id, name="Engineering",
        stardust_count=0, health_status="healthy",
    )
    personal = Planet(
        id=str(uuid4()), galaxy_id=galaxy.id, name="Personal",
        stardust_count=0, health_status="healthy",
    )
    db.add_all([eng, personal])

    biome = Biome(
        id=str(uuid4()), planet_id=eng.id, galaxy_id=galaxy.id,
        name="Test Biome", lifecycle_state="ACTIVE",
    )
    db.add(biome)
    await db.commit()

    return {
        "galaxy_id": galaxy.id, "galaxy": galaxy,
        "engineering_planet_id": eng.id, "personal_planet_id": personal.id,
        "biome_id": biome.id,
    }


@pytest_asyncio.fixture
async def client():
    """ASGI test client with in-memory SQLite and patched service modules."""
    engine = create_async_engine(TEST_DB_URL, echo=False, connect_args={"check_same_thread": False})
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with factory() as session:
            yield session

    active_patches = []
    for mod in _SERVICE_MODULES:
        try:
            p = patch(f"{mod}.async_session", factory)
            p.start()
            active_patches.append(p)
        except AttributeError:
            pass

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    for p in active_patches:
        p.stop()
    await engine.dispose()
