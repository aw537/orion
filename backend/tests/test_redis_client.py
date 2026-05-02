"""Unit tests for RedisClient — key builders and degradation behavior."""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from app.storage.redis_client import RedisClient


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.setex = AsyncMock()
    r.zadd = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.zrevrange = AsyncMock(return_value=[])
    r.set = AsyncMock()
    return r


@pytest.fixture
def client(mock_redis):
    return RedisClient(mock_redis)


# --- Key builders ---

class TestKeyBuilders:
    def test_cache_key(self):
        key = RedisClient.cache_key("gal-1", "bio-1", "star-1")
        assert key == "orion:gal-1:biome:bio-1:cache:star-1"

    def test_index_key(self):
        key = RedisClient.index_key("gal-1", "bio-1")
        assert key == "orion:gal-1:biome:bio-1:cache:index"

    def test_strength_key(self):
        key = RedisClient.strength_key("gal-1")
        assert key == "orion:gal-1:strength"

    def test_key_format_consistency(self):
        """All keys should start with 'orion:'."""
        assert RedisClient.cache_key("g", "b", "s").startswith("orion:")
        assert RedisClient.index_key("g", "b").startswith("orion:")
        assert RedisClient.strength_key("g").startswith("orion:")

    def test_special_characters_in_ids(self):
        key = RedisClient.cache_key("gal-abc-123", "bio-def-456", "star-ghi-789")
        assert "gal-abc-123" in key
        assert "bio-def-456" in key
        assert "star-ghi-789" in key


# --- Cache operations ---

class TestCacheStardust:
    @pytest.mark.asyncio
    async def test_cache_stardust_calls_setex_and_zadd(self, client, mock_redis):
        await client.cache_stardust("g1", "b1", "s1", {"content": "test"}, ttl=3600)
        mock_redis.setex.assert_called_once()
        mock_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_stardust_uses_correct_key(self, client, mock_redis):
        await client.cache_stardust("g1", "b1", "s1", {"content": "test"})
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "orion:g1:biome:b1:cache:s1"

    @pytest.mark.asyncio
    async def test_cache_stardust_uses_ttl(self, client, mock_redis):
        await client.cache_stardust("g1", "b1", "s1", {"content": "test"}, ttl=7200)
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 7200

    @pytest.mark.asyncio
    async def test_cache_stardust_serializes_json(self, client, mock_redis):
        data = {"content": "hello", "tags": ["a", "b"]}
        await client.cache_stardust("g1", "b1", "s1", data)
        stored = mock_redis.setex.call_args[0][2]
        parsed = json.loads(stored)
        assert parsed["content"] == "hello"
        assert parsed["tags"] == ["a", "b"]


# --- Degradation ---

class TestDegradation:
    @pytest.mark.asyncio
    async def test_cache_stardust_survives_redis_error(self, mock_redis):
        mock_redis.setex.side_effect = ConnectionError("Redis down")
        client = RedisClient(mock_redis)
        # Should not raise
        await client.cache_stardust("g1", "b1", "s1", {"content": "test"})

    @pytest.mark.asyncio
    async def test_get_stardust_returns_none_on_error(self, mock_redis):
        mock_redis.get.side_effect = ConnectionError("Redis down")
        client = RedisClient(mock_redis)
        result = await client.get_stardust("g1", "b1", "s1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_recent_returns_empty_on_error(self, mock_redis):
        mock_redis.zrevrange.side_effect = ConnectionError("Redis down")
        client = RedisClient(mock_redis)
        result = await client.get_recent_stardust("g1", "b1")
        assert result == []


# --- Read operations ---

class TestReadOperations:
    @pytest.mark.asyncio
    async def test_get_stardust_returns_parsed_json(self, client, mock_redis):
        mock_redis.get.return_value = '{"content": "hello", "id": "s1"}'
        result = await client.get_stardust("g1", "b1", "s1")
        assert result["content"] == "hello"
        assert result["id"] == "s1"

    @pytest.mark.asyncio
    async def test_get_stardust_returns_none_for_miss(self, client, mock_redis):
        mock_redis.get.return_value = None
        result = await client.get_stardust("g1", "b1", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_recent_stardust(self, client, mock_redis):
        mock_redis.zrevrange.return_value = ["s3", "s2", "s1"]
        result = await client.get_recent_stardust("g1", "b1", limit=3)
        assert result == ["s3", "s2", "s1"]

    @pytest.mark.asyncio
    async def test_get_all_cached_stardust(self, client, mock_redis):
        mock_redis.zrevrange.return_value = ["s1", "s2"]
        mock_redis.get.side_effect = [
            '{"id": "s1", "content": "first"}',
            '{"id": "s2", "content": "second"}',
        ]
        result = await client.get_all_cached_stardust("g1", "b1")
        assert len(result) == 2
        assert result[0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_get_all_cached_skips_none(self, client, mock_redis):
        mock_redis.zrevrange.return_value = ["s1", "s2"]
        mock_redis.get.side_effect = ['{"id": "s1"}', None]
        result = await client.get_all_cached_stardust("g1", "b1")
        assert len(result) == 1


# --- Strength ---

class TestStrength:
    @pytest.mark.asyncio
    async def test_set_strength(self, client, mock_redis):
        await client.set_strength("g1", 42.5)
        mock_redis.set.assert_called_once_with("orion:g1:strength", "42.5")

    @pytest.mark.asyncio
    async def test_get_strength(self, client, mock_redis):
        mock_redis.get.return_value = "123.4"
        result = await client.get_strength("g1")
        assert result == 123.4

    @pytest.mark.asyncio
    async def test_get_strength_default(self, client, mock_redis):
        mock_redis.get.return_value = None
        result = await client.get_strength("g1")
        assert result == 0.0
