"""Contradiction resolution REST endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy
from app.auth.dependencies import get_galaxy_for_user

router = APIRouter(prefix="/api/v1/contradictions", tags=["contradictions"])


from typing import Literal

class ResolveRequest(BaseModel):
    resolution_type: Literal["a_supersedes_b", "b_supersedes_a", "coexist", "synthesize"]
    synthesis_content: str | None = None


@router.get("")
async def list_contradictions(
    status: str = "UNRESOLVED", limit: int = 20,
    galaxy: Galaxy = Depends(get_galaxy_for_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.contradiction_service import contradiction_service
    items = await contradiction_service.list_contradictions(galaxy.id, status, limit, db)
    return {"contradictions": items}


@router.get("/{contradiction_id}")
async def get_contradiction(
    contradiction_id: str,
    galaxy: Galaxy = Depends(get_galaxy_for_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.contradiction import Contradiction
    c = await db.get(Contradiction, contradiction_id)
    if not c or c.galaxy_id != galaxy.id:
        raise HTTPException(404, "Contradiction not found")
    return {
        "id": c.id, "record_a_id": c.record_a_id, "record_b_id": c.record_b_id,
        "conflict_type": c.conflict_type, "status": c.status, "region": c.region,
        "detected_at": c.detected_at.isoformat() if c.detected_at else None,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        "resolved_by": c.resolved_by, "resolution_note": c.resolution_note,
    }


@router.post("/{contradiction_id}/resolve")
async def resolve_contradiction(
    contradiction_id: str, body: ResolveRequest,
    galaxy: Galaxy = Depends(get_galaxy_for_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.contradiction_service import contradiction_service
    try:
        result = await contradiction_service.resolve_contradiction(
            contradiction_id=contradiction_id,
            resolution_type=body.resolution_type,
            synthesis_content=body.synthesis_content,
            galaxy_id=galaxy.id, resolved_by="user", db=db,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "contradiction_id": result.contradiction_id,
        "status": result.status,
        "new_stardust_id": result.new_stardust_id,
    }
