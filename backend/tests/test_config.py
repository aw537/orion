"""Unit tests for config — settings defaults."""
import pytest
from unittest.mock import patch
from app.config import Settings


class TestSettingsDefaults:
    def test_default_database_url(self):
        s = Settings()
        assert "sqlite" in s.DATABASE_URL
        assert "orion.db" in s.DATABASE_URL

    def test_default_redis_url(self):
        s = Settings()
        assert s.REDIS_URL == "redis://localhost:6379"

    def test_default_chroma_url(self):
        s = Settings()
        assert "localhost" in s.CHROMA_URL

    def test_default_ollama_url(self):
        s = Settings()
        assert "localhost" in s.OLLAMA_URL
        assert "11434" in s.OLLAMA_URL

    def test_default_embedding_provider(self):
        s = Settings()
        assert s.EMBEDDING_PROVIDER == "ollama"

    def test_default_llm_provider(self):
        s = Settings()
        assert s.LLM_PROVIDER == "ollama"

    def test_default_api_keys_empty(self):
        s = Settings()
        assert s.GOOGLE_API_KEY == ""
        assert s.ANTHROPIC_API_KEY == ""
        assert s.OPENAI_API_KEY == ""

    def test_default_token_empty(self):
        s = Settings()
        assert s.ORION_LOCAL_TOKEN == ""

    def test_default_ports(self):
        s = Settings()
        assert s.MCP_PORT == 8787
        assert s.API_PORT == 8000

    def test_env_override(self):
        with patch.dict("os.environ", {"EMBEDDING_PROVIDER": "google", "GOOGLE_API_KEY": "test-key"}):
            s = Settings()
            assert s.EMBEDDING_PROVIDER == "google"
            assert s.GOOGLE_API_KEY == "test-key"
