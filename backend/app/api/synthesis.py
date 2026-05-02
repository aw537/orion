"""Synthesis REST endpoint."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy
from app.auth.dependencies import get_galaxy_for_user
from app.storage.redis_client import get_redis

router = APIRouter(prefix="/api/v1", tags=["synthesis"])


class SynthesizeRequest(BaseModel):
    topic: str
    planet: str | None = None
    biome: str | None = None
    include_open_questions: bool = True
    include_contradictions: bool = True


@router.post("/synthesize")
async def synthesize(body: SynthesizeRequest, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    from app.services.synthesis_service import synthesis_service
    redis = await get_redis()
    result = await synthesis_service.synthesize(
        topic=body.topic, galaxy_id=galaxy.id,
        planet_id=None, biome_id=None,
        include_open_questions=body.include_open_questions,
        include_contradictions=body.include_contradictions,
        max_tokens=1000, db=db, redis=redis,
    )
    return result.model_dump()


@router.delete("/synthesize/cache")
async def invalidate_synthesis_cache(galaxy: Galaxy = Depends(get_galaxy_for_user)):
    redis = await get_redis()
    keys = await redis.keys(f"orion:{galaxy.id}:synthesis:*")
    if keys:
        await redis.delete(*keys)
    return {"status": "cleared", "keys_removed": len(keys)}
