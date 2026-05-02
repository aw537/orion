from pydantic import BaseModel
from pydantic_settings import BaseSettings
from functools import lru_cache


class RegionCacheTTLs(BaseModel):
    analytical: int = 28800    # 8 hours
    procedural: int = 86400    # 24 hours
    contextual: int = 14400    # 4 hours
    creative: int = 259200     # 72 hours
    empathetic: int = 3600     # 1 hour
    critical: int = 28800      # 8 hours
    strategic: int = 604800    # 7 days


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/orion.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    REDIS_URL: str = "redis://localhost:6379"
    CHROMA_URL: str = "http://localhost:8001"
    OLLAMA_URL: str = "http://localhost:11434"

    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "llama3"

    GOOGLE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ORION_LOCAL_TOKEN: str = ""
    ORION_AUTH_DISABLED: bool = True

    MCP_PORT: int = 8787
    API_PORT: int = 8000

    region_cache_ttls: RegionCacheTTLs = RegionCacheTTLs()

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cache_ttl(region: str, biome_override: int | None = None) -> int:
    """Get cache TTL for a region. Biome override wins if set, then config defaults."""
    if biome_override is not None:
        return biome_override
    ttls = get_settings().region_cache_ttls
    return getattr(ttls, region, 14400)


# Reference prompts for cognitive region reasoning. Not imported by backend services
# directly — available for MCP tools and external consumers via config import.
REGION_REASONING_PROMPTS = {
    "analytical": "You are reasoning in analytical mode. Draw on accumulated logical frameworks, decision records, and trade-off analyses. Prioritize precision. Ask: what is the most defensible conclusion given all evidence?",
    "procedural": "You are reasoning in procedural mode. Draw on accumulated playbooks, established patterns, and step-by-step knowledge. Prioritize proven approaches. Ask: what is the established approach validated in this context?",
    "contextual": "You are reasoning in contextual mode. Draw on accumulated observations, preferences, and general knowledge. Balance recency with established patterns. Ask: what does the accumulated context suggest?",
    "creative": "You are reasoning in creative mode. Draw on accumulated analogies, lateral connections, and pattern-breaking insights. Prioritize novel framings. Ask: what non-obvious framing reframes this productively?",
    "empathetic": "You are reasoning in empathetic mode. Draw on accumulated relational context, emotional history, and communication patterns. Prioritize actual needs. Ask: what is this person experiencing and what do they need?",
    "critical": "You are reasoning in critical mode. Draw on accumulated failure patterns, edge cases, and assumption challenges. Actively look for what breaks. Ask: where does this break down and what assumptions are wrong?",
    "strategic": "You are reasoning in strategic mode. Draw on long-horizon thinking, goal alignment, and prioritization history. Weigh short-term against long-term. Ask: does this serve the larger goal and what are second-order effects?",
}
