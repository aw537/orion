from pydantic import BaseModel
from datetime import datetime


class NebulaEvent(BaseModel):
    event_id: int
    action_type: str
    planet_id: str | None = None
    biome_id: str | None = None
    record_id: str | None = None
    initiated_by: str
    timestamp: datetime
    metadata: dict = {}


class NebulaLogResponse(BaseModel):
    events: list[NebulaEvent]
    total: int = 0
    offset: int = 0
    limit: int = 50


class NebulaDashboardResponse(BaseModel):
    total_events: int = 0
    events_by_type: dict[str, int] = {}
    events_last_24h: int = 0
    top_agents: list[dict] = []
    top_biomes: list[dict] = []


class OnboardingRequest(BaseModel):
    role: str
    import_path: str | None = None
    first_biome_name: str = "General"


class OnboardingResponse(BaseModel):
    galaxy_id: str
    planets: list[str]
    first_biome_id: str
    import_started: bool = False


class AuditStatusResponse(BaseModel):
    id: str
    galaxy_id: str
    run_at: datetime
    run_by: str
    records_reviewed: int
    duplicates_merged: int
    contradictions_found: int
    contradictions_classified: int
    promotions_made: int
    confidence_decays: int
    duration_ms: int | None
    summary: str | None
