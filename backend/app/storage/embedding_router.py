import asyncio
import logging
import threading
from typing import Protocol
import httpx
from app.config import get_settings

_embed_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _embed_semaphore
    if _embed_semaphore is None:
        _embed_semaphore = asyncio.Semaphore(8)
    return _embed_semaphore

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    async def embed(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        ...


class OllamaEmbeddingProvider:
    def __init__(self, base_url: str = "", model: str = ""):
        settings = get_settings()
        self.base_url = base_url or settings.OLLAMA_URL
        self.model = model or settings.EMBEDDING_MODEL
        self._client = httpx.AsyncClient(timeout=30.0, base_url=self.base_url)

    async def embed(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        resp = await self._client.post(
            "/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    async def embed_batch(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        sem = _get_semaphore()
        async def _embed_one(t: str) -> list[float]:
            async with sem:
                return await self.embed(t, task_type)
        return list(await asyncio.gather(*[_embed_one(t) for t in texts]))


class GoogleEmbeddingProvider:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or get_settings().GOOGLE_API_KEY
        self._client = httpx.AsyncClient(timeout=30.0)

    async def embed(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        resp = await self._client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent",
            headers={"x-goog-api-key": self.api_key},
            json={"model": "models/text-embedding-004", "content": {"parts": [{"text": text}]}, "taskType": task_type},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]

    async def embed_batch(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        # Google supports batchEmbedContents
        requests = [{"model": "models/text-embedding-004", "content": {"parts": [{"text": t}]}, "taskType": task_type} for t in texts]
        resp = await self._client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents",
            headers={"x-goog-api-key": self.api_key},
            json={"requests": requests},
        )
        resp.raise_for_status()
        return [e["values"] for e in resp.json()["embeddings"]]


_provider: EmbeddingProvider | None = None
_provider_lock = threading.Lock()


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                settings = get_settings()
                if settings.EMBEDDING_PROVIDER == "google" and settings.GOOGLE_API_KEY:
                    _provider = GoogleEmbeddingProvider(settings.GOOGLE_API_KEY)
                else:
                    _provider = OllamaEmbeddingProvider(settings.OLLAMA_URL)
    return _provider


async def close_embedding_provider():
    """Close httpx clients on shutdown."""
    global _provider
    if _provider is not None and hasattr(_provider, "_client"):
        await _provider._client.aclose()
        _provider = None
