from pydantic import BaseModel, Field
from datetime import datetime


class StardustCreate(BaseModel):
    content: str
    planet: str | None = None
    biome: str | None = None
    region: str = "contextual"
    context_tags: list[str] = []
    gravity: str = "BIOME"
    source_agent: str | None = None


class StardustResponse(BaseModel):
    id: str
    biome_id: str
    planet_id: str
    galaxy_id: str
    content: str
    region: str
    gravity: str
    confidence: float
    valid_from: datetime
    valid_until: datetime | None
    context_tags: list[str]
    contradiction_id: str | None
    reinforcement_sources: int
    source_agent: str | None
    chroma_id: str | None
    created_at: datetime
    last_accessed: datetime | None
    access_count: int
    reasoning: str | None = None
    supersedes: list[str] | None = None


class StardustUpdate(BaseModel):
    content: str | None = None
    context_tags: list[str] | None = None
    gravity: str | None = None
    valid_until: datetime | None = None


class ConflictInfo(BaseModel):
    conflict_id: str
    conflict_type: str
    existing_record_id: str
    recommended_action: str = "COEXIST"


class WriteReceipt(BaseModel):
    status: str
    stardust_id: str
    biome_id: str
    planet_id: str
    planet_name: str = ""
    biome_name: str = ""
    routing_method: str = ""
    routing_reasoning: str = ""
    layer: str = "cache"
    cache_ttl_seconds: int = 28800
    nebula_event_id: int | None = None
    contradiction_check: str = "clean"
    promotion_eligible: bool = False
    chroma_indexed: bool = False
    contradiction: ConflictInfo | None = None


class SearchRecord(BaseModel):
    id: str
    content: str
    region: str
    biome_name: str
    planet_name: str
    confidence: float
    valid_from: datetime
    valid_until: datetime | None
    context_tags: list[str]
    source_agent: str | None
    access_count: int


class RetrievalMetadata(BaseModel):
    sources_checked: list[str] = []
    cache_hits: int = 0
    total_records_considered: int = 0
    records_returned: int = 0
    confidence_range: list[float] = Field(default_factory=list, description="Empty or [min, max]", max_length=2)
    contradiction_flags: int = 0
    retrieval_latency_ms: int = 0
    token_estimate: int = 0


class SearchResponse(BaseModel):
    records: list[SearchRecord]
    retrieval_metadata: RetrievalMetadata


class ContextBundle(BaseModel):
    bundle_id: str
    generated_at: datetime
    sun_context: dict = {}
    planet_context: dict = {}
    biome_context: dict = {}
    retrieval_metadata: RetrievalMetadata = RetrievalMetadata()


class EntityResponse(BaseModel):
    id: str
    name: str
    entity_type: str
    tier: int
    profile: dict
    mention_count: int
    first_seen: datetime
    last_seen: datetime


class EntityProfileResponse(BaseModel):
    entity: EntityResponse
    related_stardust: list[SearchRecord] = []
    timeline: list[dict] = []
    relationship_types: list[str] = []


class PaginatedResponse(BaseModel):
    items: list = []
    total: int = 0
    offset: int = 0
    limit: int = 50
