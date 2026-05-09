import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, select, update, insert
from app.database import async_session
from app.models import Stardust, Biome, Contradiction
from app.models.subagent import AuditRun
from app.storage.chroma_client import ChromaClient, get_chroma_client
from app.storage.embedding_router import get_embedding_provider
from app.services import nebula_service

logger = logging.getLogger(__name__)

_audit_lock = asyncio.Lock()


class AuditResults:
    def __init__(self):
        self.records_reviewed = 0
        self.duplicates_merged = 0
        self.contradictions_found = 0
        self.contradictions_classified = 0
        self.promotions_made = 0
        self.confidence_decays = 0
        self.transitive_relationships_inferred = 0
        self.failures: list[str] = []


def _dedup_score(r: "Stardust") -> float:
    return r.confidence * 0.7 + min(r.access_count / 100, 1.0) * 0.3


async def _dedup(galaxy_id: str, results: AuditResults):
    """Find stardust pairs with cosine similarity > 0.95, merge duplicates."""
    try:
        chroma = ChromaClient(get_chroma_client())
        provider = get_embedding_provider()
        async with async_session() as db:
            PAGE_SIZE = 500
            last_id = ""
            seen_merged: set[str] = set()
            while True:
                records = (await db.execute(
                    select(Stardust).where(
                        Stardust.galaxy_id == galaxy_id,
                        Stardust.valid_until.is_(None),
                        Stardust.id > last_id,
                    ).order_by(Stardust.id).limit(PAGE_SIZE)
                )).scalars().all()
                if not records:
                    break
                results.records_reviewed += len(records)
                last_id = records[-1].id

                texts = [rec.content for rec in records if rec.chroma_id]
                rec_with_chroma = [rec for rec in records if rec.chroma_id]
                embeddings = await provider.embed_batch(texts, task_type="RETRIEVAL_QUERY") if texts else []
                embedding_map = {rec.id: emb for rec, emb in zip(rec_with_chroma, embeddings)}

                for rec in records:
                    if rec.id in seen_merged or rec.id not in embedding_map:
                        continue
                    embedding = embedding_map[rec.id]
                    similar = await chroma.query(galaxy_id, rec.planet_id, rec.region, embedding, n_results=5)
                    if not similar or not similar["ids"] or not similar["ids"][0]:
                        continue
                    for i, sid in enumerate(similar["ids"][0]):
                        if sid == rec.id or sid in seen_merged:
                            continue
                        dist = similar["distances"][0][i] if similar["distances"] else 1.0
                        if dist < 0.05:  # cosine distance < 0.05 ≈ similarity > 0.95
                            dup = (await db.execute(select(Stardust).where(Stardust.id == sid))).scalar_one_or_none()
                            if not dup or dup.valid_until is not None:  # skip already soft-deleted
                                continue
                            keep, remove = (rec, dup) if _dedup_score(rec) >= _dedup_score(dup) else (dup, rec)
                            keep_tags = set(json.loads(keep.context_tags) if isinstance(keep.context_tags, str) else keep.context_tags)
                            remove_tags = set(json.loads(remove.context_tags) if isinstance(remove.context_tags, str) else remove.context_tags)
                            merged_tags = list(keep_tags | remove_tags)
                            await db.execute(update(Stardust).where(Stardust.id == keep.id).values(
                                context_tags=merged_tags,
                                access_count=keep.access_count + remove.access_count,
                            ))
                            await db.execute(update(Stardust).where(Stardust.id == remove.id).values(
                                valid_until=datetime.now(timezone.utc).replace(tzinfo=None)
                            ))
                            if remove.chroma_id:
                                await chroma.delete(galaxy_id, remove.region, remove.chroma_id)
                            seen_merged.add(remove.id)
                            results.duplicates_merged += 1
                            await nebula_service.log_event(galaxy_id=galaxy_id, action_type="PROMOTE", initiated_by="audit_ai", record_id=keep.id, db=db)
            await db.commit()
    except Exception as e:
        logger.error(f"Dedup failed: {e}")


async def _detect_contradictions(galaxy_id: str, results: AuditResults):
    """Find stardust pairs with similarity 0.7-0.9, classify contradictions."""
    try:
        chroma = ChromaClient(get_chroma_client())
        provider = get_embedding_provider()
        negation_words = {"not", "never", "no", "don't", "doesn't", "isn't", "wasn't", "shouldn't", "can't", "won't"}
        async with async_session() as db:
            PAGE_SIZE = 200
            last_id = ""
            while True:
                records = (await db.execute(
                    select(Stardust).where(
                        Stardust.galaxy_id == galaxy_id,
                        Stardust.contradiction_id.is_(None),
                        Stardust.id > last_id,
                    ).order_by(Stardust.id).limit(PAGE_SIZE)
                )).scalars().all()
                if not records:
                    break
                last_id = records[-1].id

                # batch embed all records in this page upfront
                texts = [rec.content for rec in records if rec.chroma_id]
                rec_with_chroma = [rec for rec in records if rec.chroma_id]
                embeddings = await provider.embed_batch(texts, task_type="RETRIEVAL_QUERY") if texts else []
                embedding_map = {rec.id: emb for rec, emb in zip(rec_with_chroma, embeddings)}

                for rec in records:
                    if rec.id not in embedding_map:
                        continue
                    embedding = embedding_map[rec.id]
                    similar = await chroma.query(galaxy_id, rec.planet_id, rec.region, embedding, n_results=5)
                    if not similar or not similar["ids"] or not similar["ids"][0]:
                        continue
                    for i, sid in enumerate(similar["ids"][0]):
                        if sid == rec.id:
                            continue
                        dist = similar["distances"][0][i] if similar["distances"] else 1.0
                        if 0.1 < dist < 0.3:  # similarity 0.7-0.9
                            other = (await db.execute(select(Stardust).where(Stardust.id == sid))).scalar_one_or_none()
                            if not other:
                                continue
                            # Classify
                            rec_negs = negation_words & set(rec.content.lower().split())
                            other_negs = negation_words & set(other.content.lower().split())
                            if rec_negs != other_negs:
                                already = (await db.execute(
                                    select(Contradiction.id).where(or_(
                                        and_(Contradiction.record_a_id == rec.id, Contradiction.record_b_id == sid),
                                        and_(Contradiction.record_a_id == sid, Contradiction.record_b_id == rec.id),
                                    )).limit(1)
                                )).scalar_one_or_none()
                                if already:
                                    continue

                                # Determine type
                                if rec.valid_from and other.valid_from and abs((rec.valid_from - other.valid_from).days) > 30:
                                    conflict_type = "TEMPORAL"
                                else:
                                    rec_tags = set(json.loads(rec.context_tags) if isinstance(rec.context_tags, str) else rec.context_tags)
                                    other_tags = set(json.loads(other.context_tags) if isinstance(other.context_tags, str) else other.context_tags)
                                    conflict_type = "CONTEXTUAL" if len(rec_tags & other_tags) < 2 else "FACTUAL"

                                cid = str(uuid.uuid4())
                                await db.execute(insert(Contradiction).values(
                                    id=cid, galaxy_id=galaxy_id, region=rec.region,
                                    record_a_id=rec.id, record_b_id=sid,
                                    conflict_type=conflict_type, status="UNRESOLVED", detected_by="audit_ai",
                                ))
                                results.contradictions_found += 1
                                results.contradictions_classified += 1
                                await nebula_service.log_event(galaxy_id=galaxy_id, action_type="CONTRADICTION_DETECTED", initiated_by="audit_ai", record_id=cid, db=db)
            await db.commit()
    except Exception as e:
        logger.error(f"Contradiction detection failed: {e}")
        results.failures.append(f"contradiction_detection: {e}")


async def _infer_transitive_relationships(galaxy_id: str, results: AuditResults):
    """Infer transitive relationships across the knowledge graph."""
    try:
        from app.services.graph_service import graph_service
        from app.models.entity import Entity
        async with async_session() as db:
            # Get hub entities (most connected) — best candidates for transitive inference
            entities = (await db.execute(select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.tier >= 2).limit(50))).scalars().all()
            for entity in entities:
                inferred = await graph_service.infer_transitive_relationships(entity.id, galaxy_id, db)
                results.transitive_relationships_inferred += len(inferred)
            await db.commit()
    except Exception as e:
        logger.error(f"Transitive relationship inference failed: {e}")


async def _confidence_decay(galaxy_id: str, results: AuditResults):
    """Apply confidence decay to stale records. Updates last_accessed after decay to prevent compounding."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff_30 = now - timedelta(days=30)
    cutoff_90 = now - timedelta(days=90)
    async with async_session() as db:
        stale = (await db.execute(
            select(Stardust).where(Stardust.galaxy_id == galaxy_id, Stardust.last_accessed < cutoff_30, Stardust.valid_until.is_(None))
        )).scalars().all()

        for s in stale:
            old_conf = s.confidence
            factor = 0.85 if (s.last_accessed and s.last_accessed < cutoff_90) else 0.95
            new_conf = old_conf * factor
            # Set last_accessed to now so this record won't be re-decayed next audit
            await db.execute(update(Stardust).where(Stardust.id == s.id).values(
                confidence=new_conf, last_accessed=now,
            ))
            results.confidence_decays += 1
            await nebula_service.log_event(galaxy_id=galaxy_id, action_type="EVICT", initiated_by="audit_ai", record_id=s.id, confidence_delta=new_conf - old_conf, db=db)
        await db.commit()


async def _cache_promotion(galaxy_id: str, results: AuditResults):
    """Promote qualifying cache entries to PLANET gravity."""
    async with async_session() as db:
        candidates = (await db.execute(
            select(Stardust).where(
                Stardust.galaxy_id == galaxy_id, Stardust.gravity == "BIOME",
                Stardust.access_count >= 3, Stardust.reinforcement_sources >= 2, Stardust.confidence >= 0.7,
            )
        )).scalars().all()
        for s in candidates:
            await db.execute(update(Stardust).where(Stardust.id == s.id).values(gravity="PLANET"))
            results.promotions_made += 1
            await nebula_service.log_event(galaxy_id=galaxy_id, action_type="PROMOTE", initiated_by="audit_ai", record_id=s.id, db=db)
        await db.commit()


async def _biome_lifecycle(galaxy_id: str):
    """Advance biome lifecycle states."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session() as db:
        biomes = (await db.execute(select(Biome).where(Biome.galaxy_id == galaxy_id))).scalars().all()
        for b in biomes:
            new_state = b.lifecycle_state
            if b.lifecycle_state == "SEED" and b.stardust_count > 10:
                new_state = "ACTIVE"
            elif b.lifecycle_state == "ACTIVE":
                if b.stardust_count > 100:
                    new_state = "MATURE"
                elif b.last_active_at and (now - b.last_active_at).days > 14:
                    new_state = "DORMANT"
            elif b.lifecycle_state == "MATURE" and b.last_active_at and (now - b.last_active_at).days > 30:
                new_state = "DORMANT"
            elif b.lifecycle_state == "DORMANT" and b.last_active_at and (now - b.last_active_at).days > 90:
                new_state = "ARCHIVED"
            if new_state != b.lifecycle_state:
                await db.execute(update(Biome).where(Biome.id == b.id).values(lifecycle_state=new_state))
        await db.commit()


async def _update_strength(galaxy_id: str):
    """Recompute galaxy strength using the 5-dimension scoring in galaxy_service."""
    from app.services import galaxy_service
    async with async_session() as db:
        await galaxy_service.compute_galaxy_strength(galaxy_id, db)


async def run_audit(galaxy_id: str) -> dict:
    """Run all 7 audit functions. Guarded against concurrent execution."""
    if _audit_lock.locked():
        return {"error": "Audit already in progress", "skipped": True}
    async with _audit_lock:
        start = datetime.now(timezone.utc).replace(tzinfo=None)
        results = AuditResults()

        await _dedup(galaxy_id, results)
        await _detect_contradictions(galaxy_id, results)
        await _infer_transitive_relationships(galaxy_id, results)
        await _confidence_decay(galaxy_id, results)
        await _cache_promotion(galaxy_id, results)
        await _biome_lifecycle(galaxy_id)
        await _update_strength(galaxy_id)

        # Record audit run
        duration_ms = int((datetime.now(timezone.utc).replace(tzinfo=None) - start).total_seconds() * 1000)
        audit_id = str(uuid.uuid4())
        async with async_session() as db:
            await db.execute(insert(AuditRun).values(
                id=audit_id, galaxy_id=galaxy_id, run_at=start, records_reviewed=results.records_reviewed,
                duplicates_merged=results.duplicates_merged, contradictions_found=results.contradictions_found,
                contradictions_classified=results.contradictions_classified, promotions_made=results.promotions_made,
                confidence_decays=results.confidence_decays, duration_ms=duration_ms,
                run_by="scheduler",
                summary=f"Reviewed {results.records_reviewed}, merged {results.duplicates_merged} dupes, found {results.contradictions_found} contradictions, decayed {results.confidence_decays}, promoted {results.promotions_made}",
            ))
            await db.commit()

        await nebula_service.log_event(galaxy_id=galaxy_id, action_type="AUDIT_RUN", initiated_by="audit_ai", record_id=audit_id)

        return {"audit_id": audit_id, "duration_ms": duration_ms, "records_reviewed": results.records_reviewed,
                "duplicates_merged": results.duplicates_merged, "contradictions_found": results.contradictions_found,
                "promotions_made": results.promotions_made, "confidence_decays": results.confidence_decays,
                "failures": results.failures}
