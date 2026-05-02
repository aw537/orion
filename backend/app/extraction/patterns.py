import re

ENTITY_PATTERNS: dict[str, list[str]] = {
    "person": [
        r'\b([A-Z][a-z]{2,} [A-Z][a-z]{2,})\b',
        r'\b([A-Z][a-z]+)\s+(?:said|mentioned|noted|decided|approved)',
        r'(?:@)([a-zA-Z0-9_]{3,})',
    ],
    "organization": [
        r'\b((?:[A-Z][a-z]*\s*){1,4}(?:Inc|LLC|Corp|Ltd|Co|AI|Labs|Technologies))\b',
        r'\b(AWS|GCP|Azure|Anthropic|OpenAI|Google|Microsoft|Apple|Meta)\b',
    ],
    "tool": [
        r'\b(FastAPI|Redis|Chroma(?:DB)?|SQLite|PostgreSQL|Docker|React|Python|TypeScript|'
        r'Vite|Tailwind|Zustand|Ollama|Alembic|pytest|httpx|Pydantic|Node\.js|Kubernetes|Terraform)\b',
        r'`([a-zA-Z][a-zA-Z0-9_\-\.]{2,})`',
    ],
    "decision": [
        r'(?:decided|chose|selected|adopted|rejected|approved|denied)\s+(?:to\s+)?(.{10,80}?)(?:\.|$)',
        r'(?:decision|choice|tradeoff):\s*(.{10,80}?)(?:\.|$)',
    ],
    "code_ref": [
        # Require at least one segment to contain an underscore or be CamelCase (uppercase letter mid-word)
        r'\b([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\b',
        r'(?:file|path|route|endpoint):\s*([\/\w\.\-]{4,})',
    ],
}

# Common false positives for code_ref — abbreviations and common dot-phrases
_CODE_REF_BLOCKLIST = {"e.g", "i.e", "vs.", "etc.", "resp.json", "req.body", "a.m", "p.m"}

# Common false positives for person/decision patterns
_BLOCKLIST = {
    "the", "this", "that", "with", "from", "have", "been", "will", "would",
    "could", "should", "about", "which", "their", "there", "these", "those",
    "other", "some", "more", "also", "just", "only", "very", "much",
}

_CAMEL_OR_UNDERSCORE = re.compile(r'[a-z][A-Z]|_')


def is_valid_code_ref(match: str) -> bool:
    """Filter code_ref matches: require at least one segment with CamelCase or underscore."""
    if match.lower() in _CODE_REF_BLOCKLIST:
        return False
    return bool(_CAMEL_OR_UNDERSCORE.search(match))
