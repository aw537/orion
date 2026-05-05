"""Unit tests for ChromaClient — collection naming and query_all_regions."""
import pytest
from unittest.mock import MagicMock
from app.storage.chroma_client import ChromaClient


@pytest.fixture
def mock_chroma_http():
    client = MagicMock()
    client.get_or_create_collection.return_value = MagicMock()
    return client


@pytest.fixture
def chroma(mock_chroma_http):
    return ChromaClient(mock_chroma_http)


class TestCollectionNaming:
    def test_basic_name(self, chroma):
        name = chroma.collection_name("gal-1", "analytical")
        assert name == "orion_gal-1_analytical"

    def test_all_regions(self, chroma):
        for region in ["analytical", "procedural", "contextual"]:
            name = chroma.collection_name("g", region)
            assert name == f"orion_g_{region}"

    def test_regions_constant(self):
        assert ChromaClient.REGIONS == ["analytical", "procedural", "contextual", "creative", "empathetic", "critical", "strategic"]


class TestEnsureCollections:
    def test_creates_all_collections(self, chroma, mock_chroma_http):
        chroma.ensure_collections("gal-1", ["p1", "p2"])
        # 7 regions (planet_ids ignored now)
        assert mock_chroma_http.get_or_create_collection.call_count == 7

    def test_single_planet(self, chroma, mock_chroma_http):
        chroma.ensure_collections("gal-1", ["p1"])
        assert mock_chroma_http.get_or_create_collection.call_count == 7

    def test_no_planets(self, chroma, mock_chroma_http):
        chroma.ensure_collections("gal-1")
        assert mock_chroma_http.get_or_create_collection.call_count == 7


class TestUpsertStardust:
    @pytest.mark.asyncio
    async def test_upsert_calls_collection(self, chroma, mock_chroma_http):
        col = MagicMock()
        mock_chroma_http.get_or_create_collection.return_value = col
        result = await chroma.upsert_stardust("g", "p", "analytical", "s1", "content", [0.1, 0.2], {"key": "val"})
        col.upsert.assert_called_once_with(ids=["s1"], embeddings=[[0.1, 0.2]], documents=["content"], metadatas=[{"key": "val", "planet_id": "p"}])
        assert result == "s1"


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_passes_params(self, chroma, mock_chroma_http):
        col = MagicMock()
        col.query.return_value = {"ids": [["s1"]], "documents": [["doc"]], "metadatas": [[{}]], "distances": [[0.1]]}
        mock_chroma_http.get_or_create_collection.return_value = col
        result = await chroma.query("g", "p", "analytical", [0.1], n_results=5)
        col.query.assert_called_once()
        kwargs = col.query.call_args[1]
        assert kwargs["n_results"] == 5

    @pytest.mark.asyncio
    async def test_query_with_where_filter(self, chroma, mock_chroma_http):
        col = MagicMock()
        col.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_chroma_http.get_or_create_collection.return_value = col
        await chroma.query("g", "p", "analytical", [0.1], where={"gravity": "BIOME"})
        kwargs = col.query.call_args[1]
        # planet_id and caller where combined via $and
        assert kwargs["where"] == {"$and": [{"planet_id": "p"}, {"gravity": "BIOME"}]}

    @pytest.mark.asyncio
    async def test_query_with_and_where_filter(self, chroma, mock_chroma_http):
        """Regression: $and filters from caller must not be flattened incorrectly."""
        col = MagicMock()
        col.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_chroma_http.get_or_create_collection.return_value = col
        caller_where = {"$and": [{"gravity": {"$in": ["BIOME", "PLANET", "GALAXY"]}}, {"biome_id": "b1"}]}
        await chroma.query("g", "p", "analytical", [0.1], where=caller_where)
        kwargs = col.query.call_args[1]
        assert kwargs["where"] == {"$and": [{"planet_id": "p"}, caller_where]}

    @pytest.mark.asyncio
    async def test_query_no_planet_with_where(self, chroma, mock_chroma_http):
        col = MagicMock()
        col.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_chroma_http.get_or_create_collection.return_value = col
        await chroma.query("g", None, "analytical", [0.1], where={"gravity": "BIOME"})
        kwargs = col.query.call_args[1]
        assert kwargs["where"] == {"gravity": "BIOME"}

    @pytest.mark.asyncio
    async def test_query_planet_no_where(self, chroma, mock_chroma_http):
        col = MagicMock()
        col.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_chroma_http.get_or_create_collection.return_value = col
        await chroma.query("g", "p", "analytical", [0.1])
        kwargs = col.query.call_args[1]
        assert kwargs["where"] == {"planet_id": "p"}


class TestQueryAllRegions:
    @pytest.mark.asyncio
    async def test_queries_all_three_regions(self, chroma, mock_chroma_http):
        col = MagicMock()
        col.query.return_value = {"ids": [["s1"]], "documents": [["doc"]], "metadatas": [[{"key": "val"}]], "distances": [[0.1]]}
        mock_chroma_http.get_or_create_collection.return_value = col
        results = await chroma.query_all_regions("g", "p", [0.1])
        # 7 regions, each returning 1 result
        assert len(results) == 7
        assert all(r["id"] == "s1" for r in results)

    @pytest.mark.asyncio
    async def test_handles_empty_results(self, chroma, mock_chroma_http):
        col = MagicMock()
        col.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_chroma_http.get_or_create_collection.return_value = col
        results = await chroma.query_all_regions("g", "p", [0.1])
        assert results == []

    @pytest.mark.asyncio
    async def test_handles_region_failure(self, chroma, mock_chroma_http):
        col = MagicMock()
        call_count = [0]
        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Chroma error")
            return {"ids": [["s1"]], "documents": [["doc"]], "metadatas": [[{}]], "distances": [[0.1]]}
        col.query.side_effect = side_effect
        mock_chroma_http.get_or_create_collection.return_value = col
        results = await chroma.query_all_regions("g", "p", [0.1])
        # 6 out of 7 regions succeed
        assert len(results) == 6

    @pytest.mark.asyncio
    async def test_result_includes_region(self, chroma, mock_chroma_http):
        col = MagicMock()
        col.query.return_value = {"ids": [["s1"]], "documents": [["doc"]], "metadatas": [[{}]], "distances": [[0.5]]}
        mock_chroma_http.get_or_create_collection.return_value = col
        results = await chroma.query_all_regions("g", "p", [0.1])
        regions = {r["region"] for r in results}
        assert regions == {"analytical", "procedural", "contextual", "creative", "empathetic", "critical", "strategic"}
