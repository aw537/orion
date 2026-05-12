import json
import logging
import time
from datetime import datetime, timezone
from collections import defaultdict
from sqlalchemy import select
from app.database import async_session
from app.models import Planet, Biome, Stardust
from app.storage.redis_client import RedisClient, get_redis
from app.storage.chroma_client import ChromaClient, get_chroma_client
from app.storage.embedding_router import get_embedding_provider
from app.services import nebula_service
from app.schemas.stardust import SearchRecord, SearchResponse, RetrievalMetadata

logger = logging.getLogger(__name__)
RRF_K = 60


def _parse_dt(value: str | None) -> datetime | None:
    if not value or value == "null":
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _rrf_fuse(rankings: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """Reciprocal Rank Fusion across multiple ranked lists."""
    scores: dict[str, float] = defaultdict(float)
    docs: dict[str, dict] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            doc_id = doc["id"]
            scores[doc_id] += 1.0 / (k + rank + 1)
            if doc_id not in docs:
                docs[doc_id] = doc
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [docs[did] for did in sorted_ids]


async def search(
    query: str,
    galaxy_id: str,
    planet_name: str | None = None,
    biome_name: str | None = None,
    region: str | None = None,
    limit: int = 5,
) -> SearchResponse:
    start = time.time()
    cache_hits = 0
    sources_checked = []
    all_records: list[dict] = []

    async with async_session() as db:
        # Resolve planet IDs
        if planet_name:
            planet = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy_id, Planet.name == planet_name))).scalar_one_or_none()
            planet_ids = [planet.id] if planet else []
        else:
            planet_ids = list((await db.execute(select(Planet.id).where(Planet.galaxy_id == galaxy_id))).scalars().all())

        biome_id = None
        if biome_name and planet_ids:
            biome = (await db.execute(select(Biome).where(Biome.planet_id.in_(planet_ids), Biome.name == biome_name))).scalar_one_or_none()
            biome_id = biome.id if biome else None

        # 1. Redis cache check
        try:
            redis = await get_redis()
            rc = RedisClient(redis)
            sources_checked.append("redis_cache")
            all_biomes = (await db.execute(select(Biome).where(Biome.planet_id.in_(planet_ids)))).scalars().all()
            for b in all_biomes:
                if biome_id and b.id != biome_id:
                    continue
                cached = await rc.get_all_cached_stardust(galaxy_id, b.id)
                query_lower = query.lower()
                for record in cached:
                    content = record.get("content", "")
                    if query_lower in content.lower():
                        cache_hits += 1
                        all_records.append(record)
        except Exception as e:
            logger.warning(f"Redis search failed: {e}")

    # 2. Chroma semantic search with multi-graph retrieval + RRF
    try:
        provider = get_embedding_provider()
        query_embedding = await provider.embed(query, task_type="RETRIEVAL_QUERY")
        chroma = ChromaClient(get_chroma_client())

        gravity_levels = ["BIOME", "PLANET", "GALAXY"]
        where_filter = {"gravity": {"$in": gravity_levels}}
        if biome_id:
            where_filter = {"$and": [{"gravity": {"$in": gravity_levels}}, {"biome_id": biome_id}]}

        regions_to_search = [region] if region else ["analytical", "procedural", "contextual", "creative", "empathetic", "critical", "strategic"]

        for pid in planet_ids:
            semantic_ranking = []
            recency_ranking = []
            confidence_ranking = []

            for r in regions_to_search:
                sources_checked.append(f"chroma_{r}")
                results = await chroma.query(galaxy_id, pid, r, query_embedding, n_results=10, where=where_filter)
                if not results or not results["ids"] or not results["ids"][0]:
                    continue
                for i, sid in enumerate(results["ids"][0]):
                    dist = results["distances"][0][i] if results["distances"] else 1.0
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    content = results["documents"][0][i] if results["documents"] else ""
                    score = 1.0 - dist  # cosine distance to similarity

                    doc = {"id": sid, "content": content, "metadata": meta, "score": score, "region": r, "planet_id": pid}
                    semantic_ranking.append(doc)

                    # Recency: score * (1 / (1 + days_since_created))
                    valid_from = meta.get("valid_from", "")
                    try:
                        created = datetime.fromisoformat(valid_from)
                        if created.tzinfo:
                            created = created.replace(tzinfo=None)
                        days = max((datetime.now(timezone.utc).replace(tzinfo=None) - created).days, 0)
                    except (ValueError, TypeError):
                        days = 30
                    recency_ranking.append({**doc, "score": score * (1.0 / (1 + days))})

                    # Confidence: score * confidence
                    conf = float(meta.get("confidence", 0.5))
                    confidence_ranking.append({**doc, "score": score * conf})

            # Sort each ranking by score desc
            semantic_ranking.sort(key=lambda x: x["score"], reverse=True)
            recency_ranking.sort(key=lambda x: x["score"], reverse=True)
            confidence_ranking.sort(key=lambda x: x["score"], reverse=True)

            fused = _rrf_fuse([semantic_ranking, recency_ranking, confidence_ranking])
            all_records.extend(fused)
    except Exception as e:
        logger.warning(f"Chroma search failed: {e}")

    # Deduplicate by ID
    seen = set()
    unique = []
    for r in all_records:
        rid = r.get("id") or r.get("stardust_id", "")
        if rid not in seen:
            seen.add(rid)
            unique.append(r)

    # Postgres fulltext fallback — triggered when Redis + Chroma both returned nothing.
    # Splits query into tokens and matches any term against stardust content via ILIKE.
    if not unique:
        try:
            from sqlalchemy import or_
            sources_checked.append("postgres_fulltext")
            terms = [t.strip() for t in query.split() if len(t.strip()) > 2]
            async with async_session() as db:
                q = select(Stardust).where(Stardust.galaxy_id == galaxy_id)
                if planet_ids:
                    q = q.where(Stardust.planet_id.in_(planet_ids))
                if biome_id:
                    q = q.where(Stardust.biome_id == biome_id)
                if region:
                    q = q.where(Stardust.region == region)
                if terms:
                    escaped = [t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for t in terms]
                    q = q.where(or_(*[Stardust.content.ilike(f"%{t}%", escape="\\") for t in escaped]))
                rows = (await db.execute(q.order_by(Stardust.confidence.desc()).limit(limit))).scalars().all()
                for s in rows:
                    all_records.append({
                        "id": s.id,
                        "content": s.content,
                        "metadata": {
                            "confidence": s.confidence,
                            "region": s.region,
                            "valid_from": s.valid_from.isoformat() if s.valid_from else "",
                            "source_agent": s.source_agent,
                            "access_count": s.access_count,
                            "context_tags": s.context_tags,
                        },
                        "score": s.confidence,
                        "region": s.region,
                        "planet_id": s.planet_id,
                    })
            # Re-deduplicate with fallback results
            seen2: set[str] = set()
            unique = []
            for r in all_records:
                rid = r.get("id") or r.get("stardust_id", "")
                if rid not in seen2:
                    seen2.add(rid)
                    unique.append(r)
        except Exception as e:
            logger.warning(f"Postgres fulltext fallback failed: {e}")

    # Build response records
    records = []
    async with async_session() as db:
        for doc in unique[:limit]:
            sid = doc.get("id", "")
            meta = doc.get("metadata", {})
            content = doc.get("content", "")
            biome_n = ""
            planet_n = ""
            conf = float(meta.get("confidence", doc.get("confidence", 0.5)))
            tags = meta.get("context_tags", doc.get("context_tags", "[]"))
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []

            # Look up names
            s = (await db.execute(select(Stardust).where(Stardust.id == sid))).scalar_one_or_none()
            if s:
                biome_row = (await db.execute(select(Biome.name).where(Biome.id == s.biome_id))).scalar()
                planet_row = (await db.execute(select(Planet.name).where(Planet.id == s.planet_id))).scalar()
                biome_n = biome_row or ""
                planet_n = planet_row or ""
                content = s.content
                conf = s.confidence
                tags = json.loads(s.context_tags) if isinstance(s.context_tags, str) else s.context_tags

            records.append(SearchRecord(
                id=sid, content=content, region=doc.get("region", meta.get("region", "contextual")),
                biome_name=biome_n, planet_name=planet_n, confidence=conf,
                valid_from=_parse_dt(meta.get("valid_from")) or datetime.now(timezone.utc).replace(tzinfo=None),
                valid_until=None, context_tags=tags,
                source_agent=meta.get("source_agent", doc.get("source_agent")),
                access_count=int(meta.get("access_count", doc.get("access_count", 0))),
            ))

        # Update last_accessed and access_count for returned records
        if records:
            try:
                from sqlalchemy import update
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                returned_ids = [r.id for r in records]
                await db.execute(
                    update(Stardust)
                    .where(Stardust.id.in_(returned_ids))
                    .values(last_accessed=now, access_count=Stardust.access_count + 1)
                )
                await db.commit()
            except Exception as e:
                logger.warning(f"Failed to update access tracking: {e}")

    # Log READ
    try:
        await nebula_service.log_event(galaxy_id=galaxy_id, action_type="READ", initiated_by="search", cache_hit=cache_hits > 0, latency_ms=int((time.time() - start) * 1000))
    except Exception:
        pass

    elapsed_ms = int((time.time() - start) * 1000)
    confidences = [r.confidence for r in records]
    return SearchResponse(
        records=records,
        retrieval_metadata=RetrievalMetadata(
            sources_checked=list(set(sources_checked)), cache_hits=cache_hits,
            total_records_considered=len(unique), records_returned=len(records),
            confidence_range=[min(confidences), max(confidences)] if confidences else [],
            retrieval_latency_ms=elapsed_ms,
        ),
    )
