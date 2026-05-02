"""Contradiction Resolution Service — resolves flagged contradictions."""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.contradiction import Contradiction
from app.models.stardust import Stardust
from app.models.brain import StardustRelationship
from app.services import nebula_service

logger = logging.getLogger(__name__)


@dataclass
class ContradictionResolutionResult:
    contradiction_id: str
    status: str
    new_stardust_id: str | None = None


class ContradictionService:

    async def resolve_contradiction(
        self,
        contradiction_id: str,
        resolution_type: str,
        synthesis_content: str | None,
        galaxy_id: str,
        resolved_by: str,
        db: AsyncSession,
    ) -> ContradictionResolutionResult:
        contradiction = await db.get(Contradiction, contradiction_id)
        if not contradiction:
            raise ValueError(f"Contradiction {contradiction_id} not found")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        new_stardust_id = None

        if resolution_type == "a_supersedes_b":
            await self._supersede(contradiction.record_a_id, contradiction.record_b_id, now, db)
            contradiction.status = "DEPRECATED"

        elif resolution_type == "b_supersedes_a":
            await self._supersede(contradiction.record_b_id, contradiction.record_a_id, now, db)
            contradiction.status = "DEPRECATED"

        elif resolution_type == "coexist":
            contradiction.conflict_type = "CONTEXTUAL"
            contradiction.status = "COEXISTING"
            await self._mark_coexisting(contradiction.record_a_id, contradiction.record_b_id, db)

        elif resolution_type == "synthesize":
            if not synthesis_content:
                raise ValueError("synthesis_content required for synthesize resolution")
            new_stardust_id = await self._synthesize(
                contradiction, synthesis_content, galaxy_id, now, db,
            )
            contradiction.status = "MERGED"

        else:
            raise ValueError(f"Unknown resolution_type: {resolution_type}")

        contradiction.resolved_at = now
        contradiction.resolved_by = resolved_by
        contradiction.human_reviewed = 1

        # Log to Nebula inside transaction so it's atomic with the resolution
        try:
            await nebula_service.log_event(
                galaxy_id=galaxy_id,
                action_type="CONTRADICTION_RESOLVED",
                initiated_by=resolved_by,
                payload_after=json.dumps({
                    "contradiction_id": contradiction_id,
                    "resolution_type": resolution_type,
                }),
                db=db,
            )
        except Exception:
            pass

        await db.commit()

        # Invalidate galaxy strength cache so health score recalculates
        try:
            from app.storage.redis_client import get_redis
            redis = await get_redis()
            await redis.delete(f"orion:{galaxy_id}:strength")
        except Exception:
            pass

        return ContradictionResolutionResult(
            contradiction_id=contradiction_id,
            status=contradiction.status,
            new_stardust_id=new_stardust_id,
        )

    async def _supersede(
        self, winner_id: str, loser_id: str, now: datetime, db: AsyncSession,
    ) -> None:
        loser = await db.get(Stardust, loser_id)
        if loser:
            loser.valid_until = now
        winner = await db.get(Stardust, winner_id)
        if winner:
            winner.confidence = min(1.0, winner.confidence + 0.05)
        # Create SUPERSEDES relationship
        db.add(StardustRelationship(
            id=str(uuid4()), galaxy_id=winner.galaxy_id if winner else "",
            source_stardust_id=winner_id, target_stardust_id=loser_id,
            relationship_type="SUPERSEDES", confidence=1.0, created_by="contradiction_resolution",
        ))

    async def _mark_coexisting(
        self, record_a_id: str, record_b_id: str, db: AsyncSession,
    ) -> None:
        for rid, other_id in [(record_a_id, record_b_id), (record_b_id, record_a_id)]:
            record = await db.get(Stardust, rid)
            if record:
                tags = list(record.context_tags)
                tag = f"coexists_with:{other_id}"
                if tag not in tags:
                    tags.append(tag)
                    record.context_tags = tags

    async def _synthesize(
        self, contradiction: Contradiction, content: str,
        galaxy_id: str, now: datetime, db: AsyncSession,
    ) -> str:
        # Get one of the originals to inherit biome/planet
        original = await db.get(Stardust, contradiction.record_a_id)
        biome_id = original.biome_id if original else ""
        planet_id = original.planet_id if original else ""

        new_id = str(uuid4())
        new_sd = Stardust(
            id=new_id, biome_id=biome_id, planet_id=planet_id,
            galaxy_id=galaxy_id, content=content,
            region=contradiction.region or "analytical",
            gravity="PLANET", confidence=0.9,
            valid_from=now, source_agent="contradiction_resolution",
            created_at=now,
        )
        new_sd.context_tags = []
        db.add(new_sd)

        # Set valid_until on both originals
        for rid in [contradiction.record_a_id, contradiction.record_b_id]:
            record = await db.get(Stardust, rid)
            if record:
                record.valid_until = now

        # Create DERIVED_FROM relationships
        for rid in [contradiction.record_a_id, contradiction.record_b_id]:
            db.add(StardustRelationship(
                id=str(uuid4()), galaxy_id=galaxy_id,
                source_stardust_id=new_id, target_stardust_id=rid,
                relationship_type="DERIVED_FROM", confidence=1.0,
                created_by="contradiction_resolution",
            ))

        return new_id

    async def list_contradictions(
        self, galaxy_id: str, status: str = "UNRESOLVED",
        limit: int = 20, db: AsyncSession = None,
    ) -> list[dict]:
        q = select(Contradiction).where(Contradiction.galaxy_id == galaxy_id)
        if status != "ALL":
            q = q.where(Contradiction.status == status)
        q = q.limit(limit)
        result = await db.execute(q)
        rows = result.scalars().all()
        return [
            {
                "id": c.id, "record_a_id": c.record_a_id,
                "record_b_id": c.record_b_id, "conflict_type": c.conflict_type,
                "status": c.status, "region": c.region,
                "detected_at": c.detected_at.isoformat() if c.detected_at else None,
            }
            for c in rows
        ]


contradiction_service = ContradictionService()
