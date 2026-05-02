"""brain.ask — Natural language knowledge graph queries.

Routes natural language questions to the appropriate graph/search/synthesis
operation using keyword matching (zero LLM calls).
"""
import re
import logging
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.brain import AgentExpertise, AgentIdentity
from app.services.graph_service import graph_service
from app.services.search_service import search as search_records
from app.services.synthesis_service import SynthesisService

logger = logging.getLogger(__name__)


class AskAnswer(BaseModel):
    question: str
    intent: str
    answer: str
    supporting_records: list[dict] = []
    graph_data: dict | None = None
    confidence: float = 0.0


# ── Intent Router ───────────────────────────────────────────────────────────

_EXPERTISE_PATTERNS = [
    re.compile(r"who (?:knows?|worked?|owns?|understands?|wrote?|built?)\s+(?:about\s+)?(?:the\s+|a\s+|an\s+|our\s+)?(.+?)(?:\?|$)", re.I),
    re.compile(r"who (?:is|was) (?:responsible|working) (?:for|on) (.+?)(?:\?|$)", re.I),
]

_DECISION_PATTERNS = [
    re.compile(r"what decisions? (?:were|was) made (?:about|for|on) (.+?)(?:\?|$)", re.I),
    re.compile(r"why (?:did we|was|were) (.+?)(?:chosen|selected|decided|picked)", re.I),
    re.compile(r"how was (.+?) decided(?:\?|$)", re.I),
]

_CONNECTION_PATTERNS = [
    re.compile(r"how does (.+?) (?:relate|connect) to (.+?)(?:\?|$)", re.I),
    re.compile(r"what connects (.+?) (?:to|with) (.+?)(?:\?|$)", re.I),
    re.compile(r"(?:show|find) (?:me )?(?:the )?(?:path|connection|link) (?:between|from) (.+?) (?:to|and) (.+?)(?:\?|$)", re.I),
]

_NEIGHBORHOOD_PATTERNS = [
    re.compile(r"(?:everything|all) (?:about|connected to|related to) (.+?)(?:\?|$)", re.I),
    re.compile(r"what (?:do we|does the team) know (?:about) (.+?)(?:\?|$)", re.I),
    re.compile(r"show (?:me )?(?:everything about|all knowledge about) (.+?)(?:\?|$)", re.I),
]

_SYNTHESIS_PATTERNS = [
    re.compile(r"(?:summarize|overview of|summary of) (.+?)(?:\?|$)", re.I),
    re.compile(r"what is (?:the )?(?:current )?state of (.+?)(?:\?|$)", re.I),
    re.compile(r"brief me on (.+?)(?:\?|$)", re.I),
]

_ALL_INTENTS = [
    ("expertise", _EXPERTISE_PATTERNS),
    ("decision", _DECISION_PATTERNS),
    ("connection", _CONNECTION_PATTERNS),
    ("neighborhood", _NEIGHBORHOOD_PATTERNS),
    ("synthesis", _SYNTHESIS_PATTERNS),
]


def route_question(question: str) -> tuple[str, list[str]]:
    """Return (intent, extracted_entities). Falls back to synthesis."""
    q = question.strip()
    for intent, patterns in _ALL_INTENTS:
        for pattern in patterns:
            m = pattern.search(q)
            if m:
                return intent, [g.strip() for g in m.groups() if g]
    return "synthesis", [question]


# ── Answer Service ──────────────────────────────────────────────────────────

async def _find_entity_by_name(name: str, galaxy_id: str, db: AsyncSession) -> Entity | None:
    """Fuzzy entity lookup — exact match first, then case-insensitive contains."""
    e = (await db.execute(
        select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.name == name)
    )).scalar_one_or_none()
    if e:
        return e
    return (await db.execute(
        select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.name.ilike(f"%{name}%"))
        .order_by(Entity.mention_count.desc()).limit(1)
    )).scalar_one_or_none()


async def answer(
    question: str,
    galaxy_id: str,
    planet_name: str | None,
    depth: int,
    db: AsyncSession,
) -> AskAnswer:
    intent, entities = route_question(question)
    topic = entities[0] if entities else question

    if intent == "expertise":
        return await _handle_expertise(question, topic, galaxy_id, db)
    elif intent == "decision":
        return await _handle_decision(question, topic, galaxy_id, planet_name, db)
    elif intent == "connection":
        if len(entities) >= 2:
            result = await _handle_connection(question, entities[0], entities[1], galaxy_id, db)
            if result:
                return result
        # Fall through to synthesis if entities not found
        intent = "synthesis"
    elif intent == "neighborhood":
        return await _handle_neighborhood(question, topic, galaxy_id, depth, db)

    # synthesis (default)
    return await _handle_synthesis(question, topic, galaxy_id, planet_name, db)


async def _handle_expertise(q: str, topic: str, galaxy_id: str, db: AsyncSession) -> AskAnswer:
    """Who knows about X? → Find agents with expertise on the topic."""
    # Search agent_expertise for matching domains
    experts = (await db.execute(
        select(AgentExpertise, AgentIdentity)
        .join(AgentIdentity, AgentExpertise.agent_identity_id == AgentIdentity.id)
        .where(AgentIdentity.galaxy_id == galaxy_id, AgentExpertise.domain.ilike(f"%{topic}%"))
        .order_by(AgentExpertise.expertise_level.desc())
        .limit(5)
    )).all()

    if experts:
        lines = [f"Agents with expertise on '{topic}':"]
        for exp, agent in experts:
            lines.append(f"  • {agent.agent_name} — level {exp.expertise_level:.1f}, {exp.evidence_count} evidence records")
        answer_text = "\n".join(lines)
    else:
        # Fall back to entity search
        entity = await _find_entity_by_name(topic, galaxy_id, db)
        if entity:
            hubs = await graph_service.get_hub_entities(galaxy_id, limit=5, db=db)
            answer_text = f"No agent expertise found for '{topic}', but entity '{entity.name}' ({entity.entity_type}) exists with {entity.mention_count} mentions."
        else:
            answer_text = f"No expertise or entities found for '{topic}'."

    return AskAnswer(question=q, intent="expertise", answer=answer_text)


async def _handle_decision(q: str, topic: str, galaxy_id: str, planet_name: str | None, db: AsyncSession) -> AskAnswer:
    """What decisions were made about X? → Search analytical region for decision records."""
    results = await search_records(
        query=topic, galaxy_id=galaxy_id, planet_name=planet_name,
        region="analytical", limit=10,
    )
    decision_words = {"decided", "chose", "selected", "rejected", "adopted", "switched", "migrated", "decision", "trade-off", "tradeoff"}
    decision_records = [
        r for r in results.records
        if any(w in r.content.lower() for w in decision_words)
    ]
    if not decision_records:
        decision_records = results.records[:5]

    if decision_records:
        lines = [f"Decisions related to '{topic}':"]
        for r in decision_records:
            snippet = r.content[:150].replace("\n", " ")
            lines.append(f"  • [{r.region}] {snippet}...")
        answer_text = "\n".join(lines)
    else:
        answer_text = f"No decision records found for '{topic}'."

    return AskAnswer(
        question=q, intent="decision", answer=answer_text,
        supporting_records=[r.model_dump() for r in decision_records],
    )


async def _handle_connection(q: str, source_name: str, target_name: str, galaxy_id: str, db: AsyncSession) -> AskAnswer | None:
    """How does X relate to Y? → Find graph path between entities."""
    source = await _find_entity_by_name(source_name, galaxy_id, db)
    target = await _find_entity_by_name(target_name, galaxy_id, db)
    if not source or not target:
        return None  # Fall through to synthesis

    path = await graph_service.find_path(source.id, target.id, galaxy_id, db)
    if path:
        # Resolve node names
        node_names = []
        for nid in path["nodes"]:
            e = await db.get(Entity, nid)
            node_names.append(e.name if e else nid)
        steps = []
        for i, rel in enumerate(path["relationship_types"]):
            steps.append(f"{node_names[i]} —[{rel}]→ {node_names[i+1]}")
        answer_text = f"Connection between '{source_name}' and '{target_name}' ({path['length']} hops):\n  " + "\n  ".join(steps)
    else:
        answer_text = f"No direct connection found between '{source_name}' and '{target_name}' in the knowledge graph."

    return AskAnswer(question=q, intent="connection", answer=answer_text, graph_data=path)


async def _handle_neighborhood(q: str, topic: str, galaxy_id: str, depth: int, db: AsyncSession) -> AskAnswer:
    """Everything about X → Entity neighborhood + search results."""
    entity = await _find_entity_by_name(topic, galaxy_id, db)
    parts = []

    if entity:
        neighborhood = await graph_service.get_entity_neighborhood(entity.id, depth, galaxy_id, db)
        n_entities = len(neighborhood.get("entities", []))
        n_edges = len(neighborhood.get("edges", []))
        parts.append(f"Entity '{entity.name}' ({entity.entity_type}, tier {entity.tier}): {n_entities} connected entities, {n_edges} relationships.")
        graph_data = neighborhood
    else:
        graph_data = None

    results = await search_records(query=topic, galaxy_id=galaxy_id, limit=5)
    if results.records:
        parts.append(f"\n{len(results.records)} related records:")
        for r in results.records:
            snippet = r.content[:120].replace("\n", " ")
            parts.append(f"  • [{r.planet_name}/{r.biome_name}] {snippet}...")

    answer_text = "\n".join(parts) if parts else f"No knowledge found about '{topic}'."
    return AskAnswer(
        question=q, intent="neighborhood", answer=answer_text,
        supporting_records=[r.model_dump() for r in results.records],
        graph_data=graph_data,
    )


async def _handle_synthesis(q: str, topic: str, galaxy_id: str, planet_name: str | None, db: AsyncSession) -> AskAnswer:
    """Summarize / overview → Run synthesis service."""
    from app.storage.redis_client import get_redis
    synthesis_service = SynthesisService()
    redis = await get_redis()
    result = await synthesis_service.synthesize(
        topic=topic, galaxy_id=galaxy_id,
        planet_id=None, biome_id=None,
        include_open_questions=True, include_contradictions=True,
        max_tokens=1000, db=db, redis=redis,
    )
    return AskAnswer(
        question=q, intent="synthesis", answer=result.current_understanding,
        confidence=result.confidence,
        supporting_records=[],
    )
