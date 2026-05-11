import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy
from app.models.profiles import ModelProfile
from app.auth.dependencies import get_galaxy_for_user

router = APIRouter(prefix="/api/v1/model-profiles", tags=["model-profiles"])


class ModelProfileResponse(BaseModel):
    id: str
    model_id: str
    display_name: str
    context_window_tokens: int
    optimal_context_tokens: int
    format_preference: str
    tool_calling: str
    is_builtin: bool
    created_at: str


class ModelProfileCreate(BaseModel):
    model_id: str
    display_name: str
    context_window_tokens: int
    optimal_context_tokens: int
    format_preference: str = "structured_json"
    tool_calling: str = "native"


class ModelProfileUpdate(BaseModel):
    display_name: str | None = None
    optimal_context_tokens: int | None = None
    format_preference: str | None = None
    tool_calling: str | None = None


@router.get("")
async def list_profiles(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ModelProfile))).scalars().all()
    return [_to_dict(p) for p in rows]


@router.get("/{model_id}")
async def get_profile(model_id: str, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(ModelProfile).where(ModelProfile.model_id == model_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Model profile not found")
    return _to_dict(p)


@router.post("", status_code=201)
async def create_profile(body: ModelProfileCreate, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(ModelProfile).where(ModelProfile.model_id == body.model_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"Profile for '{body.model_id}' already exists")
    p = ModelProfile(id=f"profile_{uuid.uuid4().hex[:8]}", is_builtin=False, **body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _to_dict(p)


@router.put("/{model_id}")
async def update_profile(model_id: str, body: ModelProfileUpdate, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(ModelProfile).where(ModelProfile.model_id == model_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Model profile not found")
    if p.is_builtin:
        raise HTTPException(400, "Cannot modify built-in profiles")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nothing to update")
    for k, v in updates.items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return _to_dict(p)


def _to_dict(p: ModelProfile) -> dict:
    return {
        "id": p.id, "model_id": p.model_id, "display_name": p.display_name,
        "context_window_tokens": p.context_window_tokens, "optimal_context_tokens": p.optimal_context_tokens,
        "format_preference": p.format_preference, "tool_calling": p.tool_calling,
        "is_builtin": p.is_builtin, "created_at": p.created_at.isoformat() if p.created_at else "",
    }
