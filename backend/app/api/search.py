from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy
from app.auth.dependencies import get_galaxy_for_user
from app.services import search_service
from app.schemas.stardust import SearchResponse

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    query: str,
    planet: str | None = None,
    biome: str | None = None,
    region: str | None = None,
    limit: int = Query(default=5, le=50),
    galaxy: Galaxy = Depends(get_galaxy_for_user),
    db: AsyncSession = Depends(get_db),
):
    return await search_service.search(
        query, galaxy.id, planet_name=planet, biome_name=biome, region=region, limit=limit,
    )
