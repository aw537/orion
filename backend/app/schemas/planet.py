from pydantic import BaseModel
from datetime import datetime


class PlanetCreate(BaseModel):
    name: str
    description: str | None = None
    color: str = "#6D28D9"


class PlanetResponse(BaseModel):
    id: str
    galaxy_id: str
    name: str
    description: str | None
    color: str
    planet_type: str = "standard"
    created_at: datetime
    stardust_count: int
    health_status: str


class PlanetDetailResponse(PlanetResponse):
    biomes: list["BiomeSummary"] = []


class BiomeSummary(BaseModel):
    id: str
    name: str
    lifecycle_state: str
    stardust_count: int
