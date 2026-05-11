"""Unit tests for config — settings defaults."""
import pytest
from unittest.mock import patch
from app.config import Settings


class TestSettingsDefaults:
    @patch.dict("os.environ", {}, clear=False)
    def test_default_database_url(self):
        import os
        env_backup = os.environ.pop("DATABASE_URL", None)
        try:
            s = Settings(_env_file=None)
            assert "postgresql+asyncpg" in s.DATABASE_URL
            assert "orion" in s.DATABASE_URL
        finally:
            if env_backup is not None:
                os.environ["DATABASE_URL"] = env_backup

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


class TestDeadCodeRemoved:
    def test_region_reasoning_prompts_removed(self):
        import app.config as cfg
        assert not hasattr(cfg, "REGION_REASONING_PROMPTS"), \
            "REGION_REASONING_PROMPTS should have been removed"

    def test_ephemeral_secret_removed(self):
        import inspect, app.auth.service as svc
        src = inspect.getsource(svc)
        assert "_EPHEMERAL_SECRET" not in src

    def test_subagent_model_removed(self):
        from app import models
        assert not hasattr(models, "Subagent")
        assert not hasattr(models, "SubagentSession")
