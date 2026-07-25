"""Tests for plan 009 retrieval-quality additions: RRF fusion, FTS config
detection, and the Reranker protocol implementations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.rag.fts import resolve_fts_config
from app.modules.rag.repositories import _reciprocal_rank_fusion
from app.modules.rag.services.rag_service import RagService
from app.modules.rag.types import HostedReranker, NoopReranker, RetrievalHit


def _hit(chunk_id: str, *, score: float = 1.0) -> RetrievalHit:
    return RetrievalHit(id=chunk_id, content=f"content-{chunk_id}", score=score, document_id="doc-1")


def test_rrf_document_in_both_top1_beats_document_in_one_top1():
    dense = [_hit("a"), _hit("b"), _hit("c")]
    lexical = [_hit("a"), _hit("d"), _hit("e")]

    fused = _reciprocal_rank_fusion([dense, lexical], k=60, limit=10)

    assert fused[0].id == "a"


def test_rrf_includes_lexical_only_hit_missing_from_dense():
    dense = [_hit("a"), _hit("b")]
    lexical = [_hit("rare-token-hit")]

    fused = _reciprocal_rank_fusion([dense, lexical], k=60, limit=10)

    assert any(hit.id == "rare-token-hit" for hit in fused)


def test_rrf_respects_limit():
    dense = [_hit(str(i)) for i in range(10)]
    fused = _reciprocal_rank_fusion([dense], k=60, limit=3)
    assert len(fused) == 3


@pytest.mark.asyncio
async def test_resolve_fts_config_explicit_setting_skips_probe():
    db = AsyncMock()
    with patch("app.modules.rag.fts.settings.ai.rag_fts_config", "simple"):
        result = await resolve_fts_config(db)
    assert result == "simple"
    db.execute.assert_not_awaited()


def _db_returning_scalar(value: object) -> AsyncMock:
    """AsyncMock recursively async-mocks children, so `.scalar()` (sync in
    real SQLAlchemy) needs an explicit non-async stand-in here."""
    result = MagicMock()
    result.scalar = MagicMock(return_value=value)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_resolve_fts_config_auto_detects_polish():
    import app.modules.rag.fts as fts_module

    fts_module._detected_fts_config = None
    db = _db_returning_scalar(1)

    with patch("app.modules.rag.fts.settings.ai.rag_fts_config", "auto"):
        result = await resolve_fts_config(db)

    assert result == "polish"
    fts_module._detected_fts_config = None


@pytest.mark.asyncio
async def test_resolve_fts_config_auto_falls_back_to_simple_when_polish_missing():
    import app.modules.rag.fts as fts_module

    fts_module._detected_fts_config = None
    db = _db_returning_scalar(None)

    with patch("app.modules.rag.fts.settings.ai.rag_fts_config", "auto"):
        result = await resolve_fts_config(db)

    assert result == "simple"
    fts_module._detected_fts_config = None


@pytest.mark.asyncio
async def test_noop_reranker_truncates_preserving_order():
    hits = [_hit(str(i)) for i in range(5)]
    reranker = NoopReranker()

    result = await reranker.rerank(query="q", hits=hits, top_n=2)

    assert [hit.id for hit in result] == ["0", "1"]


@pytest.mark.asyncio
async def test_hosted_reranker_reorders_by_response_index():
    hits = [_hit("a"), _hit("b"), _hit("c")]
    reranker = HostedReranker(url="https://rerank.example/v1", model="test-model", api_key="key")

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"results": [{"index": 2, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.5}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.modules.rag.types.httpx.AsyncClient", return_value=mock_client):
        result = await reranker.rerank(query="q", hits=hits, top_n=2)

    assert [hit.id for hit in result] == ["c", "a"]


@pytest.mark.asyncio
async def test_hosted_reranker_degrades_to_noop_on_error():
    hits = [_hit("a"), _hit("b"), _hit("c")]
    reranker = HostedReranker(url="https://rerank.example/v1", model="test-model", api_key="key")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectTimeout("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.modules.rag.types.httpx.AsyncClient", return_value=mock_client):
        result = await reranker.rerank(query="q", hits=hits, top_n=2)

    assert [hit.id for hit in result] == ["a", "b"]


class _FakeChunk:
    def __init__(self, chunk_id: str, content: str):
        self.id = chunk_id
        self.content = content


@pytest.mark.asyncio
async def test_reembed_stale_chunks_dry_run_only_counts():
    service = RagService(AsyncMock())
    service.repo = MagicMock()
    service.repo.count_chunks_needing_reembed = AsyncMock(return_value=7)
    service.repo.list_chunks_needing_reembed = AsyncMock()

    count = await service.reembed_stale_chunks(dry_run=True)

    assert count == 7
    service.repo.list_chunks_needing_reembed.assert_not_awaited()


@pytest.mark.asyncio
async def test_reembed_stale_chunks_processes_in_batches_until_none_left():
    db = AsyncMock()
    service = RagService(db)
    service._embedding = MagicMock()
    service._embedding.model = "new-model"
    service._embedding.embed_batch = AsyncMock(side_effect=lambda texts: [[float(len(t))] for t in texts])

    batches = [
        [_FakeChunk("c1", "one"), _FakeChunk("c2", "two")],
        [],
    ]
    service.repo = MagicMock()
    service.repo.list_chunks_needing_reembed = AsyncMock(side_effect=batches)
    service.repo.update_chunk_embedding = AsyncMock()

    total = await service.reembed_stale_chunks(batch_size=2)

    assert total == 2
    assert service.repo.update_chunk_embedding.await_count == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reembed_stale_chunks_second_run_is_a_noop():
    service = RagService(AsyncMock())
    service.repo = MagicMock()
    service.repo.list_chunks_needing_reembed = AsyncMock(return_value=[])

    total = await service.reembed_stale_chunks()

    assert total == 0
