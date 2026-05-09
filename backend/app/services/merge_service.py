"""Merge Service — Galaxy Merge orchestration: Sun negotiation, entity reconciliation, Gravity Bridge creation."""
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    Galaxy, SunSection, Planet, Entity, Stardust, Biome, GravityBridge,
    EntityRelationship, EntityBacklink, Contradiction, User,
)
from app.models.merge import MergeProposal, EntityMergeMapping
from app.services.sun_service import SUN_SECTIONS, _parse_content

logger = logging.getLogger(__name__)


class MergeService:

    # ── Proposal lifecycle ──────────────────────────────────────────

    async def propose_merge(
        self, source_galaxy_id: str, target_galaxy_id: str, proposed_by: str, db: AsyncSession,
    ) -> MergeProposal:
        if source_galaxy_id == target_galaxy_id:
            raise ValueError("Cannot merge a Galaxy with itself")
        # Verify both galaxies exist
        source = await db.get(Galaxy, source_galaxy_id)
        target = await db.get(Galaxy, target_galaxy_id)
        if not source or not target:
            raise ValueError("One or both Galaxies not found")
        # Check no active proposal exists between these two
        existing = (await db.execute(
            select(MergeProposal).where(
                MergeProposal.source_galaxy_id == source_galaxy_id,
                MergeProposal.target_galaxy_id == target_galaxy_id,
                MergeProposal.status.notin_(["complete", "rejected"]),
            )
        )).scalar_one_or_none()
        if existing:
            raise ValueError("An active merge proposal already exists between these Galaxies")

        proposal = MergeProposal(
            id=str(uuid4()), source_galaxy_id=source_galaxy_id,
            target_galaxy_id=target_galaxy_id, proposed_by=proposed_by,
        )
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def accept_merge(self, proposal_id: str, accepted_by: str, db: AsyncSession) -> MergeProposal:
        proposal = await self._get_proposal(proposal_id, db)
        if proposal.status != "proposed":
            raise ValueError(f"Proposal is '{proposal.status}', not 'proposed'")
        # Accepting user must belong to the target Galaxy (they are accepting on its behalf)
        accepting_user = await db.get(User, accepted_by)
        if not accepting_user or accepting_user.galaxy_id != proposal.target_galaxy_id:
            raise ValueError("Only a member of the target Galaxy can accept a merge proposal")
        proposal.status = "accepted"
        proposal.accepted_by = accepted_by
        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def reject_merge(self, proposal_id: str, rejected_by: str, reason: str, db: AsyncSession) -> MergeProposal:
        proposal = await self._get_proposal(proposal_id, db)
        if proposal.status != "proposed":
            raise ValueError(f"Proposal is '{proposal.status}', not 'proposed'")
        proposal.status = "rejected"
        proposal.rejection_reason = reason
        await db.commit()
        await db.refresh(proposal)
        return proposal

    # ── Sun negotiation ─────────────────────────────────────────────

    async def negotiate_sun(self, proposal_id: str, db: AsyncSession) -> dict:
        """Merge two Suns section-by-section. Source Sun merges into target Sun."""
        proposal = await self._get_proposal(proposal_id, db)
        if proposal.status not in ("accepted", "sun_negotiation"):
            raise ValueError(f"Proposal must be 'accepted' to negotiate Sun, got '{proposal.status}'")
        proposal.status = "sun_negotiation"

        source_sections = await self._load_sun(proposal.source_galaxy_id, db)
        target_sections = await self._load_sun(proposal.target_galaxy_id, db)
        merged = {}

        for key in SUN_SECTIONS:
            source = source_sections.get(key, {})
            target = target_sections.get(key, {})
            merged[key] = self._merge_sun_section(key, source, target)

        proposal.merged_sun = json.dumps(merged)
        await db.commit()
        return merged

    def _merge_sun_section(self, key: str, source: dict, target: dict) -> dict:
        """Merge strategy per section type. Target wins on scalar conflicts."""
        if key == "identity":
            # Target identity wins; append source context
            result = dict(target)
            if source.get("galaxy_purpose") and target.get("galaxy_purpose"):
                result["galaxy_purpose"] = f"{target['galaxy_purpose']}; merged with: {source['galaxy_purpose']}"
            return result

        if key == "values":
            result = dict(target)
            # Merge principles lists (deduplicate)
            src_principles = set(source.get("principles", []))
            tgt_principles = set(target.get("principles", []))
            result["principles"] = sorted(src_principles | tgt_principles)
            return result

        if key == "agent_protocol":
            result = dict(target)
            # Merge rule lists
            for rule_key in ("write_rules", "read_rules"):
                src_rules = source.get(rule_key, [])
                tgt_rules = target.get(rule_key, [])
                result[rule_key] = list(dict.fromkeys(tgt_rules + src_rules))  # dedup, target first
            return result

        if key == "planet_registry":
            # Combine planet lists
            src_planets = source.get("planets", [])
            tgt_planets = target.get("planets", [])
            return {"planets": tgt_planets + src_planets}

        if key == "working_context":
            # Target working context wins; merge hot_biomes and recent_decisions
            result = dict(target)
            result["hot_biomes"] = list(dict.fromkeys(
                target.get("hot_biomes", []) + source.get("hot_biomes", [])
            ))
            result["recent_decisions"] = (
                target.get("recent_decisions", []) + source.get("recent_decisions", [])
            )[:20]  # cap at 20
            return result

        if key == "evolution_log":
            # Interleave entries by timestamp
            src_entries = source.get("entries", [])
            tgt_entries = target.get("entries", [])
            all_entries = sorted(
                src_entries + tgt_entries,
                key=lambda e: e.get("timestamp", ""),
            )
            return {"entries": all_entries}

        # Fallback: target wins
        return target

    async def preview_merged_sun(self, proposal_id: str, db: AsyncSession) -> dict:
        """Preview what the merged Sun would look like without committing."""
        proposal = await self._get_proposal(proposal_id, db)
        if proposal.merged_sun:
            return json.loads(proposal.merged_sun)
        source_sections = await self._load_sun(proposal.source_galaxy_id, db)
        target_sections = await self._load_sun(proposal.target_galaxy_id, db)
        merged = {}
        for key in SUN_SECTIONS:
            merged[key] = self._merge_sun_section(
                key, source_sections.get(key, {}), target_sections.get(key, {}),
            )
        return merged

    # ── Entity reconciliation ───────────────────────────────────────

    async def reconcile_entities(self, proposal_id: str, db: AsyncSession) -> list[dict]:
        """Find duplicate entities across the two Galaxies and create merge mappings."""
        proposal = await self._get_proposal(proposal_id, db)
        if proposal.status not in ("sun_negotiation", "entity_reconciliation"):
            raise ValueError(f"Sun negotiation must complete first, got '{proposal.status}'")
        proposal.status = "entity_reconciliation"

        source_entities = (await db.execute(
            select(Entity).where(Entity.galaxy_id == proposal.source_galaxy_id)
        )).scalars().all()
        target_entities = (await db.execute(
            select(Entity).where(Entity.galaxy_id == proposal.target_galaxy_id)
        )).scalars().all()

        # Build lookup by normalized name + type
        target_by_name: dict[str, Entity] = {}
        for e in target_entities:
            key = f"{e.name.lower().strip()}::{e.entity_type.lower()}"
            target_by_name[key] = e

        mappings = []
        for src in source_entities:
            key = f"{src.name.lower().strip()}::{src.entity_type.lower()}"
            tgt = target_by_name.get(key)
            if tgt:
                mapping = EntityMergeMapping(
                    id=str(uuid4()), proposal_id=proposal_id,
                    source_entity_id=src.id, target_entity_id=tgt.id,
                    match_type="same_type_and_name", confidence=1.0,
                )
                db.add(mapping)
                mappings.append({
                    "source": {"id": src.id, "name": src.name, "type": src.entity_type},
                    "target": {"id": tgt.id, "name": tgt.name, "type": tgt.entity_type},
                    "match_type": "same_type_and_name", "confidence": 1.0,
                })

        proposal.entity_mappings_count = len(mappings)
        proposal.reconciliation_done = True
        await db.commit()
        return mappings

    async def get_entity_mappings(self, proposal_id: str, db: AsyncSession) -> list[dict]:
        """Return existing entity merge mappings for a proposal."""
        rows = (await db.execute(
            select(EntityMergeMapping).where(EntityMergeMapping.proposal_id == proposal_id)
        )).scalars().all()
        result = []
        for m in rows:
            src = await db.get(Entity, m.source_entity_id)
            tgt = await db.get(Entity, m.target_entity_id)
            result.append({
                "id": m.id,
                "source": {"id": src.id, "name": src.name, "type": src.entity_type} if src else None,
                "target": {"id": tgt.id, "name": tgt.name, "type": tgt.entity_type} if tgt else None,
                "match_type": m.match_type, "confidence": m.confidence, "merged": m.merged,
            })
        return result

    # ── Gravity Bridge creation ─────────────────────────────────────

    async def create_bridges(self, proposal_id: str, db: AsyncSession) -> list[dict]:
        """Create Gravity Bridges between semantically related Planet pairs across the two Galaxies.

        Only bridges planets whose normalized names match — avoids creating N×M bridges
        between unrelated planets.
        """
        proposal = await self._get_proposal(proposal_id, db)
        if proposal.status not in ("entity_reconciliation", "bridging"):
            raise ValueError(f"Entity reconciliation must complete first, got '{proposal.status}'")
        proposal.status = "bridging"

        source_planets = (await db.execute(
            select(Planet).where(Planet.galaxy_id == proposal.source_galaxy_id)
        )).scalars().all()
        target_planets = (await db.execute(
            select(Planet).where(Planet.galaxy_id == proposal.target_galaxy_id)
        )).scalars().all()

        # Index target planets by normalized name for O(n) matching
        target_by_name: dict[str, Planet] = {p.name.lower().strip(): p for p in target_planets}

        bridges = []
        for sp in source_planets:
            tp = target_by_name.get(sp.name.lower().strip())
            if tp is None:
                continue
            bridge = GravityBridge(
                id=str(uuid4()), galaxy_id=proposal.target_galaxy_id,
                source_planet_id=sp.id, target_planet_id=tp.id,
                bridge_type="MERGE", target_galaxy_id=proposal.source_galaxy_id,
                opened_by=proposal.proposed_by,
            )
            db.add(bridge)
            bridges.append({
                "id": bridge.id, "source_planet": sp.name,
                "target_planet": tp.name, "bridge_type": "MERGE",
            })

        logger.info(
            f"Merge {proposal_id}: created {len(bridges)} bridges from "
            f"{len(source_planets)} source × {len(target_planets)} target planets "
            f"(name-matched only)"
        )
        proposal.bridges_created = len(bridges)
        proposal.bridging_done = True
        await db.commit()
        return bridges

    # ── Execute merge ───────────────────────────────────────────────

    async def execute_merge(self, proposal_id: str, executing_user_id: str, db: AsyncSession) -> dict:
        """Execute the full merge: apply Sun, merge entities, migrate data from source to target Galaxy."""
        proposal = await self._get_proposal(proposal_id, db)
        if proposal.status not in ("bridging", "accepted"):
            raise ValueError(f"Cannot execute merge in status '{proposal.status}'")

        # Only a member of the target Galaxy may execute the merge
        executing_user = await db.get(User, executing_user_id)
        if not executing_user or executing_user.galaxy_id != proposal.target_galaxy_id:
            raise ValueError("Only a member of the target Galaxy can execute a merge")

        target_gid = proposal.target_galaxy_id
        source_gid = proposal.source_galaxy_id

        # 1. Run all phases if not already done
        if not proposal.merged_sun:
            await self.negotiate_sun(proposal_id, db)
            proposal = await self._get_proposal(proposal_id, db)

        if not proposal.reconciliation_done:
            await self.reconcile_entities(proposal_id, db)
            proposal = await self._get_proposal(proposal_id, db)

        if not proposal.bridging_done:
            await self.create_bridges(proposal_id, db)
            proposal = await self._get_proposal(proposal_id, db)

        # 2. Apply merged Sun to target Galaxy
        if proposal.merged_sun:
            merged_sun = json.loads(proposal.merged_sun)
            for key, content in merged_sun.items():
                if key == "evolution_log":
                    continue  # handled separately
                row = (await db.execute(
                    select(SunSection).where(
                        SunSection.galaxy_id == target_gid, SunSection.section_key == key,
                    )
                )).scalar_one_or_none()
                if row:
                    row.content = content
                    row.version += 1
                    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # 3. Merge matched entities (combine mention counts, keep target)
        mappings = (await db.execute(
            select(EntityMergeMapping).where(
                EntityMergeMapping.proposal_id == proposal_id, EntityMergeMapping.merged == False,
            )
        )).scalars().all()
        entities_merged = 0
        for m in mappings:
            src = await db.get(Entity, m.source_entity_id)
            tgt = await db.get(Entity, m.target_entity_id)
            if src and tgt:
                tgt.mention_count += src.mention_count
                tgt.tier = max(tgt.tier, src.tier)
                if src.last_seen and tgt.last_seen and src.last_seen > tgt.last_seen:
                    tgt.last_seen = src.last_seen
                elif src.last_seen and not tgt.last_seen:
                    tgt.last_seen = src.last_seen
                # Repoint source entity's backlinks to target
                await db.execute(
                    update(EntityBacklink)
                    .where(EntityBacklink.entity_id == src.id)
                    .values(entity_id=tgt.id)
                )
                # Repoint source entity's relationships to target
                await db.execute(
                    update(EntityRelationship)
                    .where(EntityRelationship.source_entity_id == src.id)
                    .values(source_entity_id=tgt.id)
                )
                await db.execute(
                    update(EntityRelationship)
                    .where(EntityRelationship.target_entity_id == src.id)
                    .values(target_entity_id=tgt.id)
                )
                m.merged = True
                entities_merged += 1

        # 4. Migrate remaining source data to target Galaxy — wrapped in a savepoint
        # so a mid-merge failure rolls back all bulk moves atomically.
        try:
            async with await db.begin_nested():
                # Planets
                await db.execute(
                    update(Planet).where(Planet.galaxy_id == source_gid).values(galaxy_id=target_gid)
                )
                # Biomes
                await db.execute(
                    update(Biome).where(Biome.galaxy_id == source_gid).values(galaxy_id=target_gid)
                )
                # Stardust
                await db.execute(
                    update(Stardust).where(Stardust.galaxy_id == source_gid).values(galaxy_id=target_gid)
                )
                # Unmatched entities
                await db.execute(
                    update(Entity).where(Entity.galaxy_id == source_gid).values(galaxy_id=target_gid)
                )
                # Entity relationships
                await db.execute(
                    update(EntityRelationship).where(EntityRelationship.galaxy_id == source_gid).values(galaxy_id=target_gid)
                )
                # Contradictions
                await db.execute(
                    update(Contradiction).where(Contradiction.galaxy_id == source_gid).values(galaxy_id=target_gid)
                )
                # Users — log before migrating so there's a clear audit trail
                migrating_users = (await db.execute(
                    select(User.id, User.email, User.role).where(User.galaxy_id == source_gid)
                )).all()
                if migrating_users:
                    logger.warning(
                        f"Merge {proposal_id}: migrating {len(migrating_users)} user(s) from "
                        f"Galaxy {source_gid} to {target_gid} without consent. "
                        f"Users: {[(u.email, u.role) for u in migrating_users]}"
                    )
                await db.execute(
                    update(User).where(User.galaxy_id == source_gid).values(galaxy_id=target_gid)
                )
                # Gravity bridges (update source galaxy bridges to target)
                await db.execute(
                    update(GravityBridge).where(GravityBridge.galaxy_id == source_gid).values(galaxy_id=target_gid)
                )
                # Clear target_galaxy_id on merge bridges (now all intra-galaxy)
                await db.execute(
                    update(GravityBridge)
                    .where(GravityBridge.target_galaxy_id == source_gid)
                    .values(target_galaxy_id=None)
                )
        except Exception as e:
            logger.error(f"Merge {proposal_id}: migration failed mid-way, rolling back: {e}")
            raise ValueError(f"Merge migration failed and was rolled back: {e}") from e

        # 5. Update target Galaxy totals
        target = await db.get(Galaxy, target_gid)
        source = await db.get(Galaxy, source_gid)
        if target and source:
            target.total_nodes += source.total_nodes

        # 6. Mark complete
        proposal.status = "complete"
        proposal.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

        return {
            "status": "complete",
            "target_galaxy_id": target_gid,
            "source_galaxy_id": source_gid,
            "entities_merged": entities_merged,
            "bridges_created": proposal.bridges_created,
            "sun_negotiated": proposal.merged_sun is not None,
        }

    # ── Helpers ─────────────────────────────────────────────────────

    async def _get_proposal(self, proposal_id: str, db: AsyncSession) -> MergeProposal:
        proposal = await db.get(MergeProposal, proposal_id)
        if not proposal:
            raise ValueError(f"Merge proposal '{proposal_id}' not found")
        return proposal

    async def _load_sun(self, galaxy_id: str, db: AsyncSession) -> dict:
        rows = (await db.execute(
            select(SunSection).where(SunSection.galaxy_id == galaxy_id)
        )).scalars().all()
        return {r.section_key: _parse_content(r.content) for r in rows}


merge_service = MergeService()
