import re
import logging
from dataclasses import dataclass
from app.extraction.patterns import ENTITY_PATTERNS, _BLOCKLIST, is_valid_code_ref

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    name: str
    entity_type: str
    galaxy_id: str


def _deduplicate(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    seen: dict[str, ExtractedEntity] = {}
    for e in entities:
        key = e.name.lower()
        if key not in seen:
            seen[key] = e
    return list(seen.values())


class EntityExtractor:
    def extract(self, content: str, galaxy_id: str) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        for entity_type, patterns in ENTITY_PATTERNS.items():
            for pattern in patterns:
                flags = 0 if entity_type in ("tool", "organization") else re.IGNORECASE
                matches = re.findall(pattern, content, flags)
                for match in matches:
                    name = match.strip()
                    if len(name) < 3 or name in _BLOCKLIST:
                        continue
                    if entity_type == "code_ref" and not is_valid_code_ref(name):
                        continue
                    entities.append(ExtractedEntity(name=name, entity_type=entity_type, galaxy_id=galaxy_id))
        return _deduplicate(entities)
