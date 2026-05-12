"""Signal detector — infers cognitive region from content keywords."""
import re

_KEYWORDS: dict[str, list[str]] = {
    "analytical": ["decided", "because", "tradeoff", "analysis", "evaluated",
                   "compared", "chosen", "rejected", "reason", "therefore"],
    "procedural": ["step", "first", "then", "next", "install", "run", "execute",
                   "how to", "procedure", "process", "workflow", "playbook"],
    "creative": ["analogy", "metaphor", "creative", "novel", "lateral"],
    "empathetic": ["feel", "emotion", "relationship", "team", "communication"],
    "critical": ["fail", "break", "edge case", "assumption", "risk", "vulnerability"],
    "strategic": ["goal", "long-term", "priority", "roadmap", "strategy", "quarter"],
}

_PATTERNS: dict[str, list[re.Pattern]] = {
    region: [re.compile(r"\b" + re.escape(k) + r"\b") for k in keywords]
    for region, keywords in _KEYWORDS.items()
}


def infer_region_from_content(content: str) -> str:
    content_lower = content.lower()
    scores = {
        region: sum(len(p.findall(content_lower)) for p in patterns)
        for region, patterns in _PATTERNS.items()
    }
    best_region = max(scores, key=scores.get)
    if scores[best_region] > 2:
        return best_region
    return "contextual"
