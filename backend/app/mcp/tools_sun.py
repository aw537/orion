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
    current_focus: str | None = None,
    add_blocker: str | None = None,
    remove_blocker: str | None = None,
    add_decision: str | None = None,
    add_hot_biome: str | None = None,
    remove_hot_biome: str | None = None,
    clear_decisions: bool = False,
) -> dict:
    """Quick-update the working context scratchpad.

    Operations:
    - current_focus: set what you're working on right now
    - add_blocker / remove_blocker: manage the blockers list
    - add_hot_biome / remove_hot_biome: manage frequently-accessed biomes
    - add_decision: append a decision to recent_decisions
    - clear_decisions: wipe the recent_decisions list
    """
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        section = await sun_service.get_section(galaxy_id, "working_context", db)
        if not section:
            return {"error": "working_context section not found"}
        import copy
        wc = copy.deepcopy(section.get("content", {}))
        changed = False
        if current_focus is not None:
            wc["current_focus"] = current_focus
            changed = True
        if add_blocker:
            wc.setdefault("blockers", []).append(add_blocker)
            changed = True
        if remove_blocker:
            blockers = wc.get("blockers", [])
            wc["blockers"] = [b for b in blockers if b != remove_blocker]
            changed = True
        if add_decision:
            wc.setdefault("recent_decisions", []).append(add_decision)
            changed = True
        if clear_decisions:
            wc["recent_decisions"] = []
            changed = True
        if add_hot_biome:
            hot = wc.get("hot_biomes", [])
            if add_hot_biome not in hot:
                hot.append(add_hot_biome)
            wc["hot_biomes"] = hot
            changed = True
        if remove_hot_biome:
            wc["hot_biomes"] = [b for b in wc.get("hot_biomes", []) if b != remove_hot_biome]
            changed = True
        if not changed:
            return {"status": "no changes", "content": wc}
        wc["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        result = await sun_service.update_section(galaxy_id, "working_context", wc, "agent", "Working context updated", db)
        return result


async def sun_lesson(
    correction: str, context: str = "", tags: list[str] | None = None,
    severity: str = "medium", agent_name: str = "mcp_client",
) -> dict:
    """Record a lesson learned permanently in the Sun."""
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        return await sun_service.append_lesson(galaxy_id, correction, context, tags or [], agent_name, severity, db)


async def sun_lesson_list(
    tags: list[str] | None = None, limit: int = 20, include_resolved: bool = False,
) -> dict:
    """List lessons recorded in the Sun. Active lessons only by default.

    Parameters:
    - tags: filter to lessons matching any of these topic tags
    - limit: max number of lessons to return (default 20)
    - include_resolved: set True to also return lessons already marked resolved
    """
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        entries = await sun_service.get_lessons(galaxy_id, tags, limit, include_resolved, db)
        return {"lessons": entries, "total": len(entries)}


async def sun_lesson_resolve(lesson_id: str) -> dict:
    """Mark a lesson as resolved. The lesson remains in history but is excluded from active lists.

    Parameters:
    - lesson_id: the lesson ID (e.g. 'L001') from sun.lesson_list
    """
    galaxy_id = await _get_galaxy_id()
    if not galaxy_id:
        return {"error": "No galaxy found"}
    async with async_session() as db:
        try:
            entry = await sun_service.resolve_lesson(galaxy_id, lesson_id, db)
            return {"status": "resolved", "lesson": entry}
        except KeyError as e:
            return {"error": str(e)}
        except ValueError as e:
            return {"error": str(e)}
