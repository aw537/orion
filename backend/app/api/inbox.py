import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, insert, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy, Planet, Biome
from app.models.inbox import InboxIngestion
from app.auth.dependencies import get_current_user, get_galaxy_for_user
from app.models.user import User
from app.schemas.inbox import InboxUploadResponse, InboxRoutingResult, InboxHistoryResponse, InboxHistoryItem

router = APIRouter(prefix="/api/v1/inbox", tags=["inbox"])

ALLOWED_EXTENSIONS = {".md", ".txt", ".yaml", ".yml", ".json"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def get_or_create_inbox_planet(galaxy_id: str, db: AsyncSession) -> Planet:
    """Lazily get or create the Inbox Planet for a Galaxy."""
    planet = (await db.execute(
        select(Planet).where(Planet.galaxy_id == galaxy_id, Planet.planet_type == "inbox")
    )).scalar_one_or_none()
    if planet:
        return planet

    planet_id = str(uuid.uuid4())
    await db.execute(insert(Planet).values(
        id=planet_id,
        galaxy_id=galaxy_id,
        name="Inbox",
        description="Drop zone — files uploaded here are parsed and routed to other Planets.",
        color="#F59E0B",
        planet_type="inbox",
    ))
    await db.commit()
    return (await db.execute(select(Planet).where(Planet.id == planet_id))).scalar_one()


@router.post("/upload", response_model=InboxUploadResponse)
async def upload_to_inbox(
    file: UploadFile = File(...),
    galaxy: Galaxy = Depends(get_galaxy_for_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate extension
    filename = file.filename or "untitled"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Ensure inbox planet exists
    await get_or_create_inbox_planet(galaxy.id, db)

    # Parse file into chunks
    from app.services.inbox_service import parse_file
    chunks = parse_file(filename, content)

    ingestion_id = str(uuid.uuid4())

    if not chunks:
        await db.execute(insert(InboxIngestion).values(
            id=ingestion_id, galaxy_id=galaxy.id, filename=filename,
            status="complete", chunks_total=0, chunks_routed=0, results_json="[]",
        ))
        await db.commit()
        return InboxUploadResponse(
            ingestion_id=ingestion_id, filename=filename,
            status="complete", chunks_total=0, chunks_routed=0, results=[],
        )

    # Route each chunk via stardust_service
    from app.services import stardust_service
    results: list[InboxRoutingResult] = []
    for chunk in chunks:
        receipt = await stardust_service.write_stardust(
            content=chunk.content,
            galaxy_id=galaxy.id,
            context_tags=chunk.context_tags,
            source_agent="inbox",
            filename=filename,
        )
        planet = (await db.execute(select(Planet).where(Planet.id == receipt.planet_id))).scalar_one_or_none()
        biome = (await db.execute(select(Biome).where(Biome.id == receipt.biome_id))).scalar_one_or_none()
        results.append(InboxRoutingResult(
            chunk_preview=chunk.content[:80],
            target_planet_id=receipt.planet_id,
            target_planet_name=planet.name if planet else "Unknown",
            target_biome_id=receipt.biome_id,
            target_biome_name=biome.name if biome else None,
            confidence=0.7,
            method="planet_assignment_engine",
        ))

    # Persist ingestion record
    await db.execute(insert(InboxIngestion).values(
        id=ingestion_id, galaxy_id=galaxy.id, filename=filename,
        status="complete", chunks_total=len(chunks), chunks_routed=len(results),
        results_json=json.dumps([r.model_dump() for r in results]),
    ))
    await db.commit()

    return InboxUploadResponse(
        ingestion_id=ingestion_id, filename=filename,
        status="complete", chunks_total=len(chunks), chunks_routed=len(results),
        results=results,
    )


@router.get("/history", response_model=InboxHistoryResponse)
async def inbox_history(
    galaxy: Galaxy = Depends(get_galaxy_for_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(InboxIngestion)
        .where(InboxIngestion.galaxy_id == galaxy.id)
        .order_by(desc(InboxIngestion.created_at))
        .limit(50)
    )).scalars().all()

    items = [
        InboxHistoryItem(
            ingestion_id=r.id, filename=r.filename, status=r.status,
            chunks_total=r.chunks_total, chunks_routed=r.chunks_routed,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return InboxHistoryResponse(items=items, total=len(items))
