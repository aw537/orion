"""Pydantic schemas for brain, agent, and graph endpoints."""
from datetime import datetime
from pydantic import BaseModel


# ── Agent Identity ──────────────────────────────────────────────────────────

class AgentOrientRequest(BaseModel):
    agent_name: str
    model: str
    agent_type: str = "GENERAL"
    active_planet: str | None = None
    active_biome: str | None = None
    max_tokens: int | None = None


class AgentExpertiseResponse(BaseModel):
    domain: str
    level: float
    evidence_count: int
    last_demonstrated: str | None = None


class AgentIdentityResponse(BaseModel):
    id: str
    agent_name: str
    agent_type: str
    current_model: str | None
    model_family: str | None
    total_sessions: int
    total_reads: int
    total_writes: int
    retrieval_quality_score: float
    calibration_score: float = 0.0
    contradiction_rate: float = 0.0
    last_active: datetime | None = None
    birth_date: datetime | None = None


class AgentSessionResponse(BaseModel):
    id: str
    model_used: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    reads: int
    writes: int
    session_quality_score: float | None = None
    model_switch_from: str | None = None


# ── Brain Tools ─────────────────────────────────────────────────────────────

class BrainThinkRequest(BaseModel):
    content: str
    planet: str
    biome: str | None = None
    # NOTE: "cognitive_mode" is the user-facing name; maps to "region" in the Stardust model.
    # See STYLE-002 in BUGS.md for context on this naming inconsistency.
    cognitive_mode: str = "contextual"
    confidence: float = 0.7
    reasoning: str | None = None
    supersedes: list[str] | None = None
    scope: str = "BIOME"
    context_tags: list[str] | None = None
    session_id: str | None = None


class BrainThinkReceipt(BaseModel):
    status: str
    stardust_id: str
    biome_id: str
    planet_id: str
    cognitive_mode: str
    reasoning_stored: bool = False
    supersedes_count: int = 0


class BrainRecallRequest(BaseModel):
    query: str
    cognitive_mode: str | None = None
    planet: str | None = None
    biome: str | None = None
    context_window: str | None = None
    include_reasoning: bool = False
    include_graph_paths: bool = False
    recency_weight: float = 0.3
    limit: int = 5
    session_id: str | None = None


class BrainCalibrateRequest(BaseModel):
    session_id: str
    records_used: list[str]
    records_retrieved_unused: list[str] | None = None
    knowledge_gaps: list[str] | None = None
    session_outcome: str | None = None
    knowledge_quality_score: float | None = None


class CalibrationReceipt(BaseModel):
    calibration_id: str
    records_boosted: int
    records_decayed: int
    gaps_logged: int


class BrainHealthResponse(BaseModel):
    overall_health: float
    knowledge_freshness: float
    total_knowledge_items: int
    coverage_gaps: list[str] = []
    stale_beliefs: list[dict] = []
    expertise_summary: list[AgentExpertiseResponse] = []
    recommended_enrichment: list[str] = []
    agent_sessions: int
    current_model: str | None
    brain_age_days: int


# ── Model Switch ────────────────────────────────────────────────────────────

class ModelSwitchResponse(BaseModel):
    id: str
    agent_identity_id: str
    previous_model: str
    new_model: str
    switched_at: datetime | None = None
    continuity_score: float | None
    reason: str | None


class ModelSwitchLatest(BaseModel):
    agent_name: str
    previous_model: str
    new_model: str
    switched_at: datetime | None = None
    continuity_score: float | None


# ── Knowledge Graph ─────────────────────────────────────────────────────────

class GraphEntityResponse(BaseModel):
    id: str
    name: str
    type: str
    tier: int
    mentions: int


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    type: str
    confidence: float


class GraphNeighborhoodResponse(BaseModel):
    center_entity_id: str
    entities: list[GraphEntityResponse] = []
    edges: list[GraphEdgeResponse] = []
    depth: int


class GraphPathResponse(BaseModel):
    nodes: list[str]
    relationship_types: list[str]
    length: int


class HubEntityResponse(BaseModel):
    id: str
    name: str
    entity_type: str
    tier: int
    degree: int


class UnlinkedMentionResponse(BaseModel):
    entity_id: str
    entity_name: str
    unlinked_count: int
    stardust_ids: list[str] = []
    sample: str = ""


class LinkRequest(BaseModel):
    entity_id: str
    stardust_id: str


class LinkAllResponse(BaseModel):
    entity_id: str
    links_created: int


# ── Orientation ─────────────────────────────────────────────────────────────

class ModelCalibration(BaseModel):
    model: str | None
    token_budget: int
    format_preference: str
    tool_calling: str


class OrientationResponse(BaseModel):
    orientation_id: str
    session_id: str
    agent_identity: dict
    galaxy_identity: dict
    current_context: dict
    knowledge_state: dict
    operating_protocol: dict
    model_calibration: ModelCalibration
    transition_brief: dict | None = None
