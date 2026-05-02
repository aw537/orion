"""Shared utilities for MCP and API modules."""
from sqlalchemy import select
from app.database import async_session
from app.models import Galaxy


async def get_galaxy_id() -> str | None:
    """Return the ID of the first Galaxy, or None.

    Used by MCP tools and background tasks that don't have request context.
    For REST endpoints, use get_galaxy_for_user dependency instead.
    """
    async with async_session() as db:
        galaxy = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
        return galaxy.id if galaxy else None
