import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy, Planet, Biome
from app.models.user import User
from app.auth.dependencies import get_current_user, get_galaxy_for_user
from app.auth.permissions import permission_checker
from app.schemas.planet import PlanetCreate, PlanetResponse, PlanetDetailResponse, BiomeSummary

router = APIRouter(prefix="/api/v1/planets", tags=["planets"])


@router.get("", response_model=list[PlanetResponse])
async def list_planets(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id))).scalars().all()
    return [PlanetResponse(id=p.id, galaxy_id=p.galaxy_id, name=p.name, description=p.description, color=p.color, planet_type=p.planet_type, created_at=p.created_at, stardust_count=p.stardust_count, health_status=p.health_status) for p in planets]


@router.get("/{planet_id}", response_model=PlanetDetailResponse)
async def get_planet(planet_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    planet = (await db.execute(select(Planet).where(Planet.id == planet_id))).scalar_one_or_none()
    if not planet:
        raise HTTPException(404, "Planet not found")
    await permission_checker.require_planet_access(user, planet_id, "read", db)
    biomes = (await db.execute(select(Biome).where(Biome.planet_id == planet_id))).scalars().all()
    return PlanetDetailResponse(
        id=planet.id, galaxy_id=planet.galaxy_id, name=planet.name, description=planet.description,
        color=planet.color, planet_type=planet.planet_type, created_at=planet.created_at, stardust_count=planet.stardust_count,
        health_status=planet.health_status,
        biomes=[BiomeSummary(id=b.id, name=b.name, lifecycle_state=b.lifecycle_state, stardust_count=b.stardust_count) for b in biomes],
    )


@router.post("", response_model=PlanetResponse, status_code=201)
async def create_planet(body: PlanetCreate, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    planet_id = str(uuid.uuid4())
    await db.execute(insert(Planet).values(id=planet_id, galaxy_id=galaxy.id, name=body.name, description=body.description, color=body.color))
    await db.commit()
    from app.services import sun_service
    await sun_service.update_planet_registry(galaxy.id)
    planet = (await db.execute(select(Planet).where(Planet.id == planet_id))).scalar_one()
    return PlanetResponse(id=planet.id, galaxy_id=planet.galaxy_id, name=planet.name, description=planet.description, color=planet.color, planet_type=planet.planet_type, created_at=planet.created_at, stardust_count=planet.stardust_count, health_status=planet.health_status)
