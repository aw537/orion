"""Relationship Extractor — zero LLM calls, pure deterministic pattern matching."""
import re
import logging
from dataclasses import dataclass
from app.models.entity import Entity

logger = logging.getLogger(__name__)

RELATIONSHIP_PATTERNS = {
    "USES": [
        r"(?P<source>{E}) (?:uses?|utilizes?|leverages?) (?P<target>{E})",
        r"(?P<source>{E}) (?:is built|built) (?:on|with|using) (?P<target>{E})",
    ],
    "REPLACES": [
        r"(?P<source>{E}) (?:replaces?|supersedes?) (?P<target>{E})",
        r"(?:switched?|migrated?) from (?P<target>{E}) to (?P<source>{E})",
        r"(?P<source>{E}) (?:instead of|over|rather than) (?P<target>{E})",
    ],
    "EVALUATES": [
        r"(?:evaluated?|compared?) (?P<source>{E}) (?:against|vs\.?) (?P<target>{E})",
        r"(?P<source>{E}) (?:was chosen|selected) over (?P<target>{E})",
    ],
    "DEPENDS_ON": [
        r"(?P<source>{E}) (?:requires?|needs?|depends? on) (?P<target>{E})",
        r"(?P<source>{E}) (?:cannot work|fails?) without (?P<target>{E})",
    ],
    "WORKS_WITH": [
        r"(?P<source>{E}) (?:works? with|pairs? with) (?P<target>{E})",
        r"(?P<source>{E}) and (?P<target>{E}) (?:work|function) together",
    ],
    "PART_OF": [
        r"(?P<source>{E}) (?:is part of|belongs to) (?P<target>{E})",
        r"(?P<target>{E}) (?:contains?|includes?) (?P<source>{E})",
    ],
    "INFORMS": [
        r"(?P<source>{E}) (?:informs?|guides?|influences?) (?P<target>{E})",
        r"(?P<source>{E}) (?:led to|resulted in) (?P<target>{E})",
    ],
}


@dataclass
class ExtractedRelationship:
    source_entity: Entity
    target_entity: Entity
    relationship_type: str
    confidence: float
    matched_text: str


class RelationshipExtractor:

    def extract(self, content: str, entities: list[Entity]) -> list[ExtractedRelationship]:
        if len(entities) < 2:
            return []
        entity_map = {e.name.lower(): e for e in entities}
        alt = "|".join(re.escape(n) for n in entity_map)
        if not alt:
            return []

        # Compile all patterns once for this entity batch
        compiled: list[tuple[str, re.Pattern]] = []
        for rel_type, templates in RELATIONSHIP_PATTERNS.items():
            for tmpl in templates:
                try:
                    compiled.append((rel_type, re.compile(tmpl.replace("{E}", f"(?:{alt})"), re.IGNORECASE)))
                except re.error:
                    continue

        results = []
        for rel_type, pattern in compiled:
            for m in pattern.finditer(content):
                src = m.group("source").lower()
                tgt = m.group("target").lower()
                if src in entity_map and tgt in entity_map and src != tgt:
                    results.append(ExtractedRelationship(
                        source_entity=entity_map[src],
                        target_entity=entity_map[tgt],
                        relationship_type=rel_type,
                        confidence=0.75,
                        matched_text=m.group(0),
                    ))

        return self._deduplicate(results)

    def _deduplicate(self, results: list[ExtractedRelationship]) -> list[ExtractedRelationship]:
        seen, out = set(), []
        for r in results:
            k = (r.source_entity.id, r.target_entity.id, r.relationship_type)
            if k not in seen:
                seen.add(k)
                out.append(r)
        return out


relationship_extractor = RelationshipExtractor()
