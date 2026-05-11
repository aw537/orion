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


class TestStardustContextTagsNoDoubleparse:
    def test_stardust_to_response_uses_hybrid_property_directly(self):
        """_stardust_to_response must not re-parse tags; hybrid_property already returns list."""
        import ast, inspect
        from app.api import stardust as api_mod
        src = inspect.getsource(api_mod._stardust_to_response)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
                assert name != "loads", "json.loads() found inside _stardust_to_response — remove it"


class TestSettingsCache:
    def test_clear_settings_cache_exists(self):
        from app.config import clear_settings_cache
        assert callable(clear_settings_cache)

    def test_clear_settings_cache_resets_lru(self):
        from app import config
        s1 = config.get_settings()
        config.clear_settings_cache()
        s2 = config.get_settings()
        # After clearing, a new Settings object is returned
        assert s1 is not s2


class TestRedisPassword:
    def test_no_password_url_unchanged(self):
        from app.storage.redis_client import _build_redis_url
        url = _build_redis_url("redis://localhost:6379", "")
        assert url == "redis://localhost:6379"

    def test_password_injected_into_bare_url(self):
        from app.storage.redis_client import _build_redis_url
        url = _build_redis_url("redis://localhost:6379", "s3cr3t")
        assert url == "redis://:s3cr3t@localhost:6379"

    def test_password_not_doubled_if_already_in_url(self):
        from app.storage.redis_client import _build_redis_url
        url = _build_redis_url("redis://:existing@localhost:6379", "s3cr3t")
        # URL already has credentials — leave it alone
        assert url == "redis://:existing@localhost:6379"


class TestBooleanColumns:
    def test_model_types_are_bool(self):
        from sqlalchemy import Boolean
        from app.models.brain import TransitionOrientation, EntityRelationship
        from app.models.contradiction import Contradiction
        from app.models.nebula import InteractionLog
        from app.models.profiles import ModelProfile

        checks = [
            (TransitionOrientation, "used"),
            (EntityRelationship, "inferred"),
            (Contradiction, "human_reviewed"),
            (InteractionLog, "personal_data"),
            (ModelProfile, "is_builtin"),
        ]
        for model_cls, col_name in checks:
            col = model_cls.__table__.c[col_name]
            assert isinstance(col.type, Boolean), \
                f"{model_cls.__name__}.{col_name} should be Boolean, got {type(col.type).__name__}"
