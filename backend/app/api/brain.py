"""Brain REST endpoints — expose brain.* operations as REST for the standalone MCP server."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.models import Galaxy
from app.models.user import User
from app.auth.dependencies import get_current_user, get_galaxy_for_user
from app.mcp import tools_brain, tools_memory

router = APIRouter(prefix="/api/v1/brain", tags=["brain"])


class OrientRequest(BaseModel):
    agent_name: str
    model: str
    agent_type: str = "GENERAL"
    active_planet: str | None = None
    active_biome: str | None = None
    max_tokens: int | None = None


class ThinkRequest(BaseModel):
    content: str
    planet: str
    biome: str | None = None
    cognitive_mode: str = "contextual"
    confidence: float = 0.7
    reasoning: str | None = None
    supersedes: list[str] | None = None
    scope: str = "BIOME"
    context_tags: list[str] | None = None
    session_id: str | None = None
    agent_name: str | None = None


class RecallRequest(BaseModel):
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


class CalibrateRequest(BaseModel):
    session_id: str
    records_used: list[str]
    records_retrieved_unused: list[str] | None = None
    knowledge_gaps: list[str] | None = None
    session_outcome: str | None = None
    knowledge_quality_score: float | None = None


class KnowRequest(BaseModel):
    concept: str
    depth: str = "summary"


class GraphQueryRequest(BaseModel):
    entity_name: str
    relationship_types: list[str] | None = None
    depth: int = 2


class FindPathRequest(BaseModel):
    source_concept: str
    target_concept: str


class ContextRequest(BaseModel):
    planet: str | None = None
    biome: str | None = None
    max_tokens: int = 4000
    model: str | None = None


class WriteRequest(BaseModel):
    content: str
    planet: str
    biome: str | None = None
    region: str = "contextual"
    context_tags: list[str] | None = None
    gravity: str = "BIOME"


class EntityGetRequest(BaseModel):
    entity_name: str
    planet: str | None = None


@router.post("/orient")
async def orient(body: OrientRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_brain.brain_orient(
        body.agent_name, body.model, body.agent_type,
        body.active_planet, body.active_biome, body.max_tokens,
        galaxy_id=galaxy.id,
    )


@router.post("/think")
async def think(body: ThinkRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_brain.brain_think(
        body.content, body.planet, body.biome, body.cognitive_mode,
        body.confidence, body.reasoning, body.supersedes, body.scope,
        body.context_tags, body.session_id, body.agent_name,
        galaxy_id=galaxy.id,
    )


@router.post("/recall")
async def recall(body: RecallRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_brain.brain_recall(
        body.query, body.cognitive_mode, body.planet, body.biome,
        body.context_window, body.include_reasoning, body.include_graph_paths,
        body.recency_weight, body.limit, body.session_id,
        galaxy_id=galaxy.id,
    )


@router.post("/calibrate")
async def calibrate(body: CalibrateRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_brain.brain_calibrate(
        body.session_id, body.records_used, body.records_retrieved_unused,
        body.knowledge_gaps, body.session_outcome, body.knowledge_quality_score,
        galaxy_id=galaxy.id,
    )


@router.get("/health/{agent_name}")
async def health(agent_name: str, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_brain.brain_health(agent_name, galaxy_id=galaxy.id)


@router.post("/know")
async def know(body: KnowRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_brain.brain_know(body.concept, body.depth, galaxy_id=galaxy.id)


@router.post("/graph-query")
async def graph_query(body: GraphQueryRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_brain.brain_graph_query(
        body.entity_name, body.relationship_types, body.depth,
        galaxy_id=galaxy.id,
    )


@router.post("/find-path")
async def find_path(body: FindPathRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    result = await tools_brain.brain_find_path(body.source_concept, body.target_concept, galaxy_id=galaxy.id)
    return result or {"path": None, "message": "No path found"}


@router.post("/context")
async def context(body: ContextRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_memory.memory_context(body.planet, body.biome, body.max_tokens, body.model, galaxy_id=galaxy.id)


@router.post("/write")
async def write(body: WriteRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_memory.memory_write(
        body.content, body.planet, body.biome, body.region, body.context_tags, body.gravity,
        galaxy_id=galaxy.id,
    )


@router.post("/entity-get")
async def entity_get(body: EntityGetRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_memory.memory_entity_get(body.entity_name, body.planet, galaxy_id=galaxy.id)


@router.get("/status")
async def status(user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_memory.memory_status(galaxy_id=galaxy.id)


@router.get("/planets")
async def planet_list(user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_memory.planet_list(galaxy_id=galaxy.id)


@router.get("/biomes")
async def biome_list(planet: str | None = None, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_memory.biome_list(planet=planet, galaxy_id=galaxy.id)


@router.get("/stardust/{stardust_id}")
async def stardust_get(stardust_id: str, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_memory.stardust_get(stardust_id, galaxy_id=galaxy.id)


@router.delete("/stardust/{stardust_id}")
async def stardust_delete(stardust_id: str, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user)):
    return await tools_memory.stardust_delete(stardust_id, galaxy_id=galaxy.id)
