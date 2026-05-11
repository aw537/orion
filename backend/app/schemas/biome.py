from pydantic import BaseModel, field_validator
from datetime import datetime

_TTL_MIN = 60
_TTL_MAX = 2_592_000  # 30 days


class BiomeCreate(BaseModel):
    name: str
    description: str | None = None
    cache_ttl_seconds: int | None = None

    @field_validator("cache_ttl_seconds")
    @classmethod
    def clamp_ttl(cls, v: int | None) -> int | None:
        if v is None:
            return v
        return max(_TTL_MIN, min(_TTL_MAX, v))


class BiomeResponse(BaseModel):
    id: str
    planet_id: str
    galaxy_id: str
    name: str
    description: str | None
    lifecycle_state: str
    created_at: datetime
    last_active_at: datetime | None
    stardust_count: int
    cache_ttl_seconds: int


class BiomeLifecycleUpdate(BaseModel):
    lifecycle_state: str


class BiomeGraphResponse(BaseModel):
    nodes: list["GraphNode"]
    edges: list["GraphEdge"]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # stardust | entity
    size: float = 1.0
    color: str | None = None
    metadata: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str  # entity_link | contradiction
