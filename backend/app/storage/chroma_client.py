from __future__ import annotations
import asyncio
import logging
import threading
import chromadb
from app.config import get_settings

logger = logging.getLogger(__name__)

_client: chromadb.HttpClient | None = None
_client_lock = threading.Lock()


def get_chroma_client() -> chromadb.HttpClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                settings = get_settings()
                _client = chromadb.HttpClient(host=settings.CHROMA_URL.replace("http://", "").split(":")[0],
                                               port=int(settings.CHROMA_URL.split(":")[-1]))
    return _client


class ChromaClient:
    REGIONS = ["analytical", "procedural", "contextual", "creative", "empathetic", "critical", "strategic"]

    def __init__(self, client: chromadb.HttpClient):
        self.client = client

    def collection_name(self, galaxy_id: str, region: str) -> str:
        return f"orion_{galaxy_id}_{region}"

    def _get_or_create_collection_sync(self, galaxy_id: str, region: str):
        return self.client.get_or_create_collection(
            name=self.collection_name(galaxy_id, region),
            metadata={"hnsw:space": "cosine"},
        )

    async def _get_or_create_collection(self, galaxy_id: str, region: str):
        return await asyncio.get_running_loop().run_in_executor(
            None, self._get_or_create_collection_sync, galaxy_id, region,
        )

    def get_or_create_collection(self, galaxy_id: str, region: str):
        """Sync version for backward compat (ensure_collections)."""
        return self._get_or_create_collection_sync(galaxy_id, region)

    def ensure_collections(self, galaxy_id: str, planet_ids: list[str] | None = None):
        for region in self.REGIONS:
            self._get_or_create_collection_sync(galaxy_id, region)

    async def upsert_stardust(self, galaxy_id: str, planet_id: str, region: str,
                              stardust_id: str, content: str, embedding: list[float], metadata: dict):
        metadata["planet_id"] = planet_id
        col = await self._get_or_create_collection(galaxy_id, region)

        def _upsert():
            col.upsert(ids=[stardust_id], embeddings=[embedding], documents=[content], metadatas=[metadata])

        await asyncio.get_running_loop().run_in_executor(None, _upsert)
        return stardust_id

    async def query(self, galaxy_id: str, planet_id: str | None, region: str,
                    query_embedding: list[float], n_results: int = 10, where: dict | None = None):
        col = await self._get_or_create_collection(galaxy_id, region)
        kwargs = {"query_embeddings": [query_embedding], "n_results": n_results, "include": ["documents", "metadatas", "distances"]}
        if planet_id:
            planet_filter = {"planet_id": planet_id}
            kwargs["where"] = {**planet_filter, **(where or {})} if where else planet_filter
        elif where:
            kwargs["where"] = where

        def _query():
            return col.query(**kwargs)

        return await asyncio.get_running_loop().run_in_executor(None, _query)

    async def query_all_regions(self, galaxy_id: str, planet_id: str | None,
                                query_embedding: list[float], n_results: int = 10, where: dict | None = None) -> list[dict]:
        all_results = []
        for region in self.REGIONS:
            try:
                results = await self.query(galaxy_id, planet_id, region, query_embedding, n_results, where)
                if results and results["ids"] and results["ids"][0]:
                    for i, sid in enumerate(results["ids"][0]):
                        all_results.append({
                            "id": sid,
                            "content": results["documents"][0][i] if results["documents"] else "",
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                            "distance": results["distances"][0][i] if results["distances"] else 1.0,
                            "region": region,
                        })
            except Exception as e:
                logger.warning(f"Chroma query failed for region {region}: {e}")
        return all_results
