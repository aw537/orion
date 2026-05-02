"""Graph Service — knowledge graph operations: relationships, paths, neighborhoods."""
import json
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.brain import EntityRelationship, EntityBacklink, GraphPathCache
from app.models.entity import Entity
from app.models.stardust import Stardust

logger = logging.getLogger(__name__)


class GraphService:

    async def upsert_relationship(
        self, source_id: str, target_id: str, rel_type: str,
        confidence: float, stardust_id: str, galaxy_id: str, db: AsyncSession,
    ) -> EntityRelationship:
        result = await db.execute(
            select(EntityRelationship)
            .where(
                EntityRelationship.source_entity_id == source_id,
                EntityRelationship.target_entity_id == target_id,
                EntityRelationship.relationship_type == rel_type,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.strength += 1
            existing.confidence = existing.confidence * 0.7 + confidence * 0.3
            ids = existing.source_stardust_ids if isinstance(existing.source_stardust_ids, list) else json.loads(existing.source_stardust_ids or "[]")
            if stardust_id not in ids:
                ids.append(stardust_id)
            existing.source_stardust_ids = ids
            await db.flush()
            return existing

        rel = EntityRelationship(
            id=str(uuid4()), galaxy_id=galaxy_id,
            source_entity_id=source_id, target_entity_id=target_id,
            relationship_type=rel_type, confidence=confidence,
            source_stardust_ids=[stardust_id], strength=1,
        )
        db.add(rel)
        await db.flush()
        return rel

    async def update_backlinks(
        self, stardust: Stardust, entities: list[Entity], db: AsyncSession,
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for entity in entities:
            result = await db.execute(
                select(EntityBacklink)
                .where(EntityBacklink.entity_id == entity.id, EntityBacklink.stardust_id == stardust.id)
            )
            backlink = result.scalar_one_or_none()
            if backlink:
                backlink.mention_count += 1
                backlink.last_mention = now
            else:
                db.add(EntityBacklink(
                    id=str(uuid4()), entity_id=entity.id,
                    stardust_id=stardust.id, mention_type="explicit",
                    mention_count=1, first_mention=now, last_mention=now,
                ))
        await db.flush()

    async def find_path(
        self, source_entity_id: str, target_entity_id: str,
        galaxy_id: str, db: AsyncSession,
    ) -> dict | None:
        """BFS shortest path. Max depth 6."""
        if source_entity_id == target_entity_id:
            return {"nodes": [source_entity_id], "relationship_types": [], "length": 0}

        # Check cache
        cached = await self._get_cached_path(source_entity_id, target_entity_id, galaxy_id, db)
        if cached:
            return cached

        visited = {source_entity_id}
        queue = deque([([source_entity_id], [])])

        while queue:
            path, rels = queue.popleft()
            current = path[-1]
            if len(path) >= 7:
                continue
            neighbors = await self._get_neighbors(current, galaxy_id, db)
            for neighbor_id, rel_type in neighbors:
                if neighbor_id == target_entity_id:
                    result = {"nodes": path + [neighbor_id], "relationship_types": rels + [rel_type], "length": len(path)}
                    await self._cache_path(result, galaxy_id, source_entity_id, target_entity_id, db)
                    return result
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((path + [neighbor_id], rels + [rel_type]))
        return None

    async def get_entity_neighborhood(
        self, entity_id: str, depth: int, galaxy_id: str, db: AsyncSession,
    ) -> dict:
        nodes = {entity_id}
        edges = []
        frontier = {entity_id}
        for _ in range(depth):
            next_frontier = set()
            for node_id in frontier:
                neighbors = await self._get_neighbors_with_confidence(node_id, galaxy_id, db)
                for neighbor_id, rel_type, confidence in neighbors:
                    edges.append({"source": node_id, "target": neighbor_id, "type": rel_type, "confidence": confidence})
                    if neighbor_id not in nodes:
                        nodes.add(neighbor_id)
                        next_frontier.add(neighbor_id)
            frontier = next_frontier

        # Load entity details
        entity_records = []
        for nid in nodes:
            e = await db.get(Entity, nid)
            if e:
                entity_records.append({"id": e.id, "name": e.name, "type": e.entity_type, "tier": e.tier, "mentions": e.mention_count, "planet_id": e.planet_id})

        return {"center_entity_id": entity_id, "entities": entity_records, "edges": edges, "depth": depth}

    async def find_unlinked_mentions(self, galaxy_id: str, db: AsyncSession) -> list[dict]:
        """Find stardust that mentions an entity by name but has no formal backlink."""
        entities = (await db.execute(
            select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.tier >= 2).limit(50)
        )).scalars().all()

        suggestions = []
        for entity in entities:
            # Find stardust containing entity name but not linked
            linked_ids = (await db.execute(
                select(EntityBacklink.stardust_id).where(EntityBacklink.entity_id == entity.id)
            )).scalars().all()
            linked_set = set(linked_ids)

            # Simple text search for entity name
            matches = (await db.execute(
                select(Stardust.id, Stardust.content)
                .where(Stardust.galaxy_id == galaxy_id, Stardust.content.contains(entity.name))
                .limit(20)
            )).all()

            unlinked = [m for m in matches if m.id not in linked_set]
            if unlinked:
                suggestions.append({
                    "entity_id": entity.id, "entity_name": entity.name,
                    "unlinked_count": len(unlinked),
                    "stardust_ids": [m.id for m in unlinked[:10]],
                    "sample": unlinked[0].content[:120] if unlinked else "",
                })

        return sorted(suggestions, key=lambda x: x["unlinked_count"], reverse=True)

    async def get_hub_entities(self, galaxy_id: str, limit: int, db: AsyncSession) -> list[dict]:
        result = await db.execute(text("""
            SELECT e.id, e.name, e.entity_type, e.tier,
                COUNT(DISTINCT er.id) as degree
            FROM entities e
            LEFT JOIN entity_relationships er
                ON e.id = er.source_entity_id OR e.id = er.target_entity_id
            WHERE e.galaxy_id = :gid
            GROUP BY e.id
            ORDER BY degree DESC
            LIMIT :limit
        """), {"gid": galaxy_id, "limit": limit})
        return [dict(row._mapping) for row in result]

    async def link_entity_stardust(self, entity_id: str, stardust_id: str, db: AsyncSession) -> EntityBacklink:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        backlink = EntityBacklink(
            id=str(uuid4()), entity_id=entity_id, stardust_id=stardust_id,
            mention_type="explicit", mention_count=1, first_mention=now, last_mention=now,
        )
        db.add(backlink)
        await db.flush()
        return backlink

    async def link_all_unlinked(self, entity_id: str, galaxy_id: str, db: AsyncSession) -> int:
        """Link all unlinked mentions for an entity."""
        entity = await db.get(Entity, entity_id)
        if not entity:
            return 0

        linked_ids = set((await db.execute(
            select(EntityBacklink.stardust_id).where(EntityBacklink.entity_id == entity_id)
        )).scalars().all())

        matches = (await db.execute(
            select(Stardust.id)
            .where(Stardust.galaxy_id == galaxy_id, Stardust.content.contains(entity.name))
        )).scalars().all()

        count = 0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for sid in matches:
            if sid not in linked_ids:
                db.add(EntityBacklink(
                    id=str(uuid4()), entity_id=entity_id, stardust_id=sid,
                    mention_type="explicit", mention_count=1, first_mention=now, last_mention=now,
                ))
                count += 1
        await db.flush()
        return count

    async def infer_transitive_relationships(
        self, entity_id: str, galaxy_id: str, db: AsyncSession,
    ) -> list[EntityRelationship]:
        """Infer transitive relationships with type-aware inference.

        Rules:
        - A USES B + B DEPENDS_ON C → A INDIRECTLY_DEPENDS_ON C
        - A USES B + B USES C → A INDIRECTLY_USES C
        - Otherwise → A INDIRECTLY_RELATED C
        """
        # Get direct relationships
        direct = (await db.execute(
            select(EntityRelationship)
            .where(EntityRelationship.source_entity_id == entity_id, EntityRelationship.galaxy_id == galaxy_id)
        )).scalars().all()

        inferred = []
        for rel in direct:
            # Get second-hop relationships
            second_hop = (await db.execute(
                select(EntityRelationship)
                .where(EntityRelationship.source_entity_id == rel.target_entity_id, EntityRelationship.galaxy_id == galaxy_id)
            )).scalars().all()

            for rel2 in second_hop:
                if rel2.target_entity_id == entity_id:
                    continue  # Skip cycles
                # Check if direct relationship already exists
                existing = (await db.execute(
                    select(EntityRelationship)
                    .where(
                        EntityRelationship.source_entity_id == entity_id,
                        EntityRelationship.target_entity_id == rel2.target_entity_id,
                        EntityRelationship.galaxy_id == galaxy_id,
                    )
                )).scalar_one_or_none()
                if not existing:
                    composed_confidence = rel.confidence * rel2.confidence * 0.5
                    if composed_confidence > 0.4:
                        inferred_type = self._infer_transitive_type(rel.relationship_type, rel2.relationship_type)
                        new_rel = EntityRelationship(
                            id=str(uuid4()), galaxy_id=galaxy_id,
                            source_entity_id=entity_id, target_entity_id=rel2.target_entity_id,
                            relationship_type=inferred_type,
                            confidence=composed_confidence, strength=1, inferred=1,
                            source_stardust_ids=[],
                        )
                        db.add(new_rel)
                        inferred.append(new_rel)
        await db.flush()
        return inferred

    @staticmethod
    def _infer_transitive_type(first: str, second: str) -> str:
        """Determine inferred relationship type from the two source types."""
        if "DEPENDS_ON" in second:
            return "INDIRECTLY_DEPENDS_ON"
        if first == "USES" and second == "USES":
            return "INDIRECTLY_USES"
        return "INDIRECTLY_RELATED"

    # ── Private helpers ─────────────────────────────────────────────────

    async def _get_neighbors(self, entity_id: str, galaxy_id: str, db: AsyncSession) -> list[tuple[str, str]]:
        result = await db.execute(
            select(EntityRelationship.target_entity_id, EntityRelationship.relationship_type)
            .where(EntityRelationship.source_entity_id == entity_id, EntityRelationship.galaxy_id == galaxy_id)
        )
        outgoing = [(r.target_entity_id, r.relationship_type) for r in result]
        result2 = await db.execute(
            select(EntityRelationship.source_entity_id, EntityRelationship.relationship_type)
            .where(EntityRelationship.target_entity_id == entity_id, EntityRelationship.galaxy_id == galaxy_id)
        )
        incoming = [(r.source_entity_id, r.relationship_type) for r in result2]
        return outgoing + incoming

    async def _get_neighbors_with_confidence(self, entity_id: str, galaxy_id: str, db: AsyncSession) -> list[tuple[str, str, float]]:
        result = await db.execute(
            select(EntityRelationship.target_entity_id, EntityRelationship.relationship_type, EntityRelationship.confidence)
            .where(EntityRelationship.source_entity_id == entity_id, EntityRelationship.galaxy_id == galaxy_id)
        )
        outgoing = [(r.target_entity_id, r.relationship_type, r.confidence) for r in result]
        result2 = await db.execute(
            select(EntityRelationship.source_entity_id, EntityRelationship.relationship_type, EntityRelationship.confidence)
            .where(EntityRelationship.target_entity_id == entity_id, EntityRelationship.galaxy_id == galaxy_id)
        )
        incoming = [(r.source_entity_id, r.relationship_type, r.confidence) for r in result2]
        return outgoing + incoming

    async def _get_cached_path(self, source_id: str, target_id: str, galaxy_id: str, db: AsyncSession) -> dict | None:
        result = await db.execute(
            select(GraphPathCache)
            .where(
                GraphPathCache.source_node_id == source_id,
                GraphPathCache.target_node_id == target_id,
                GraphPathCache.galaxy_id == galaxy_id,
                GraphPathCache.expires_at > datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        cached = result.scalar_one_or_none()
        if cached:
            p = cached.path if isinstance(cached.path, list) else json.loads(cached.path)
            pt = cached.path_types if isinstance(cached.path_types, list) else json.loads(cached.path_types)
            return {"nodes": p, "relationship_types": pt, "length": cached.path_length}
        return None

    async def _cache_path(self, path: dict, galaxy_id: str, source_id: str, target_id: str, db: AsyncSession) -> None:
        db.add(GraphPathCache(
            id=str(uuid4()), galaxy_id=galaxy_id,
            source_node_id=source_id, source_node_type="entity",
            target_node_id=target_id, target_node_type="entity",
            path=path["nodes"], path_length=path["length"],
            path_types=path["relationship_types"],
            computed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        ))
        await db.flush()


graph_service = GraphService()
