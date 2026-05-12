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
    DATABASE_URL: str = "postgresql+asyncpg://orion:orion_dev@localhost:5432/orion"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: str = ""
    # TLS: use rediss:// scheme in REDIS_URL for TLS-encrypted connections.
    # DATABASE_URL: use postgresql+asyncpg://...?ssl=require for TLS to PostgreSQL.
    # Both are operator responsibilities; the app passes URLs through as-is.
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
    ORION_OWNER_RECOVERY_TOKEN: str = ""  # SHA-256 hex digest of the token; allows re-registering an owner

    MCP_PORT: int = 8787
    API_PORT: int = 8000

    region_cache_ttls: RegionCacheTTLs = RegionCacheTTLs()

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    """Invalidate the lru_cache on get_settings().

    Note: module-level consumers that captured the result at import time
    (e.g. database.py's engine) are unaffected — intended for test fixtures
    that import modules fresh.
    """
    get_settings.cache_clear()


def get_cache_ttl(region: str, biome_override: int | None = None) -> int:
    """Get cache TTL for a region. Biome override wins if set, then config defaults."""
    if biome_override is not None:
        return biome_override
    ttls = get_settings().region_cache_ttls
    return getattr(ttls, region, 14400)
