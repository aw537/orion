import json
import logging
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy, Planet, Biome, Stardust, Entity
from app.services import nebula_service, sun_service
from app.storage.chroma_client import ChromaClient, get_chroma_client

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

PLANET_COLORS = {"Engineering": "#6D28D9", "Personal": "#0EA5E9", "Product": "#F59E0B", "Design": "#EC4899", "Research": "#10B981", "General": "#6B7280"}

ROLE_PLANETS = {
    "Software Engineer": ["Engineering", "Personal"],
    "Technical Founder": ["Engineering", "Product", "Personal"],
    "Designer": ["Design", "Personal"],
    "Researcher": ["Research", "Personal"],
    "Developer": ["Engineering", "Personal"],
    "Other": ["General", "Personal"],
}

ROLE_SUN_DEFAULTS = {
    "Software Engineer": {
        "principles": ["Cite the specific Biome when referencing prior decisions.", "Prefer concrete examples over abstract explanations.", "Flag contradictions rather than silently overwriting.", "When uncertain, say so explicitly with a confidence estimate."],
        "write_rules": ["Write Stardust records for architectural decisions with full rationale.", "Record tool evaluations with both pros and cons.", "Capture error resolutions — what failed and what fixed it."],
    },
    "Developer": {
        "principles": ["Cite the specific Biome when referencing prior decisions.", "Prefer concrete examples over abstract explanations.", "Flag contradictions rather than silently overwriting."],
        "write_rules": ["Write Stardust records for architectural decisions with full rationale.", "Record tool evaluations with both pros and cons."],
    },
}


class ArchitecturalDecision(BaseModel):
    decision: str
    reasoning: str


class OnboardingRequest(BaseModel):
    role: str
    import_path: str | None = None
    source_type: str = "folder"
    first_biome_name: str = "General"
    # Extended v0.5 fields
    name: str = ""
    goal: str = ""
    tools: list[str] = []
    communication_style: str = "direct"
    contradiction_preference: str = "flag_and_ask"
    # H1.2 — Structured onboarding fields
    codebase_description: str = ""
    framework: str = ""
    architectural_decisions: list[ArchitecturalDecision] = []
    reexplanation_frustrations: list[str] = []
    ai_frustrations: list[str] = []
    steering_doc_path: str | None = None


class OnboardingResponse(BaseModel):
    galaxy_id: str
    planets: list[str]
    first_biome_id: str
    import_started: bool = False
    stardust_count: int = 0
    entities_count: int = 0
    sun_configured: bool = False
    knowledge_gaps_count: int = 0


@router.post("/start", response_model=OnboardingResponse, status_code=201)
async def start_onboarding(body: OnboardingRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Galaxy already exists. Onboarding already completed.")

    galaxy_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create galaxy
    await db.execute(insert(Galaxy).values(id=galaxy_id, name=f"{body.role}'s Galaxy", created_at=now))

    # Create planets based on role
    planet_names = ROLE_PLANETS.get(body.role, ["General", "Personal"])
    planet_ids = {}
    for name in planet_names:
        pid = str(uuid.uuid4())
        planet_ids[name] = pid
        await db.execute(insert(Planet).values(id=pid, galaxy_id=galaxy_id, name=name, color=PLANET_COLORS.get(name, "#6D28D9")))

    # Create first biome
    first_planet_id = planet_ids[planet_names[0]]
    biome_id = str(uuid.uuid4())
    await db.execute(insert(Biome).values(id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id, name=body.first_biome_name, lifecycle_state="ACTIVE", created_at=now, last_active_at=now))

    # Initialize Sun with role defaults + wizard answers
    role_defaults = ROLE_SUN_DEFAULTS.get(body.role, ROLE_SUN_DEFAULTS.get("Developer", {}))
    wizard = {
        "name": body.name,
        "role": body.role,
        "communication_style": body.communication_style,
        "contradiction_preference": body.contradiction_preference,
        "principles": role_defaults.get("principles", []),
        "write_rules": role_defaults.get("write_rules", []),
        "session_start_instruction": "Call orion_context to load current project context.",
        "session_end_instruction": "Write any new decisions or learnings to the active Biome.",
        "current_focus": body.goal or body.first_biome_name,
    }
    await sun_service.initialize_sun(galaxy_id, wizard, db,
        steering_doc_content=_read_steering_doc(body.steering_doc_path),
        steering_doc_path=body.steering_doc_path)

    # Seed stardust records if goal/tools provided
    stardust_count = 0
    entities_count = 0
    knowledge_gaps_count = 0

    # H1.2: Codebase description → 2 Contextual Stardust
    if body.framework:
        sd = Stardust(
            id=str(uuid.uuid4()), biome_id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id,
            content=f"Primary stack: {body.framework}", region="contextual", gravity="PLANET",
            confidence=0.9, valid_from=now, source_agent="onboarding", created_at=now,
        )
        sd.context_tags = []
        db.add(sd)
        stardust_count += 1
    if body.codebase_description:
        sd = Stardust(
            id=str(uuid.uuid4()), biome_id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id,
            content=f"Project purpose: {body.codebase_description}", region="contextual", gravity="PLANET",
            confidence=0.9, valid_from=now, source_agent="onboarding", created_at=now,
        )
        sd.context_tags = []
        db.add(sd)
        stardust_count += 1

    # H1.2: Architectural decisions → Analytical Stardust with reasoning
    for dec in body.architectural_decisions:
        sd = Stardust(
            id=str(uuid.uuid4()), biome_id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id,
            content=dec.decision, region="analytical", gravity="PLANET",
            confidence=0.9, valid_from=now, source_agent="onboarding", created_at=now,
            reasoning=dec.reasoning,
        )
        sd.context_tags = []
        db.add(sd)
        stardust_count += 1

    # H1.2: Tools → Entity records + 1 Procedural Stardust
    if body.tools:
        tools_str = ", ".join(body.tools)
        sd2 = Stardust(
            id=str(uuid.uuid4()), biome_id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id,
            content=f"Primary tools: {tools_str}", region="procedural", gravity="PLANET",
            confidence=0.7, valid_from=now, source_agent="onboarding", created_at=now,
        )
        sd2.context_tags = body.tools
        db.add(sd2)
        stardust_count += 1
        for tool in body.tools:
            db.add(Entity(id=str(uuid.uuid4()), galaxy_id=galaxy_id, planet_id=first_planet_id, name=tool, entity_type="tool"))
            entities_count += 1

    # H1.2: Re-explanation frustrations → GALAXY gravity, high confidence
    for frustration in body.reexplanation_frustrations:
        sd = Stardust(
            id=str(uuid.uuid4()), biome_id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id,
            content=frustration, region="contextual", gravity="GALAXY",
            confidence=0.95, valid_from=now, source_agent="onboarding", created_at=now,
        )
        sd.context_tags = []
        db.add(sd)
        stardust_count += 1

    # H1.2: AI frustrations → GALAXY-gravity contextual stardust (no real session yet)
    for frustration in body.ai_frustrations:
        sd = Stardust(
            id=str(uuid.uuid4()), biome_id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id,
            content=f"AI frustration to avoid: {frustration}", region="contextual", gravity="GALAXY",
            confidence=0.95, valid_from=now, source_agent="onboarding", created_at=now,
        )
        sd.context_tags = ["ai_frustration"]
        db.add(sd)
        stardust_count += 1
        knowledge_gaps_count += 1

    # Create SessionCalibration record if there are knowledge gaps
    if body.ai_frustrations:
        from app.models.brain import SessionCalibration
        db.add(SessionCalibration(
            id=str(uuid.uuid4()), session_id="onboarding",
            agent_identity_id="onboarding", galaxy_id=galaxy_id,
            knowledge_gaps=body.ai_frustrations,
        ))

    # Legacy: goal-based seeding (if no H1.2 fields provided)
    if body.goal and not body.codebase_description:
        sd = Stardust(
            id=str(uuid.uuid4()), biome_id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id,
            content=f"Current focus: {body.goal}", region="analytical", gravity="BIOME",
            confidence=0.7, valid_from=now, source_agent="onboarding", created_at=now,
        )
        sd.context_tags = []
        db.add(sd)
        stardust_count += 1

    # Update biome/planet counts
    from sqlalchemy import update
    await db.execute(update(Biome).where(Biome.id == biome_id).values(stardust_count=stardust_count))
    await db.execute(update(Planet).where(Planet.id == first_planet_id).values(stardust_count=stardust_count))

    await db.commit()

    # Update planet registry in Sun
    await sun_service.update_planet_registry(galaxy_id)

    # Ensure Chroma collections in background — sync HTTP calls should not block the response
    def _init_chroma_collections(_galaxy_id: str = galaxy_id) -> None:
        try:
            chroma = ChromaClient(get_chroma_client())
            chroma.ensure_collections(_galaxy_id)
        except Exception:
            pass

    background_tasks.add_task(_init_chroma_collections)

    await nebula_service.log_event(galaxy_id=galaxy_id, action_type="SESSION_START", initiated_by="onboarding")

    # Background import — non-fatal if path is inaccessible from this process (e.g. inside Docker)
    import_started = False
    if body.import_path:
        resolved = None
        try:
            resolved = _validate_import_path(body.import_path)
        except Exception as e:
            logger.warning(f"Import path '{body.import_path}' not accessible: {e}")
            # Fallback: when running in Docker, the Obsidian vault is mounted at /vault
            if body.source_type == "obsidian" and os.path.isdir("/vault"):
                logger.info("Falling back to Docker-mounted vault at /vault")
                resolved = "/vault"
        if resolved:
            try:
                from app.services import import_service
                background_tasks.add_task(import_service.import_markdown_folder, resolved, first_planet_id, galaxy_id)
                import_started = True
            except Exception as e:
                logger.error(f"Failed to schedule import task: {e}")

    return OnboardingResponse(
        galaxy_id=galaxy_id, planets=planet_names, first_biome_id=biome_id,
        import_started=import_started, stardust_count=stardust_count,
        entities_count=entities_count, sun_configured=True,
        knowledge_gaps_count=knowledge_gaps_count,
    )


_IMPORT_MAX_FILES = 500
_IMPORT_MAX_DEPTH = 5

# Safe base directories for import/steering doc reads
_SAFE_BASES = [
    os.path.expanduser("~"),  # user home
    "/vault",                  # Docker-mounted vault
    "/tmp",                    # temp files
]


def _is_safe_path(resolved: str) -> bool:
    """Check that resolved path is under an allowed base directory."""
    return any(resolved.startswith(os.path.realpath(b) + os.sep) or resolved == os.path.realpath(b) for b in _SAFE_BASES)


def _validate_import_path(path: str) -> str:
    """Resolve and validate an import path. Rejects paths outside safe directories."""
    resolved = os.path.realpath(os.path.expanduser(path))
    if not os.path.isdir(resolved):
        raise HTTPException(400, f"Import path is not a directory: {path}")
    if not _is_safe_path(resolved):
        raise HTTPException(403, "Import path is outside allowed directories")
    return resolved


def _read_steering_doc(path: str | None) -> str | None:
    """Read a markdown file from disk for the steering doc. Rejects paths outside safe directories."""
    if not path:
        return None
    resolved = os.path.realpath(os.path.expanduser(path))
    if not _is_safe_path(resolved):
        logger.warning(f"Steering doc path outside allowed directories: {resolved}")
        return None
    if not os.path.isfile(resolved):
        logger.warning(f"Steering doc path not found: {resolved}")
        return None
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Failed to read steering doc: {e}")
        return None


@router.post("/import")
async def import_markdown(planet_id: str, path: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    resolved = _validate_import_path(path)
    galaxy = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
    if not galaxy:
        raise HTTPException(400, "No galaxy exists. Run onboarding first.")
    planet = (await db.execute(select(Planet).where(Planet.id == planet_id))).scalar_one_or_none()
    if not planet:
        raise HTTPException(404, "Planet not found")
    from app.services import import_service
    background_tasks.add_task(import_service.import_markdown_folder, resolved, planet_id, galaxy.id)
    return {"status": "import_started", "planet_id": planet_id, "path": resolved}
