"""Knowledge Integration Engine — runs async after every brain.think."""
import json
import time
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.stardust import Stardust
from app.models.entity import Entity, EntityStardust
from app.models.brain import KnowledgeIntegrationLog, StardustRelationship
from app.extraction.relationship_extractor import relationship_extractor
from app.services.graph_service import graph_service
from app.services import nebula_service

logger = logging.getLogger(__name__)


class KnowledgeIntegrationEngine:

    async def integrate(self, stardust: Stardust, galaxy_id: str, db: AsyncSession) -> dict:
        start = time.monotonic()
        result = {
            "supersessions_processed": 0,
            "contradictions_detected": 0,
            "relationships_extracted": 0,
            "adjacencies_flagged": 0,
        }

        # 1. Process explicit supersession
        if stardust.supersedes:
            superseded_ids = stardust.supersedes if isinstance(stardust.supersedes, list) else json.loads(stardust.supersedes)
            for sid in superseded_ids:
                await self._process_supersession(stardust, sid, galaxy_id, db)
                result["supersessions_processed"] += 1

        # 2. Extract typed relationships → update knowledge graph
        entities = await self._get_entities_for_stardust(stardust, db)
        if len(entities) >= 2:
            relationships = relationship_extractor.extract(stardust.content, entities)
            if stardust.reasoning:
                relationships.extend(relationship_extractor.extract(stardust.reasoning, entities))
            # Deduplicate across content + reasoning
            seen = set()
            unique_rels = []
            for rel in relationships:
                k = (rel.source_entity.id, rel.target_entity.id, rel.relationship_type)
                if k not in seen:
                    seen.add(k)
                    unique_rels.append(rel)

            for rel in unique_rels:
                await graph_service.upsert_relationship(
                    source_id=rel.source_entity.id, target_id=rel.target_entity.id,
                    rel_type=rel.relationship_type, confidence=rel.confidence,
                    stardust_id=stardust.id, galaxy_id=galaxy_id, db=db,
                )
            result["relationships_extracted"] = len(unique_rels)

            # Co-occurrence: entities sharing the same stardust get a WORKS_WITH edge
            # (only if no explicit relationship was already extracted between them)
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    pair = (entities[i].id, entities[j].id)
                    reverse_pair = (entities[j].id, entities[i].id)
                    if pair not in seen and reverse_pair not in seen:
                        await graph_service.upsert_relationship(
                            source_id=entities[i].id, target_id=entities[j].id,
                            rel_type="WORKS_WITH", confidence=0.5,
                            stardust_id=stardust.id, galaxy_id=galaxy_id, db=db,
                        )
                        seen.add(pair)
                        result["relationships_extracted"] += 1

        # 3. Update backlinks
        if entities:
            await graph_service.update_backlinks(stardust, entities, db)

        # 4. Log integration
        duration_ms = int((time.monotonic() - start) * 1000)
        db.add(KnowledgeIntegrationLog(
            id=str(uuid4()), stardust_id=stardust.id,
            agent_identity_id="system",
            contradictions_detected=result["contradictions_detected"],
            supersessions_processed=result["supersessions_processed"],
            relationships_extracted=result["relationships_extracted"],
            adjacencies_flagged=result["adjacencies_flagged"],
            integration_duration_ms=duration_ms,
        ))
        # Flush only — caller owns the transaction boundary and must commit.
        await db.flush()

        try:
            await nebula_service.log_event(
                action_type="INTEGRATION_COMPLETE", galaxy_id=galaxy_id,
                record_id=stardust.id, initiated_by="integration_engine",
                latency_ms=duration_ms,
            )
        except Exception:
            pass

        return result

    async def _process_supersession(
        self, new_record: Stardust, superseded_id: str, galaxy_id: str, db: AsyncSession,
    ) -> None:
        old = await db.get(Stardust, superseded_id)
        if old and old.galaxy_id == galaxy_id:
            old.valid_until = datetime.now(timezone.utc).replace(tzinfo=None)
            tags = list(old.context_tags) if isinstance(old.context_tags, list) else json.loads(old.context_tags or "[]")
            tags.append(f"superseded_by:{new_record.id}")
            old.context_tags = tags

            for rel_type, src, tgt in [
                ("SUPERSEDES", new_record.id, superseded_id),
                ("SUPERSEDED_BY", superseded_id, new_record.id),
            ]:
                db.add(StardustRelationship(
                    id=str(uuid4()), galaxy_id=galaxy_id,
                    source_stardust_id=src, target_stardust_id=tgt,
                    relationship_type=rel_type, created_by="integration_engine",
                ))

            try:
                await nebula_service.log_event(
                    action_type="SUPERSESSION", galaxy_id=galaxy_id,
                    record_id=superseded_id, initiated_by="integration_engine",
                    payload_after=json.dumps({"superseded_by": new_record.id}),
                )
            except Exception:
                pass

    async def _get_entities_for_stardust(self, stardust: Stardust, db: AsyncSession) -> list[Entity]:
        links = (await db.execute(
            select(EntityStardust.entity_id).where(EntityStardust.stardust_id == stardust.id)
        )).scalars().all()
        if not links:
            return []
        entities = (await db.execute(
            select(Entity).where(Entity.id.in_(links))
        )).scalars().all()
        return list(entities)


integration_engine = KnowledgeIntegrationEngine()
