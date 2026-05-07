"""Determines which Planet and Biome a piece of knowledge belongs in.

Runs four strategies in priority order, returns the first match above threshold.
Strategy order: graphify_cluster → entity_routing → keyword_match → caller_suggestion → inbox_fallback
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.graphify_adapter import GraphifyAnalysis, graphify_adapter
from app.extraction.entity_extractor import EntityExtractor
from app.models.biome import Biome
from app.models.brain import EntityBacklink
from app.models.entity import Entity
from app.models.planet import Planet
from app.models.stardust import Stardust
from app.storage.embedding_router import get_embedding_provider

logger = logging.getLogger(__name__)

GRAPHIFY_MIN_CONFIDENCE = 0.75
ENTITY_MIN_CONFIDENCE = 0.70
KEYWORD_MIN_CONFIDENCE = 0.55

_extractor = EntityExtractor()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class PlanetAssignment:
    planet: Planet
    biome: Optional[Biome]
    confidence: float
    method: str
    reasoning: str
    graphify_cluster: Optional[str] = None
    override_caller: bool = False


def should_run_graphify(content: str, filename: str | None = None) -> bool:
    if len(content.split()) > 500:
        return True
    if content.count("\n") > 10 and any(k in content for k in ("def ", "function ", "class ", "import ", "const ", "func ")):
        return True
    if content.count("```") >= 2:
        return True
    if filename:
        src_exts = {".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c", ".rb", ".cs", ".kt", ".swift"}
        if Path(filename).suffix.lower() in src_exts:
            return True
    return False


class PlanetAssignmentEngine:

    async def assign(
        self, content: str, galaxy_id: str,
        caller_planet: str | None, caller_biome: str | None,
        filename: str | None, db: AsyncSession,
    ) -> PlanetAssignment:
        planets = await self._get_planets(galaxy_id, db)
        if not planets:
            inbox = await self._get_or_create_inbox(galaxy_id, db)
            return PlanetAssignment(planet=await self._planet_for_biome(inbox, db), biome=inbox, confidence=0.0,
                                    method="inbox_fallback", reasoning="No Planets exist in this Galaxy yet")

        # Strategy 1: Graphify
        if should_run_graphify(content, filename):
            try:
                analysis = await graphify_adapter.analyze(content, filename=filename)
                if analysis.graphify_ran:
                    a = await self._strategy_graphify(analysis, planets, db)
                    if a and a.confidence >= GRAPHIFY_MIN_CONFIDENCE:
                        a.override_caller = caller_planet is not None and a.planet.name != caller_planet
                        return a
            except Exception as e:
                logger.warning(f"Graphify strategy failed: {e}")

        # Strategy 2: Entity routing
        try:
            a = await self._strategy_entity(content, galaxy_id, planets, db)
            if a and a.confidence >= ENTITY_MIN_CONFIDENCE:
                a.override_caller = caller_planet is not None and a.planet.name != caller_planet
                return a
        except Exception as e:
            logger.warning(f"Entity strategy failed: {e}")

        # Strategy 3: Keyword match
        a = self._strategy_keyword(content, planets)
        if a and a.confidence >= KEYWORD_MIN_CONFIDENCE:
            a.override_caller = caller_planet is not None and a.planet.name != caller_planet
            return a

        # Strategy 4: Caller suggestion
        if caller_planet:
            planet = next((p for p in planets if p.name == caller_planet), None)
            if planet:
                biome = await self._resolve_biome(caller_biome, planet, db) if caller_biome else None
                return PlanetAssignment(planet=planet, biome=biome, confidence=0.5,
                                        method="caller_suggestion", reasoning=f"Using caller-specified Planet: {caller_planet}")

        # Strategy 5: Inbox
        inbox = await self._get_or_create_inbox(galaxy_id, db)
        return PlanetAssignment(
            planet=await self._planet_for_biome(inbox, db), biome=inbox, confidence=0.0,
            method="inbox_fallback", reasoning="Content could not be confidently assigned to any Planet. Review in Inbox.",
        )

    # ── Strategies ──

    async def _strategy_graphify(self, result: GraphifyAnalysis, planets: list[Planet], db: AsyncSession) -> PlanetAssignment | None:
        if not result.primary_cluster or result.primary_cluster == "unknown":
            return None
        cluster_text = result.primary_cluster.replace("_", " ")
        try:
            provider = get_embedding_provider()
            cluster_emb = await provider.embed(cluster_text, task_type="RETRIEVAL_QUERY")
        except Exception:
            return None

        best_planet, best_score = None, 0.0
        for p in planets:
            try:
                p_emb = await provider.embed(f"{p.name} {p.description or ''}".strip(), task_type="RETRIEVAL_DOCUMENT")
                score = _cosine_similarity(cluster_emb, p_emb)
                if score > best_score:
                    best_score, best_planet = score, p
            except Exception:
                continue

        if not best_planet or best_score < 0.6:
            return None
        conf = round(result.cluster_confidence * best_score, 3)
        biome = await self._suggest_biome_from_concepts(result.extracted_concepts, best_planet, db)
        return PlanetAssignment(
            planet=best_planet, biome=biome, confidence=conf, method="graphify_cluster",
            reasoning=f"Graphify cluster '{result.primary_cluster}' matches Planet '{best_planet.name}' "
                      f"(sim: {best_score:.2f}, cluster conf: {result.cluster_confidence:.2f})",
            graphify_cluster=result.primary_cluster,
        )

    async def _strategy_entity(self, content: str, galaxy_id: str, planets: list[Planet], db: AsyncSession) -> PlanetAssignment | None:
        extracted = _extractor.extract(content, galaxy_id)
        if not extracted:
            return None

        planet_scores: dict[str, float] = {}
        matched: list[str] = []
        for ent in extracted:
            row = (await db.execute(
                select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.name.ilike(ent.name))
                .order_by(Entity.mention_count.desc()).limit(1)
            )).scalar_one_or_none()
            if not row:
                continue
            matched.append(ent.name)
            rows = (await db.execute(
                select(Stardust.planet_id, func.count(EntityBacklink.id).label("c"))
                .join(EntityBacklink, EntityBacklink.stardust_id == Stardust.id)
                .where(EntityBacklink.entity_id == row.id)
                .group_by(Stardust.planet_id)
            )).fetchall()
            for pid, cnt in rows:
                planet_scores[pid] = planet_scores.get(pid, 0) + cnt

        if not planet_scores:
            return None
        top_id = max(planet_scores, key=planet_scores.get)
        top_planet = next((p for p in planets if p.id == top_id), None)
        if not top_planet:
            return None
        total = sum(planet_scores.values())
        conf = round(planet_scores[top_id] / total, 3)
        biome = await self._suggest_biome_from_entities(matched, top_planet, db)
        return PlanetAssignment(
            planet=top_planet, biome=biome, confidence=conf, method="entity_routing",
            reasoning=f"Entities [{', '.join(matched[:3])}] appear predominantly in Planet '{top_planet.name}' ({conf:.0%})",
        )

    @staticmethod
    def _strategy_keyword(content: str, planets: list[Planet]) -> PlanetAssignment | None:
        content_lower = content.lower()
        words = set(content_lower.split())
        best_planet, best_score, best_reason = None, 0.0, ""
        for p in planets:
            score = 0.0
            reason = ""
            # Name match: planet name (or any word in it) appears in content
            name_words = set(p.name.lower().split())
            name_hits = name_words & words
            if name_hits:
                # Full name present scores higher than partial
                name_score = 0.65 if p.name.lower() in content_lower else 0.57
                if name_score > score:
                    score, reason = name_score, f"Planet name '{p.name}' found in content"
            # Description word overlap (when available)
            if p.description:
                pw = set(p.description.lower().split())
                overlap = len(words & pw)
                if overlap > 0:
                    desc_score = min(0.65, overlap / max(len(pw), 1))
                    if desc_score > score:
                        score, reason = desc_score, f"Keyword overlap with Planet '{p.name}' description"
            if score > best_score:
                best_score, best_planet, best_reason = score, p, reason
        if not best_planet or best_score < KEYWORD_MIN_CONFIDENCE:
            return None
        return PlanetAssignment(
            planet=best_planet, biome=None, confidence=round(best_score, 3), method="keyword_match",
            reasoning=best_reason,
        )

    # ── Biome helpers ──

    async def _suggest_biome_from_concepts(self, concepts: list[str], planet: Planet, db: AsyncSession) -> Biome | None:
        if not concepts:
            return None
        scores: dict[str, int] = {}
        for c in concepts[:10]:
            rows = (await db.execute(
                select(Stardust.biome_id, func.count(EntityBacklink.id))
                .join(EntityBacklink, EntityBacklink.stardust_id == Stardust.id)
                .join(Entity, EntityBacklink.entity_id == Entity.id)
                .where(Stardust.planet_id == planet.id, Entity.name.ilike(c))
                .group_by(Stardust.biome_id)
            )).fetchall()
            for bid, cnt in rows:
                scores[bid] = scores.get(bid, 0) + cnt
        if not scores:
            return None
        return await db.get(Biome, max(scores, key=scores.get))

    async def _suggest_biome_from_entities(self, names: list[str], planet: Planet, db: AsyncSession) -> Biome | None:
        counts: Counter = Counter()
        for name in names:
            rows = (await db.execute(
                select(Stardust.biome_id)
                .join(EntityBacklink, EntityBacklink.stardust_id == Stardust.id)
                .join(Entity, EntityBacklink.entity_id == Entity.id)
                .where(Stardust.planet_id == planet.id, Entity.name.ilike(name))
            )).fetchall()
            for (bid,) in rows:
                counts[bid] += 1
        if not counts:
            return None
        return await db.get(Biome, counts.most_common(1)[0][0])

    async def _resolve_biome(self, name: str, planet: Planet, db: AsyncSession) -> Biome | None:
        return (await db.execute(select(Biome).where(Biome.planet_id == planet.id, Biome.name == name))).scalar_one_or_none()

    # ── Inbox ──

    async def _get_or_create_inbox(self, galaxy_id: str, db: AsyncSession) -> Biome:
        row = (await db.execute(
            select(Biome).join(Planet, Biome.planet_id == Planet.id)
            .where(Planet.galaxy_id == galaxy_id, Biome.is_inbox == True).limit(1)
        )).scalar_one_or_none()
        if row:
            return row

        planet = (await db.execute(
            select(Planet).where(Planet.galaxy_id == galaxy_id).order_by(Planet.created_at).limit(1)
        )).scalar_one_or_none()
        if not planet:
            planet = Planet(id=str(uuid4()), galaxy_id=galaxy_id, name="Inbox",
                            description="Temporary holding for unrouted knowledge", color="#6B7280")
            db.add(planet)
            await db.flush()

        inbox = Biome(id=str(uuid4()), planet_id=planet.id, galaxy_id=galaxy_id,
                      name="Inbox", description="Unrouted knowledge awaiting manual review.",
                      lifecycle_state="SEED", is_inbox=True)
        db.add(inbox)
        await db.flush()
        return inbox

    async def _planet_for_biome(self, biome: Biome, db: AsyncSession) -> Planet:
        return await db.get(Planet, biome.planet_id)

    async def _get_planets(self, galaxy_id: str, db: AsyncSession) -> list[Planet]:
        return list((await db.execute(select(Planet).where(Planet.galaxy_id == galaxy_id))).scalars().all())


planet_assignment_engine = PlanetAssignmentEngine()
