import json
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import insert, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models.stardust import Stardust
from app.models.biome import Biome
from app.models.planet import Planet
from app.models.contradiction import Contradiction
from app.models.entity import Entity, EntityStardust, EntityTimeline
from app.storage.redis_client import RedisClient, get_redis
from app.storage.chroma_client import ChromaClient, get_chroma_client
from app.storage.embedding_router import get_embedding_provider
from app.services import nebula_service
from app.extraction.entity_extractor import EntityExtractor
from app.schemas.stardust import WriteReceipt, ConflictInfo

logger = logging.getLogger(__name__)
_extractor = EntityExtractor()

# Entity tier thresholds per spec
TIER_THRESHOLDS = {
    3: {"min_mentions": 8, "min_biomes": 2},
    2: {"min_mentions": 3, "min_biomes": 1},
    1: {"min_mentions": 1, "min_biomes": 1},
}


def _compute_tier(mention_count: int, biomes_count: int) -> int:
    for tier in [3, 2, 1]:
        t = TIER_THRESHOLDS[tier]
        if mention_count >= t["min_mentions"] and biomes_count >= t["min_biomes"]:
            return tier
    return 1


async def _resolve_biome(db: AsyncSession, planet_id: str, biome_name: str | None) -> Biome | None:
    if biome_name:
        row = (await db.execute(select(Biome).where(Biome.planet_id == planet_id, Biome.name == biome_name))).scalar_one_or_none()
        return row
    # Fallback: most recently active biome for this planet
    row = (await db.execute(
        select(Biome).where(Biome.planet_id == planet_id).order_by(Biome.last_active_at.desc().nullslast()).limit(1)
    )).scalar_one_or_none()
    return row


async def _check_contradiction(redis_client: RedisClient, galaxy_id: str, biome_id: str, content: str, context_tags: list[str]) -> str | None:
    """Check if any cached record shares >2 context tags AND has contradictory content via embedding similarity."""
    if len(context_tags) < 2:
        return None
    cached = await redis_client.get_all_cached_stardust(galaxy_id, biome_id)
    tag_set = set(context_tags)

    # Get embedding for new content
    try:
        from app.storage.embedding_router import get_embedding_provider
        provider = get_embedding_provider()
        new_embedding = await provider.embed(content, task_type="RETRIEVAL_DOCUMENT")
    except Exception:
        return None  # Can't check without embeddings — skip rather than false-positive

    for record in cached:
        existing_tags = set(json.loads(record.get("context_tags", "[]")) if isinstance(record.get("context_tags"), str) else record.get("context_tags", []))
        if len(tag_set & existing_tags) > 2:
            # Compute cosine similarity via embedding
            try:
                existing_content = record.get("content", "")
                existing_embedding = await provider.embed(existing_content, task_type="RETRIEVAL_DOCUMENT")
                similarity = _cosine_similarity(new_embedding, existing_embedding)
                # Low similarity between records sharing many tags = likely contradiction
                if similarity < 0.75:
                    return record.get("id")
            except Exception:
                continue
    return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def write_stardust(
    content: str,
    galaxy_id: str,
    planet_name: str | None = None,
    biome_name: str | None = None,
    region: str = "contextual",
    context_tags: list[str] | None = None,
    gravity: str = "BIOME",
    source_agent: str | None = None,
    confidence: float = 0.5,
    reasoning: str | None = None,
    supersedes: list[str] | None = None,
    filename: str | None = None,
) -> WriteReceipt:
    tags = context_tags or []
    stardust_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with async_session() as db:
        async with db.begin():
            from app.services.planet_assignment_engine import planet_assignment_engine
            from app.models.routing_log import RoutingLog

            # ── Routing: resolve planet/biome assignment ──
            assignment = await planet_assignment_engine.assign(
                content=content, galaxy_id=galaxy_id,
                caller_planet=planet_name, caller_biome=biome_name,
                filename=filename, db=db,
            )
            planet = assignment.planet
            biome = assignment.biome or await _resolve_biome(db, planet.id, biome_name)
            if not biome:
                biome = await _resolve_biome(db, planet.id, None)
            if not biome:
                raise ValueError(f"No biome found for planet '{planet.name}'")

            # Contradiction check (Redis — no DB queries, no autoflush risk)
            redis = await get_redis()
            rc = RedisClient(redis)
            conflict_id = None
            contradiction_info = None
            existing_id = await _check_contradiction(rc, galaxy_id, biome.id, content, tags)
            if existing_id:
                conflict_id = str(uuid.uuid4())
                await db.execute(insert(Contradiction).values(
                    id=conflict_id, galaxy_id=galaxy_id, region=region,
                    record_a_id=existing_id, record_b_id=stardust_id,
                    conflict_type="FACTUAL", status="UNRESOLVED", detected_by=source_agent or "system",
                ))
                contradiction_info = ConflictInfo(
                    conflict_id=conflict_id, conflict_type="FACTUAL",
                    existing_record_id=existing_id, recommended_action="COEXIST",
                )

            # ── Write stardust first so FK constraints are satisfied ──
            await db.execute(insert(Stardust).values(
                id=stardust_id, biome_id=biome.id, planet_id=planet.id, galaxy_id=galaxy_id,
                content=content, region=region, gravity=gravity, confidence=confidence,
                valid_from=now, _context_tags=tags, contradiction_id=conflict_id,
                source_agent=source_agent, created_at=now, reinforcement_sources=1,
                reasoning=reasoning, supersedes=supersedes,
            ))

            # Update biome and planet counts
            await db.execute(update(Biome).where(Biome.id == biome.id).values(
                last_active_at=now, stardust_count=Biome.stardust_count + 1,
            ))
            await db.execute(update(Planet).where(Planet.id == planet.id).values(
                stardust_count=Planet.stardust_count + 1,
            ))

            # ── Routing log: must come after stardust insert (FK: routing_log.stardust_id -> stardust.id) ──
            db.add(RoutingLog(
                galaxy_id=galaxy_id, stardust_id=stardust_id,
                caller_suggested_planet=planet_name, caller_suggested_biome=biome_name,
                assigned_planet_id=planet.id,
                assigned_biome_id=biome.id if biome else None,
                routing_method=assignment.method, confidence=assignment.confidence,
                reasoning=assignment.reasoning, graphify_cluster=assignment.graphify_cluster,
            ))

            # Nebula log
            nebula_action = "INBOX_ROUTED" if assignment.method == "inbox_fallback" else "PLANET_ROUTED"
            await nebula_service.log_event(
                galaxy_id=galaxy_id, action_type=nebula_action,
                initiated_by=source_agent or "system",
                planet_id=planet.id, biome_id=biome.id,
                payload_after=json.dumps({
                    "method": assignment.method, "confidence": assignment.confidence,
                    "caller_suggested": planet_name, "assigned_planet": planet.name,
                    "override": assignment.override_caller,
                }),
                db=db,
            )

            event_id = await nebula_service.log_event(
                galaxy_id=galaxy_id, action_type="WRITE", initiated_by=source_agent or "system",
                planet_id=planet.id, biome_id=biome.id, region=region, record_id=stardust_id, db=db,
            )

            if conflict_id:
                await nebula_service.log_event(
                    galaxy_id=galaxy_id, action_type="CONTRADICTION_DETECTED",
                    initiated_by=source_agent or "system", record_id=conflict_id, db=db,
                )

        # Write to Redis (outside transaction — best effort)
        try:
            stardust_data = {
                "id": stardust_id, "content": content, "region": region, "gravity": gravity,
                "confidence": confidence, "context_tags": tags, "biome_id": biome.id,
                "planet_id": planet.id, "galaxy_id": galaxy_id, "source_agent": source_agent,
                "created_at": now.isoformat(),
            }
            from app.config import get_cache_ttl
            ttl = get_cache_ttl(region, biome.cache_ttl_seconds)
            await rc.cache_stardust(galaxy_id, biome.id, stardust_id, stardust_data, ttl)
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

        # H1.5: Invalidate synthesis caches for this galaxy
        try:
            cursor = 0
            pattern = f"orion:{galaxy_id}:synthesis:*"
            keys_to_delete: list[str] = []
            while True:
                cursor, batch = await redis.scan(cursor, match=pattern, count=100)
                keys_to_delete.extend(batch)
                if cursor == 0:
                    break
            if keys_to_delete:
                await redis.delete(*keys_to_delete)
        except Exception:
            pass

        return WriteReceipt(
            status="written_with_conflict" if conflict_id else "success",
            stardust_id=stardust_id, biome_id=biome.id, planet_id=planet.id,
            planet_name=planet.name, biome_name=biome.name,
            routing_method=assignment.method, routing_reasoning=assignment.reasoning,
            cache_ttl_seconds=biome.cache_ttl_seconds, nebula_event_id=event_id,
            contradiction_check="conflict" if conflict_id else "clean",
            contradiction=contradiction_info,
        )


async def run_async_tasks(stardust_id: str, content: str, galaxy_id: str, planet_id: str, biome_id: str, region: str):
    """Background tasks: entity extraction + Chroma indexing + biome lifecycle."""
    # Entity extraction
    try:
        entities = _extractor.extract(content, galaxy_id)
        if entities:
            async with async_session() as db:
                async with db.begin():
                    for ent in entities:
                        existing = (await db.execute(
                            select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.name == ent.name, Entity.entity_type == ent.entity_type)
                        )).scalar_one_or_none()

                        if existing:
                            new_count = existing.mention_count + 1
                            await db.execute(update(Entity).where(Entity.id == existing.id).values(
                                mention_count=new_count, last_seen=datetime.now(timezone.utc).replace(tzinfo=None),
                            ))
                            entity_id = existing.id
                            # Check tier upgrade with proper thresholds
                            biomes_count = (await db.execute(
                                select(func.count(func.distinct(Stardust.biome_id)))
                                .join(EntityStardust, EntityStardust.stardust_id == Stardust.id)
                                .where(EntityStardust.entity_id == entity_id)
                            )).scalar() or 1
                            old_tier = existing.tier
                            new_tier = _compute_tier(new_count, biomes_count)
                            if new_tier != old_tier:
                                await db.execute(update(Entity).where(Entity.id == entity_id).values(tier=new_tier))
                                await nebula_service.log_event(
                                    galaxy_id=galaxy_id, action_type="ENTITY_ENRICHED",
                                    record_id=entity_id, initiated_by="system",
                                    planet_id=planet_id, biome_id=biome_id,
                                    payload_after=json.dumps({"entity_name": ent.name, "entity_type": ent.entity_type, "previous_tier": old_tier, "new_tier": new_tier}),
                                    db=db,
                                )
                        else:
                            entity_id = str(uuid.uuid4())
                            await db.execute(insert(Entity).values(
                                id=entity_id, galaxy_id=galaxy_id, planet_id=planet_id,
                                name=ent.name, entity_type=ent.entity_type,
                            ))
                            await nebula_service.log_event(
                                galaxy_id=galaxy_id, action_type="ENTITY_EXTRACTED",
                                record_id=entity_id, initiated_by="system",
                                planet_id=planet_id, biome_id=biome_id,
                                payload_after=json.dumps({"entity_name": ent.name, "entity_type": ent.entity_type, "entity_tier": 1}),
                                db=db,
                            )

                        # Link
                        await db.execute(insert(EntityStardust).values(
                            entity_id=entity_id, stardust_id=stardust_id, relationship_type="mentioned_in",
                        ).on_conflict_do_nothing())

                        # Timeline
                        await db.execute(insert(EntityTimeline).values(
                            id=str(uuid.uuid4()), entity_id=entity_id, event_type="mention",
                            event_content=content[:200], source_stardust_id=stardust_id,
                        ))
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")

    # Chroma indexing
    try:
        provider = get_embedding_provider()
        embedding = await provider.embed(content)
        chroma = ChromaClient(get_chroma_client())
        # Read actual record values instead of hardcoding
        async with async_session() as db2:
            rec = (await db2.execute(select(Stardust).where(Stardust.id == stardust_id))).scalar_one_or_none()
        metadata = {
            "stardust_id": stardust_id, "biome_id": biome_id, "planet_id": planet_id,
            "galaxy_id": galaxy_id, "gravity": rec.gravity if rec else "BIOME",
            "confidence": rec.confidence if rec else 0.5,
            "valid_from": (rec.valid_from.isoformat() if rec and rec.valid_from else datetime.now(timezone.utc).replace(tzinfo=None).isoformat()),
            "valid_until": "null",
            "contradiction_status": "conflict" if (rec and rec.contradiction_id) else "clean",
            "access_count": rec.access_count if rec else 0,
            "reinforcement_sources": rec.reinforcement_sources if rec else 1,
        }
        chroma_id = await chroma.upsert_stardust(galaxy_id, planet_id, region, stardust_id, content, embedding, metadata)
        async with async_session() as db:
            await db.execute(update(Stardust).where(Stardust.id == stardust_id).values(chroma_id=chroma_id))
            await db.commit()
    except Exception as e:
        logger.warning(f"Chroma indexing failed (will retry on audit): {e}")

    # Biome lifecycle check
    try:
        async with async_session() as db:
            biome = (await db.execute(select(Biome).where(Biome.id == biome_id))).scalar_one_or_none()
            if biome and biome.lifecycle_state == "SEED" and biome.stardust_count > 10:
                await db.execute(update(Biome).where(Biome.id == biome_id).values(lifecycle_state="ACTIVE"))
                await db.commit()
    except Exception as e:
        logger.warning(f"Biome lifecycle check failed: {e}")
