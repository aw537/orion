import json
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, desc
from app.database import async_session
from app.models import SunSection, Planet, Biome, Stardust, Entity
from app.storage.redis_client import RedisClient, get_redis
from app.schemas.stardust import ContextBundle, RetrievalMetadata

logger = logging.getLogger(__name__)

# Rough token estimate: ~4 chars per token
CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _stardust_to_dict(s) -> dict:
    tags = json.loads(s.context_tags) if isinstance(s.context_tags, str) else s.context_tags
    return {"id": s.id, "content": s.content, "region": s.region, "confidence": s.confidence, "gravity": s.gravity, "context_tags": tags, "source_agent": s.source_agent, "created_at": s.created_at.isoformat() if s.created_at else None}


async def build_context(
    galaxy_id: str,
    planet_name: str | None = None,
    biome_name: str | None = None,
    max_tokens: int = 4000,
) -> ContextBundle:
    budget = max_tokens
    used = 0
    cache_hits = 0
    total_considered = 0

    sun_context = {}
    planet_context = {}
    biome_context = {}

    async with async_session() as db:
        # --- Sun context (always included, highest priority) ---
        sections = (await db.execute(select(SunSection).where(SunSection.galaxy_id == galaxy_id))).scalars().all()
        sun_data = {}
        for s in sections:
            sun_data[s.section_key] = s.content if isinstance(s.content, dict) else (json.loads(s.content) if s.content else {})
        sun_context = {
            "core_values": sun_data.get("values", []),
            "agent_protocol": sun_data.get("agent_protocol", []),
            "active_planets": sun_data.get("planet_registry", []),
        }
        used += _estimate_tokens(json.dumps(sun_context))

        # Resolve planet
        planet = None
        if planet_name:
            planet = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy_id, Planet.name == planet_name))).scalar_one_or_none()
        if not planet:
            planet = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy_id).limit(1))).scalar_one_or_none()
        if not planet:
            return ContextBundle(bundle_id=str(uuid.uuid4()), generated_at=datetime.now(timezone.utc).replace(tzinfo=None), sun_context=sun_context, retrieval_metadata=RetrievalMetadata(token_estimate=used))

        # Resolve biome
        biome = None
        if biome_name:
            biome = (await db.execute(select(Biome).where(Biome.planet_id == planet.id, Biome.name == biome_name))).scalar_one_or_none()
        if not biome:
            biome = (await db.execute(select(Biome).where(Biome.planet_id == planet.id).order_by(Biome.last_active_at.desc().nullslast()).limit(1))).scalar_one_or_none()

        active_biomes = (await db.execute(select(Biome.name).where(Biome.planet_id == planet.id, Biome.lifecycle_state.in_(["SEED", "ACTIVE", "MATURE"])))).scalars().all()

        # --- Priority stack (spec section 10, orion_context) ---
        stardust_items = []

        # 1. Active cache (Redis)
        try:
            redis = await get_redis()
            rc = RedisClient(redis)
            if biome:
                cached_ids = await rc.get_recent_stardust(galaxy_id, biome.id, limit=20)
                cache_hits = len(cached_ids)
                total_considered += cache_hits
                if cached_ids:
                    rows = (await db.execute(select(Stardust).where(Stardust.id.in_(cached_ids), Stardust.valid_until.is_(None)))).scalars().all()
                    for s in rows:
                        if used + _estimate_tokens(s.content) > budget:
                            break
                        stardust_items.append(_stardust_to_dict(s))
                        used += _estimate_tokens(s.content)
        except Exception as e:
            logger.warning(f"Redis context fetch failed: {e}")

        # 2. High-confidence permanent (confidence >= 0.7)
        high_conf = (await db.execute(
            select(Stardust).where(Stardust.planet_id == planet.id, Stardust.confidence >= 0.7, Stardust.valid_until.is_(None))
            .order_by(desc(Stardust.confidence)).limit(30)
        )).scalars().all()
        total_considered += len(high_conf)
        seen_ids = {s["id"] for s in stardust_items}
        for s in high_conf:
            if s.id in seen_ids or used + _estimate_tokens(s.content) > budget:
                continue
            stardust_items.append(_stardust_to_dict(s))
            seen_ids.add(s.id)
            used += _estimate_tokens(s.content)

        # 3. Recent entities
        recent_entities = []
        if biome:
            entity_rows = (await db.execute(
                select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.planet_id == planet.id)
                .order_by(desc(Entity.last_seen)).limit(10)
            )).scalars().all()
            for e in entity_rows:
                entry = {"name": e.name, "type": e.entity_type, "tier": e.tier, "mentions": e.mention_count}
                cost = _estimate_tokens(json.dumps(entry))
                if used + cost > budget:
                    break
                recent_entities.append(entry)
                used += cost

        # 4. Medium-confidence (0.3-0.7) if budget remains
        if used < budget:
            med_conf = (await db.execute(
                select(Stardust).where(Stardust.planet_id == planet.id, Stardust.confidence >= 0.3, Stardust.confidence < 0.7, Stardust.valid_until.is_(None))
                .order_by(desc(Stardust.access_count)).limit(20)
            )).scalars().all()
            total_considered += len(med_conf)
            for s in med_conf:
                if s.id in seen_ids or used + _estimate_tokens(s.content) > budget:
                    continue
                stardust_items.append(_stardust_to_dict(s))
                seen_ids.add(s.id)
                used += _estimate_tokens(s.content)

        # Build planet context
        permanent = [s for s in stardust_items if s.get("gravity") in ("PLANET", "GALAXY")]
        planet_context = {"planet_name": planet.name, "permanent_knowledge": permanent, "active_biomes": list(active_biomes)}

        # Build biome context
        biome_stardust = [s for s in stardust_items if s.get("gravity") == "BIOME"] or stardust_items
        biome_context = {
            "biome_name": biome.name if biome else "",
            "lifecycle_state": biome.lifecycle_state if biome else "",
            "stardust": biome_stardust,
            "recent_entities": recent_entities,
        }

    confidences = [s.get("confidence", 0.5) for s in stardust_items]
    return ContextBundle(
        bundle_id=str(uuid.uuid4()),
        generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        sun_context=sun_context,
        planet_context=planet_context,
        biome_context=biome_context,
        retrieval_metadata=RetrievalMetadata(
            total_records_considered=total_considered,
            records_returned=len(stardust_items),
            cache_hits=cache_hits,
            token_estimate=used,
            confidence_range=[min(confidences), max(confidences)] if confidences else [],
        ),
    )
