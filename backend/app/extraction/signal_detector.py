"""Signal detector — infers cognitive region from content keywords."""


def infer_region_from_content(content: str) -> str:
    analytical_keywords = ["decided", "because", "tradeoff", "analysis", "evaluated",
                           "compared", "chosen", "rejected", "reason", "therefore"]
    procedural_keywords = ["step", "first", "then", "next", "install", "run", "execute",
                           "how to", "procedure", "process", "workflow", "playbook"]
    creative_keywords = ["analogy", "metaphor", "creative", "novel", "lateral"]
    empathetic_keywords = ["feel", "emotion", "relationship", "team", "communication"]
    critical_keywords = ["fail", "break", "edge case", "assumption", "risk", "vulnerability"]
    strategic_keywords = ["goal", "long-term", "priority", "roadmap", "strategy", "quarter"]

    content_lower = content.lower()

    scores = {
        "analytical": sum(content_lower.count(k) for k in analytical_keywords),
        "procedural": sum(content_lower.count(k) for k in procedural_keywords),
        "creative": sum(content_lower.count(k) for k in creative_keywords),
        "empathetic": sum(content_lower.count(k) for k in empathetic_keywords),
        "critical": sum(content_lower.count(k) for k in critical_keywords),
        "strategic": sum(content_lower.count(k) for k in strategic_keywords),
    }

    best_region = max(scores, key=scores.get)
    if scores[best_region] > 2:
        return best_region
    return "contextual"
