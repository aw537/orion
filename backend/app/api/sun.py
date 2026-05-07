from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy
from app.auth.dependencies import get_galaxy_for_user
from app.services import sun_service

router = APIRouter(prefix="/api/v1/sun", tags=["sun"])


class SunSectionUpdateBody(BaseModel):
    content: dict
    changed_by: str = "user"
    summary: str = ""


class AddBlockerBody(BaseModel):
    blocker: str


class RemoveBlockerBody(BaseModel):
    blocker: str


class AddHotBiomeBody(BaseModel):
    biome: str


class RemoveHotBiomeBody(BaseModel):
    biome: str


class AddDecisionBody(BaseModel):
    decision: str
    biome: str = ""


class AppendLessonBody(BaseModel):
    correction: str
    context: str = ""
    tags: list[str] = []
    agent_name: str = "user"
    severity: str = "medium"


@router.post("/steering-doc/reimport")
async def reimport_steering_doc(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    try:
        return await sun_service.reimport_steering_doc(galaxy.id, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("")
async def get_full_sun(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    return await sun_service.get_full_sun(galaxy.id, db)


@router.get("/evolution-log")
async def get_evolution_log(limit: int = Query(default=50, le=200), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    return await sun_service.get_evolution_log(galaxy.id, limit, db)


@router.post("/lessons")
async def append_lesson(body: AppendLessonBody, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    try:
        return await sun_service.append_lesson(galaxy.id, body.correction, body.context, body.tags, body.agent_name, body.severity, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/lessons")
async def get_lessons(tags: str = Query(default="", description="Comma-separated tags to filter by"), limit: int = Query(default=50, le=200), include_resolved: bool = Query(default=False), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return await sun_service.get_lessons(galaxy.id, tag_list, limit, include_resolved, db)


@router.post("/lessons/{lesson_id}/resolve")
async def resolve_lesson(lesson_id: str, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    try:
        return await sun_service.resolve_lesson(galaxy.id, lesson_id, db)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{section_key}")
async def get_section(section_key: str, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    result = await sun_service.get_section(galaxy.id, section_key, db)
    if not result:
        raise HTTPException(404, f"Section '{section_key}' not found")
    return result


@router.put("/{section_key}")
async def update_section(section_key: str, body: SunSectionUpdateBody, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    try:
        return await sun_service.update_section(galaxy.id, section_key, body.content, body.changed_by, body.summary, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/working-context/add-blocker")
async def add_blocker(body: AddBlockerBody, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    section = await sun_service.get_section(galaxy.id, "working_context", db)
    if not section:
        raise HTTPException(404, "working_context section not found")
    content = section["content"]
    blockers = content.get("blockers", [])
    blockers.append(body.blocker)
    content["blockers"] = blockers
    content["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return await sun_service.update_section(galaxy.id, "working_context", content, "user", f"Added blocker: {body.blocker[:50]}", db)


@router.post("/working-context/add-decision")
async def add_decision(body: AddDecisionBody, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    section = await sun_service.get_section(galaxy.id, "working_context", db)
    if not section:
        raise HTTPException(404, "working_context section not found")
    content = section["content"]
    decisions = content.get("recent_decisions", [])
    decisions.append({"decision": body.decision, "date": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), "biome": body.biome})
    content["recent_decisions"] = decisions
    content["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return await sun_service.update_section(galaxy.id, "working_context", content, "user", f"Added decision: {body.decision[:50]}", db)


@router.post("/working-context/add-hot-biome")
async def add_hot_biome(body: AddHotBiomeBody, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    section = await sun_service.get_section(galaxy.id, "working_context", db)
    if not section:
        raise HTTPException(404, "working_context section not found")
    content = section["content"]
    hot = content.get("hot_biomes", [])
    if body.biome not in hot:
        hot.append(body.biome)
    content["hot_biomes"] = hot
    content["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return await sun_service.update_section(galaxy.id, "working_context", content, "agent", f"Added hot biome: {body.biome}", db)


@router.post("/working-context/remove-blocker")
async def remove_blocker(body: RemoveBlockerBody, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    section = await sun_service.get_section(galaxy.id, "working_context", db)
    if not section:
        raise HTTPException(404, "working_context section not found")
    content = section["content"]
    content["blockers"] = [b for b in content.get("blockers", []) if b != body.blocker]
    content["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return await sun_service.update_section(galaxy.id, "working_context", content, "agent", f"Removed blocker: {body.blocker[:50]}", db)


@router.post("/working-context/remove-hot-biome")
async def remove_hot_biome(body: RemoveHotBiomeBody, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    section = await sun_service.get_section(galaxy.id, "working_context", db)
    if not section:
        raise HTTPException(404, "working_context section not found")
    content = section["content"]
    content["hot_biomes"] = [b for b in content.get("hot_biomes", []) if b != body.biome]
    content["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return await sun_service.update_section(galaxy.id, "working_context", content, "agent", f"Removed hot biome: {body.biome}", db)


@router.post("/working-context/clear-decisions")
async def clear_decisions(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    section = await sun_service.get_section(galaxy.id, "working_context", db)
    if not section:
        raise HTTPException(404, "working_context section not found")
    content = section["content"]
    content["recent_decisions"] = []
    content["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return await sun_service.update_section(galaxy.id, "working_context", content, "agent", "Cleared recent decisions", db)
