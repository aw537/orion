import json
import logging
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
import yaml

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy, Planet, Biome, Stardust, Entity
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.services import nebula_service, sun_service
from app.storage.chroma_client import ChromaClient, get_chroma_client

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

# --- Galaxy Templates ---

_TEMPLATES_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))).joinpath("content", "templates")


def _load_templates() -> list[dict]:
    """Load all YAML templates from content/templates/."""
    templates = []
    if not _TEMPLATES_DIR.is_dir():
        return templates
    for f in sorted(_TEMPLATES_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
            data["id"] = f.stem
            templates.append(data)
        except Exception as e:
            logger.warning(f"Failed to load template {f.name}: {e}")
    return templates


def _get_template(template_id: str) -> dict | None:
    path = _TEMPLATES_DIR / f"{template_id}.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text())
        data["id"] = path.stem
        return data
    except Exception:
        return None


@router.get("/templates")
async def list_templates():
    """Return available Galaxy templates for the onboarding wizard."""
    templates = _load_templates()
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t.get("description", ""),
            "icon": t.get("icon", ""),
            "planets": [
                {"name": p["name"], "color": p.get("color", "#6B7280"), "biomes": [b["name"] for b in p.get("biomes", [])]}
                for p in t.get("planets", [])
            ],
        }
        for t in templates
    ]


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
    template_id: str | None = None
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
    steering_doc_content: str | None = None


class OnboardingResponse(BaseModel):
    galaxy_id: str
    planets: list[str]
    first_biome_id: str
    import_started: bool = False
    stardust_count: int = 0
    entities_count: int = 0
    sun_configured: bool = False
    knowledge_gaps_count: int = 0


@router.post("/start", response_model=OnboardingResponse)
async def start_onboarding(body: OnboardingRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    existing = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
    if existing:
        # Galaxy already exists — trigger import if a path was provided, then return existing state
        import_started = False
        if body.import_path:
            resolved = None
            try:
                resolved = _validate_import_path(body.import_path)
            except Exception as e:
                logger.warning(f"Re-import path '{body.import_path}' not accessible: {e}")
                if body.source_type == "obsidian" and os.path.isdir("/vault"):
                    resolved = "/vault"
            if resolved:
                try:
                    first_planet = (await db.execute(
                        select(Planet).where(Planet.galaxy_id == existing.id).limit(1)
                    )).scalar_one_or_none()
                    if first_planet:
                        from app.services import import_service
                        background_tasks.add_task(
                            import_service.import_markdown_folder, resolved, first_planet.id, existing.id
                        )
                        import_started = True
                except Exception as e:
                    logger.error(f"Failed to schedule re-import task: {e}")
        planets = (await db.execute(select(Planet).where(Planet.galaxy_id == existing.id))).scalars().all()
        first_biome = (await db.execute(select(Biome).where(Biome.galaxy_id == existing.id).limit(1))).scalar_one_or_none()
        return OnboardingResponse(
            galaxy_id=existing.id,
            planets=[p.name for p in planets],
            first_biome_id=first_biome.id if first_biome else "",
            import_started=import_started,
        )

    galaxy_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create galaxy
    await db.execute(insert(Galaxy).values(id=galaxy_id, name=f"{body.role}'s Galaxy", created_at=now))

    # Load template if provided
    template = _get_template(body.template_id) if body.template_id else None

    # Create planets and biomes — from template or role defaults
    planet_ids = {}
    biome_id = None
    first_planet_id = None

    if template:
        planet_names = []
        for tp in template.get("planets", []):
            pid = str(uuid.uuid4())
            name = tp["name"]
            planet_names.append(name)
            planet_ids[name] = pid
            await db.execute(insert(Planet).values(id=pid, galaxy_id=galaxy_id, name=name, color=tp.get("color", PLANET_COLORS.get(name, "#6D28D9"))))
            for tb in tp.get("biomes", []):
                bid = str(uuid.uuid4())
                await db.execute(insert(Biome).values(id=bid, planet_id=pid, galaxy_id=galaxy_id, name=tb["name"], lifecycle_state="ACTIVE", created_at=now, last_active_at=now))
                if biome_id is None:
                    biome_id = bid
                    first_planet_id = pid
        if not planet_names:
            planet_names = ["General", "Personal"]
    else:
        planet_names = ROLE_PLANETS.get(body.role, ["General", "Personal"])
        for name in planet_names:
            pid = str(uuid.uuid4())
            planet_ids[name] = pid
            await db.execute(insert(Planet).values(id=pid, galaxy_id=galaxy_id, name=name, color=PLANET_COLORS.get(name, "#6D28D9")))
        first_planet_id = planet_ids[planet_names[0]]

    # Ensure at least one biome exists (from body.first_biome_name or template)
    if biome_id is None:
        if first_planet_id is None:
            first_planet_id = planet_ids[planet_names[0]]
        biome_id = str(uuid.uuid4())
        await db.execute(insert(Biome).values(id=biome_id, planet_id=first_planet_id, galaxy_id=galaxy_id, name=body.first_biome_name, lifecycle_state="ACTIVE", created_at=now, last_active_at=now))

    # Initialize Sun with template or role defaults + wizard answers
    if template and template.get("sun"):
        tsun = template["sun"]
        role_defaults = {"principles": tsun.get("principles", []), "write_rules": tsun.get("write_rules", [])}
    else:
        role_defaults = ROLE_SUN_DEFAULTS.get(body.role, ROLE_SUN_DEFAULTS.get("Developer", {}))

    wizard = {
        "name": body.name,
        "role": body.role,
        "communication_style": body.communication_style if body.communication_style != "direct" else (template.get("sun", {}).get("communication_style", "direct") if template else "direct"),
        "contradiction_preference": body.contradiction_preference,
        "principles": role_defaults.get("principles", []),
        "write_rules": role_defaults.get("write_rules", []),
        "session_start_instruction": "Call orion_context to load current project context.",
        "session_end_instruction": "Write any new decisions or learnings to the active Biome.",
        "current_focus": body.goal or body.first_biome_name,
    }
    _FALLBACK_STEERING = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "content", "STEERING.md")
    steering_content = body.steering_doc_content or _read_steering_doc(body.steering_doc_path) or _read_steering_doc(_FALLBACK_STEERING)
    await sun_service.initialize_sun(galaxy_id, wizard, db,
        steering_doc_content=steering_content,
        steering_doc_path=body.steering_doc_path or _FALLBACK_STEERING)

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

    # Template: seed stardust and entities from template definition
    if template:
        for tsd in template.get("seed_stardust", []):
            target_planet_id = planet_ids.get(tsd.get("planet"), "") or first_planet_id
            sd = Stardust(
                id=str(uuid.uuid4()), biome_id=biome_id, planet_id=target_planet_id, galaxy_id=galaxy_id,
                content=tsd["content"], region=tsd.get("region", "procedural"), gravity=tsd.get("gravity", "PLANET"),
                confidence=0.85, valid_from=now, source_agent="onboarding-template", created_at=now,
            )
            sd.context_tags = []
            db.add(sd)
            stardust_count += 1
        for tent in template.get("entities", []):
            db.add(Entity(id=str(uuid.uuid4()), galaxy_id=galaxy_id, planet_id=first_planet_id, name=tent["name"], entity_type=tent.get("type", "tool")))
            entities_count += 1

    await db.execute(update(Biome).where(Biome.id == biome_id).values(stardust_count=stardust_count))
    await db.execute(update(Planet).where(Planet.id == first_planet_id).values(stardust_count=stardust_count))

    await db.commit()

    # Ensure inbox planet and biome exist
    from app.api.inbox import get_or_create_inbox_planet
    await get_or_create_inbox_planet(galaxy_id, db)

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

# Safe base directories for import/steering doc reads.
# In Docker, set OBSIDIAN_VAULT_PATH so the vault is mounted at /vault.
# Do NOT mount $HOME into the container — use /vault for all vault access.
_SAFE_BASES = [
    os.path.expanduser("~"),  # user home (container user, not host)
    "/vault",                  # Docker-mounted vault (set OBSIDIAN_VAULT_PATH)
    "/tmp",                    # temp files
    "/app",                    # Docker working directory
]


def _is_safe_path(resolved: str) -> bool:
    """Check that resolved path is under an allowed base directory."""
    return any(resolved.startswith(os.path.realpath(b) + os.sep) or resolved == os.path.realpath(b) for b in _SAFE_BASES)


def _validate_import_path(path: str) -> str:
    """Resolve and validate an import path. Rejects paths outside safe directories."""
    resolved = os.path.realpath(os.path.expanduser(path))
    if not os.path.isdir(resolved):
        raise HTTPException(400, "Invalid import path")
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
async def import_markdown(planet_id: str, path: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
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


@router.post("/import-files")
async def import_uploaded_files(
    galaxy_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Accept markdown files uploaded directly from the browser (no filesystem path needed)."""
    galaxy = (await db.execute(select(Galaxy).where(Galaxy.id == galaxy_id))).scalar_one_or_none()
    if not galaxy:
        raise HTTPException(404, "Galaxy not found")

    planet = (await db.execute(
        select(Planet).where(Planet.galaxy_id == galaxy_id).limit(1)
    )).scalar_one_or_none()
    if not planet:
        raise HTTPException(404, "No planet found for galaxy")

    from app.services import stardust_service
    from app.services.import_service import parse_frontmatter, chunk_by_paragraph, _get_or_create_planet, _get_or_create_biome
    from app.extraction.signal_detector import infer_region_from_content

    def _clean(name: str) -> str:
        return name.replace("_", " ").replace("-", " ").title()

    imported = 0
    for upload in files:
        try:
            content = (await upload.read()).decode("utf-8", errors="ignore")
            if not content.strip():
                continue

            # webkitRelativePath sent as filename: e.g. "Vault/TopFolder/SubFolder/file.md"
            # parts[0] = vault root (skip), parts[1] = planet, parts[2] = biome
            relative_path = upload.filename or "unknown.md"
            parts = Path(relative_path).parts
            remaining = parts[1:]  # strip vault root

            if len(remaining) <= 1:
                cur_planet_id = planet.id
                cur_planet_name = planet.name
                biome_name = "General"
            elif len(remaining) == 2:
                cur_planet_name = _clean(remaining[0])
                cur_planet_id = await _get_or_create_planet(galaxy_id, cur_planet_name)
                biome_name = "General"
            else:
                cur_planet_name = _clean(remaining[0])
                cur_planet_id = await _get_or_create_planet(galaxy_id, cur_planet_name)
                biome_name = _clean(remaining[1])

            await _get_or_create_biome(cur_planet_id, galaxy_id, biome_name)

            frontmatter, body = parse_frontmatter(content)
            if not body.strip():
                continue

            region = infer_region_from_content(body)
            tags = frontmatter.get("tags", [])
            if isinstance(tags, str):
                tags = [tags] if tags else []

            chunks = chunk_by_paragraph(body)
            for chunk in chunks:
                if len(chunk.strip()) < 10:
                    continue
                await stardust_service.write_stardust(
                    content=chunk, galaxy_id=galaxy_id,
                    planet_name=cur_planet_name, biome_name=biome_name,
                    region=region, gravity="BIOME", confidence=0.5,
                    source_agent="importer", context_tags=tags,
                    filename=relative_path,
                )
                imported += 1
        except Exception as e:
            logger.warning(f"Failed to import uploaded file {upload.filename}: {e}")

    logger.info(f"Browser upload complete: {imported} stardust from {len(files)} files")
    return {"imported": imported, "file_count": len(files)}
