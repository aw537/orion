"""Sun Service — structured 6-section steering document."""
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models import SunSection, Planet, Biome
from app.services import nebula_service

logger = logging.getLogger(__name__)

SUN_SECTIONS = ["identity", "values", "agent_protocol", "planet_registry", "working_context", "evolution_log", "steering_doc", "lessons"]

DEFAULT_STEERING_DOC = """# Steering Document

This is your free-form steering document. It's always available to every agent that connects to your Galaxy.

Use it to define tone, behavior conventions, project-specific rules, or anything you want agents to follow.

You can paste an existing CLAUDE.md, .cursorrules, or any markdown content here.
"""

DEFAULT_SUN = {
    "identity": {"name": "", "role": "", "primary_domain": "", "working_style": "", "timezone": "", "galaxy_purpose": ""},
    "values": {"principles": [], "communication_style": "direct", "contradiction_preference": "flag_and_ask", "citation_required": True},
    "agent_protocol": {"write_rules": [], "read_rules": [], "uncertainty_handling": "Flag low-confidence results explicitly.", "session_start_instruction": "Call brain.orient to register your agent identity and load current Galaxy context. Required at the start of every session.", "session_end_instruction": "Use brain.think to persist new decisions and learnings before ending the session. Then call brain.calibrate to improve future retrieval."},
    "planet_registry": {"planets": []},
    "working_context": {"current_focus": "", "hot_biomes": [], "recent_decisions": [], "blockers": [], "updated_at": ""},
    "evolution_log": {"entries": []},
    "steering_doc": {"markdown": DEFAULT_STEERING_DOC, "source_path": None},
    "lessons": {"entries": []},
}


def _parse_content(content) -> dict:
    if isinstance(content, dict):
        return content
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {}


async def get_section(galaxy_id: str, section_key: str, db: AsyncSession) -> dict | None:
    row = (await db.execute(
        select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == section_key)
    )).scalar_one_or_none()
    if not row:
        return None
    return {"section_key": row.section_key, "content": _parse_content(row.content), "version": row.version, "updated_at": row.updated_at.isoformat() if row.updated_at else ""}


async def get_full_sun(galaxy_id: str, db: AsyncSession | None = None) -> dict:
    async def _fetch(session):
        rows = (await session.execute(
            select(SunSection).where(SunSection.galaxy_id == galaxy_id)
        )).scalars().all()
        sun = {r.section_key: _parse_content(r.content) for r in rows}
        # Virtual 7th section: aggregate Planet protocol overrides
        from app.models import Planet
        planets = (await session.execute(
            select(Planet).where(Planet.galaxy_id == galaxy_id, Planet.protocol_override.isnot(None))
        )).scalars().all()
        if planets:
            overrides = {}
            for p in planets:
                try:
                    overrides[p.name] = json.loads(p.protocol_override)
                except (json.JSONDecodeError, TypeError):
                    pass
            if overrides:
                sun["planet_protocol_overrides"] = overrides
        return sun

    if db:
        return await _fetch(db)
    async with async_session() as session:
        return await _fetch(session)


async def update_section(galaxy_id: str, section_key: str, content: dict, changed_by: str, summary: str, db: AsyncSession) -> dict:
    if section_key not in SUN_SECTIONS:
        raise ValueError(f"Invalid section: {section_key}. Must be one of {SUN_SECTIONS}")
    if section_key == "evolution_log":
        raise ValueError("evolution_log is append-only and cannot be directly updated")

    row = (await db.execute(
        select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == section_key)
    )).scalar_one_or_none()
    if not row:
        raise ValueError(f"Section '{section_key}' not found")

    previous = row.content
    row.content = content
    row.version += 1
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()

    # Append to evolution_log
    await _append_evolution_entry(galaxy_id, section_key, changed_by, summary, previous, db)

    # Log to interaction_log
    action = "HUMAN_EDIT" if changed_by == "user" else "WRITE"
    await nebula_service.log_event(galaxy_id=galaxy_id, action_type=action, initiated_by=changed_by, record_id=row.id, db=db)

    await db.commit()
    await db.refresh(row)
    return {"section_key": row.section_key, "content": _parse_content(row.content), "version": row.version, "updated_at": row.updated_at.isoformat()}


async def _append_evolution_entry(galaxy_id: str, section_changed: str, changed_by: str, summary: str, previous_value: str, db: AsyncSession):
    evo_row = (await db.execute(
        select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == "evolution_log")
    )).scalar_one_or_none()
    if not evo_row:
        return
    log = _parse_content(evo_row.content)
    entries = log.get("entries", [])
    entries.append({
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "section_changed": section_changed,
        "changed_by": changed_by,
        "summary": summary,
        "previous_value_snapshot": (json.dumps(previous_value) if isinstance(previous_value, (dict, list)) else str(previous_value))[:500],
    })
    evo_row.content = {"entries": entries}
    evo_row.version += 1
    evo_row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


async def update_planet_registry(galaxy_id: str, db: AsyncSession | None = None):
    async def _do(session, should_commit):
        planets = (await session.execute(select(Planet).where(Planet.galaxy_id == galaxy_id))).scalars().all()
        registry = []
        for p in planets:
            biomes = (await session.execute(
                select(Biome.name).where(Biome.planet_id == p.id, Biome.lifecycle_state.in_(["SEED", "ACTIVE", "MATURE"]))
            )).scalars().all()
            registry.append({"name": p.name, "purpose": p.description or "", "active_biomes": list(biomes), "primary_region": "contextual"})

        row = (await session.execute(
            select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == "planet_registry")
        )).scalar_one_or_none()
        if row:
            row.content = {"planets": registry}
            row.version += 1
            row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if should_commit:
                await session.commit()

    if db:
        await _do(db, False)
    else:
        async with async_session() as session:
            await _do(session, True)


async def initialize_sun(galaxy_id: str, wizard_answers: dict, db: AsyncSession, steering_doc_content: str | None = None, steering_doc_path: str | None = None):
    """Create all 7 Sun sections from onboarding wizard answers."""
    import uuid
    sun = {k: dict(v) if isinstance(v, dict) else v for k, v in DEFAULT_SUN.items()}

    # Populate identity from wizard
    if "name" in wizard_answers:
        sun["identity"]["name"] = wizard_answers["name"]
    if "role" in wizard_answers:
        sun["identity"]["role"] = wizard_answers["role"]
    if "timezone" in wizard_answers:
        sun["identity"]["timezone"] = wizard_answers["timezone"]

    # Populate values from wizard
    if "communication_style" in wizard_answers:
        sun["values"]["communication_style"] = wizard_answers["communication_style"]
    if "contradiction_preference" in wizard_answers:
        sun["values"]["contradiction_preference"] = wizard_answers["contradiction_preference"]
    if "principles" in wizard_answers:
        sun["values"]["principles"] = wizard_answers["principles"]

    # Populate agent_protocol from wizard
    if "write_rules" in wizard_answers:
        sun["agent_protocol"]["write_rules"] = wizard_answers["write_rules"]
    if "session_start_instruction" in wizard_answers:
        sun["agent_protocol"]["session_start_instruction"] = wizard_answers["session_start_instruction"]
    if "session_end_instruction" in wizard_answers:
        sun["agent_protocol"]["session_end_instruction"] = wizard_answers["session_end_instruction"]

    # Working context
    if "current_focus" in wizard_answers:
        sun["working_context"]["current_focus"] = wizard_answers["current_focus"]
        sun["working_context"]["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    # Steering doc
    if steering_doc_content:
        sun["steering_doc"] = {"markdown": steering_doc_content, "source_path": steering_doc_path}

    for key, content in sun.items():
        from sqlalchemy import insert
        await db.execute(insert(SunSection).values(
            id=str(uuid.uuid4()), galaxy_id=galaxy_id,
            section_key=key, content=content,
        ))


async def get_evolution_log(galaxy_id: str, limit: int = 50, db: AsyncSession | None = None) -> list:
    async def _fetch(session):
        row = (await session.execute(
            select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == "evolution_log")
        )).scalar_one_or_none()
        if not row:
            return []
        log = _parse_content(row.content)
        entries = log.get("entries", [])
        return entries[-limit:]

    if db:
        return await _fetch(db)
    async with async_session() as session:
        return await _fetch(session)


async def append_lesson(galaxy_id: str, correction: str, context: str, tags: list[str], agent_name: str, severity: str = "medium", db: AsyncSession | None = None) -> dict:
    """Append a lesson to the Sun's lessons section. Append-only."""
    async def _do(session, should_commit: bool):
        row = (await session.execute(
            select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == "lessons")
        )).scalar_one_or_none()
        if not row:
            raise ValueError("lessons section not found — run onboarding first")
        content = _parse_content(row.content)
        entries = content.get("entries", [])
        entry = {
            "id": f"L{len(entries) + 1:03d}",
            "correction": correction,
            "context": context,
            "tags": tags,
            "severity": severity,
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "status": "active",
        }
        entries.append(entry)
        row.content = {"entries": entries}
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(row, "content")
        row.version += 1
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if should_commit:
            await session.commit()
        else:
            await session.flush()
        return entry

    if db:
        return await _do(db, should_commit=True)
    async with async_session() as session:
        return await _do(session, should_commit=True)


async def get_lessons(galaxy_id: str, tags: list[str] | None = None, limit: int = 50, include_resolved: bool = False, db: AsyncSession | None = None) -> list[dict]:
    """Get lessons, optionally filtered by tags. Active only by default; set include_resolved=True to include resolved ones."""
    async def _fetch(session):
        row = (await session.execute(
            select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == "lessons")
        )).scalar_one_or_none()
        if not row:
            return []
        content = _parse_content(row.content)
        entries = content.get("entries", [])
        if tags:
            entries = [e for e in entries if any(t in e.get("tags", []) for t in tags)]
        if not include_resolved:
            entries = [e for e in entries if e.get("status") == "active"]
        return entries[-limit:]

    if db:
        return await _fetch(db)
    async with async_session() as session:
        return await _fetch(session)


async def resolve_lesson(galaxy_id: str, lesson_id: str, db: AsyncSession | None = None) -> dict:
    """Mark a lesson as resolved. Returns the updated lesson entry."""
    async def _do(session, should_commit: bool):
        row = (await session.execute(
            select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == "lessons")
        )).scalar_one_or_none()
        if not row:
            raise ValueError("lessons section not found")
        content = _parse_content(row.content)
        entries = content.get("entries", [])
        target = next((e for e in entries if e.get("id") == lesson_id), None)
        if not target:
            raise KeyError(f"Lesson '{lesson_id}' not found")
        target["status"] = "resolved"
        target["resolved_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        row.content = {"entries": entries}
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(row, "content")
        row.version += 1
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if should_commit:
            await session.commit()
        else:
            await session.flush()
        return target

    if db:
        return await _do(db, should_commit=True)
    async with async_session() as session:
        return await _do(session, should_commit=True)


async def reimport_steering_doc(galaxy_id: str, db: AsyncSession) -> dict:
    """Re-read the steering doc from its stored source_path."""
    import os
    row = (await db.execute(
        select(SunSection).where(SunSection.galaxy_id == galaxy_id, SunSection.section_key == "steering_doc")
    )).scalar_one_or_none()
    if not row:
        raise ValueError("steering_doc section not found")
    content = _parse_content(row.content)
    source_path = content.get("source_path")
    if not source_path:
        raise ValueError("No source_path stored — this steering doc was not imported from a file")
    resolved = os.path.realpath(os.path.expanduser(source_path))
    if not os.path.isfile(resolved):
        raise ValueError(f"File not found: {resolved}")
    with open(resolved, "r", encoding="utf-8") as f:
        markdown = f.read()
    previous = row.content
    row.content = {"markdown": markdown, "source_path": source_path}
    row.version += 1
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await _append_evolution_entry(galaxy_id, "steering_doc", "user", "Re-imported from file", previous, db)
    await db.commit()
    await db.refresh(row)
    return {"section_key": "steering_doc", "content": _parse_content(row.content), "version": row.version, "updated_at": row.updated_at.isoformat()}
