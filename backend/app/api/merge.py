"""Galaxy Merge REST endpoints (H2.8)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.services.merge_service import merge_service

router = APIRouter(prefix="/api/v1/galaxy/merge", tags=["galaxy-merge"])


class ProposeRequest(BaseModel):
    target_galaxy_id: str


class RejectRequest(BaseModel):
    reason: str = ""


@router.post("/propose")
async def propose_merge(
    body: ProposeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owner/admin can propose merges")
    if not user.galaxy_id:
        raise HTTPException(400, "User has no galaxy")
    proposal = await merge_service.propose_merge(
        user.galaxy_id, body.target_galaxy_id, user.id, db,
    )
    return {"proposal_id": proposal.id, "status": proposal.status}


@router.post("/{proposal_id}/accept")
async def accept_merge(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owner/admin can accept merges")
    proposal = await merge_service.accept_merge(proposal_id, user.id, db)
    return {"proposal_id": proposal.id, "status": proposal.status}


@router.post("/{proposal_id}/reject")
async def reject_merge(
    proposal_id: str,
    body: RejectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owner/admin can reject merges")
    proposal = await merge_service.reject_merge(proposal_id, user.id, body.reason, db)
    return {"proposal_id": proposal.id, "status": proposal.status}


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.merge import MergeProposal
    proposal = await db.get(MergeProposal, proposal_id)
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    return {
        "id": proposal.id,
        "source_galaxy_id": proposal.source_galaxy_id,
        "target_galaxy_id": proposal.target_galaxy_id,
        "status": proposal.status,
        "proposed_by": proposal.proposed_by,
        "accepted_by": proposal.accepted_by,
        "entity_mappings_count": proposal.entity_mappings_count,
        "bridges_created": proposal.bridges_created,
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
        "completed_at": proposal.completed_at.isoformat() if proposal.completed_at else None,
        "rejection_reason": proposal.rejection_reason,
    }


@router.get("/{proposal_id}/sun-preview")
async def sun_preview(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await merge_service.preview_merged_sun(proposal_id, db)


@router.get("/{proposal_id}/entity-mappings")
async def entity_mappings(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await merge_service.get_entity_mappings(proposal_id, db)


@router.post("/{proposal_id}/execute")
async def execute_merge(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owner/admin can execute merges")
    result = await merge_service.execute_merge(proposal_id, db)
    return result
