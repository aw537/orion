"""brain.ask REST endpoint — natural language knowledge graph queries."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy
from app.auth.dependencies import get_galaxy_for_user
from app.services import brain_ask_service

router = APIRouter(prefix="/api/v1", tags=["ask"])


class AskRequest(BaseModel):
    question: str
    planet: str | None = None
    depth: int = 2


@router.post("/ask")
async def ask(body: AskRequest, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    result = await brain_ask_service.answer(
        question=body.question,
        galaxy_id=galaxy.id,
        planet_name=body.planet,
        depth=body.depth,
        db=db,
    )
    return result.model_dump()
