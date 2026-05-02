from pydantic import BaseModel
from datetime import datetime


class GalaxyResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    owner_agent: str | None = None
    strength_score: float
    total_nodes: int
    schema_version: str
    planets: list["PlanetSummary"] = []


class PlanetSummary(BaseModel):
    id: str
    name: str
    stardust_count: int
    health_status: str
    active_biomes: list[str] = []


class GalaxyStrengthResponse(BaseModel):
    galaxy_id: str
    strength_score: float
    total_stardust: int
    total_entities: int


class SunSectionResponse(BaseModel):
    id: str
    section_key: str
    content: dict | str
    version: int
    updated_at: datetime


class SunSectionUpdate(BaseModel):
    content: str


class GalaxyStatusResponse(BaseModel):
    galaxy_id: str
    galaxy_name: str
    strength_score: float
    total_stardust: int
    total_entities: int
    planets: list[PlanetSummary]
    active_session_agents: int = 0
    last_audit_at: datetime | None = None
    contradiction_count_unresolved: int = 0
