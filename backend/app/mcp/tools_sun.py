"""Sun namespace — Galaxy steering document tools."""
import logging
from datetime import datetime, timezone
from app.database import async_session
from app.services import sun_service
from app.mcp.utils import get_galaxy_id as _get_galaxy_id

logger = logging.getLogger(__name__)


async def sun_read(section: str | None = None) -> dict:
    """Read the Galaxy's Sun — the steering document for all agents."""
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    if section:
        async with async_session() as db:
            result = await sun_service.get_section(galaxy_id, section, db)
            return result or {"error": f"Section '{section}' not found"}
    return await sun_service.get_full_sun(galaxy_id)


async def sun_update(section_key: str, content: dict, summary: str) -> dict:
    """Update a Sun section. Changes logged to evolution_log."""
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        result = await sun_service.update_section(galaxy_id, section_key, content, "agent", summary, db)
        return result


async def sun_working_context(
    current_focus: str | None = None, add_blocker: str | None = None,
    add_decision: str | None = None, add_hot_biome: str | None = None,
) -> dict:
    """Quick-update the working context scratchpad."""
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        section = await sun_service.get_section(galaxy_id, "working_context", db)
        if not section:
            return {"error": "working_context section not found"}
        wc = section.get("content", {})
        if current_focus is not None:
            wc["current_focus"] = current_focus
        if add_blocker:
            wc.setdefault("blockers", []).append(add_blocker)
        if add_decision:
            wc.setdefault("recent_decisions", []).append(add_decision)
        if add_hot_biome:
            hot = wc.get("hot_biomes", [])
            if add_hot_biome not in hot:
                hot.append(add_hot_biome)
            wc["hot_biomes"] = hot
        wc["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        result = await sun_service.update_section(galaxy_id, "working_context", wc, "agent", "Working context updated", db)
        return result
