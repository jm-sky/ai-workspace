"""RAG types and retrieval contracts."""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RagSourceType(StrEnum):
    PASTE = "paste"
    ATTACHMENT = "attachment"
    WIKI = "wiki"


@dataclass(frozen=True)
class RetrievalAcl:
    """Permissions filter applied before vector ranking."""

    tenant_id: str
    user_id: str


@dataclass(frozen=True)
class RetrievalHit:
    """Single retrieval result from a chunk store."""

    id: str
    content: str
    score: float
    document_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkRetriever(Protocol):
    """Permissions-aware chunk search (ACL before ranking)."""

    async def search(
        self,
        *,
        query_embedding: list[float],
        acl: RetrievalAcl,
        limit: int,
        min_similarity: float,
        query_text: str | None = None,
    ) -> list[RetrievalHit]: ...


class Reranker(Protocol):
    """Re-orders/truncates retrieval hits after dense+lexical fusion."""

    async def rerank(
        self,
        *,
        query: str,
        hits: list[RetrievalHit],
        top_n: int,
    ) -> list[RetrievalHit]: ...


class NoopReranker:
    """Default: truncates to `top_n`, preserving input order."""

    async def rerank(
        self,
        *,
        query: str,
        hits: list[RetrievalHit],
        top_n: int,
    ) -> list[RetrievalHit]:
        _ = query
        return hits[:top_n]


class HostedReranker:
    """HTTP reranker (Cohere Rerank-style: {results:[{index, relevance_score}]}).

    Any error or timeout degrades to Noop behavior — a reranker must never
    fail the user's search request (plan 009 dec. #9).
    """

    def __init__(self, *, url: str, model: str, api_key: str):
        self._url = url
        self._model = model
        self._api_key = api_key

    async def rerank(
        self,
        *,
        query: str,
        hits: list[RetrievalHit],
        top_n: int,
    ) -> list[RetrievalHit]:
        if not hits:
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "query": query,
                        "documents": [hit.content for hit in hits],
                        "top_n": top_n,
                    },
                )
                response.raise_for_status()
                payload = response.json()

            ordered = [
                hits[item["index"]]
                for item in payload.get("results", [])
                if isinstance(item.get("index"), int) and 0 <= item["index"] < len(hits)
            ]
            if ordered:
                return ordered[:top_n]
            return hits[:top_n]
        except Exception:
            logger.warning("HostedReranker request failed, degrading to Noop behavior", exc_info=True)
            return hits[:top_n]


def resolve_reranker() -> Reranker:
    """Build the configured reranker (NoopReranker unless AI_RAG_RERANK_ENABLED)."""
    if settings.ai.rag_rerank_enabled and settings.ai.rag_rerank_url:
        return HostedReranker(
            url=settings.ai.rag_rerank_url,
            model=settings.ai.rag_rerank_model,
            api_key=settings.ai.rag_rerank_api_key,
        )
    return NoopReranker()
