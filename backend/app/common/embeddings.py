"""Shared text embedding client (OpenRouter / OpenAI-compatible)."""

import asyncio
import hashlib
import json
import logging
from typing import cast

from openai import InternalServerError, RateLimitError

from app.core.config import settings
from app.core.redis import get_redis_client
from app.modules.usage.openrouter_client import create_openrouter_client
from app.modules.usage.recorder import UsageRecordContext, UsageRecorder

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_INITIAL_BACKOFF_SECONDS = 1.0


class EmbeddingService:
    """Generate text embeddings via OpenRouter (OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        usage_recorder: UsageRecorder | None = None,
        usage_ctx: UsageRecordContext | None = None,
    ):
        key = api_key or settings.ai.openrouter_api_key
        if not key:
            raise ValueError("OPENROUTER_API_KEY is not configured")
        self.model = settings.ai.embedding_model
        self.dimensions = settings.ai.embedding_dimensions
        self.usage_recorder = usage_recorder
        self.usage_ctx = usage_ctx
        self.client = create_openrouter_client(api_key=key)

    async def embed(self, text: str) -> list[float]:
        """Return embedding vector for a single text (Redis-cached)."""
        stripped = text.strip()
        cached = await self._cache_get(stripped)
        if cached is not None:
            return cached

        embeddings = await self._embed_with_retry([stripped])
        embedding = embeddings[0]
        await self._cache_set(stripped, embedding)
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for many texts, preserving input order.

        Cache hits are served without an API call; the remainder is batched
        by ``AI_EMBEDDING_BATCH_SIZE`` and sent to the provider.
        """
        stripped = [t.strip() for t in texts]
        results: list[list[float] | None] = [None] * len(stripped)
        pending_indexes: list[int] = []
        pending_texts: list[str] = []

        for index, item in enumerate(stripped):
            cached = await self._cache_get(item)
            if cached is not None:
                results[index] = cached
            else:
                pending_indexes.append(index)
                pending_texts.append(item)

        batch_size = settings.ai.embedding_batch_size
        for start in range(0, len(pending_texts), batch_size):
            batch = pending_texts[start : start + batch_size]
            embeddings = await self._embed_with_retry(batch)
            for offset, embedding in enumerate(embeddings):
                index = pending_indexes[start + offset]
                results[index] = embedding
                await self._cache_set(batch[offset], embedding)

        return [embedding for embedding in results if embedding is not None]

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        delay = _INITIAL_BACKOFF_SECONDS
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                    dimensions=self.dimensions,
                )
                embeddings = [item.embedding for item in response.data]
                for embedding in embeddings:
                    if len(embedding) != self.dimensions:
                        logger.warning(
                            "Embedding dimension mismatch: expected %s, got %s",
                            self.dimensions,
                            len(embedding),
                        )
                if self.usage_recorder and self.usage_ctx:
                    await self.usage_recorder.record_embedding_batch(
                        self.usage_ctx,
                        model=self.model,
                        texts=texts,
                    )
                return embeddings
            except (RateLimitError, InternalServerError):
                if attempt == _MAX_ATTEMPTS:
                    raise
                logger.warning(
                    "Embedding request failed (attempt %s/%s), retrying in %.1fs",
                    attempt,
                    _MAX_ATTEMPTS,
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= 2

        raise RuntimeError("unreachable")  # pragma: no cover

    def _cache_key(self, text: str) -> str:
        raw = f"{self.model}|{self.dimensions}|{text}"
        return "embed:" + hashlib.sha256(raw.encode()).hexdigest()

    async def _cache_get(self, text: str) -> list[float] | None:
        if not settings.ai.cache_enabled:
            return None
        try:
            redis_client = await get_redis_client()
            cached = await redis_client.get(self._cache_key(text))
        except Exception:
            logger.warning("Embedding cache read failed", exc_info=True)
            return None
        if cached is None:
            return None
        return cast(list[float], json.loads(cached))

    async def _cache_set(self, text: str, embedding: list[float]) -> None:
        if not settings.ai.cache_enabled:
            return
        try:
            redis_client = await get_redis_client()
            ttl_seconds = settings.ai.cache_ttl_embed * 86400
            await redis_client.setex(self._cache_key(text), ttl_seconds, json.dumps(embedding))
        except Exception:
            logger.warning("Embedding cache write failed", exc_info=True)

    @staticmethod
    def vector_to_pg_literal(vector: list[float]) -> str:
        """Format vector for pgvector SQL literal."""
        return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
