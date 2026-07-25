"""Tests for the shared EmbeddingService (batch/retry/cache — plan 009 embed-swap)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import InternalServerError, RateLimitError

from app.common.embeddings import EmbeddingService


class FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio.Redis (get/setex only)."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self._store[key] = value


def _make_response(vectors: list[list[float]]) -> MagicMock:
    response = MagicMock()
    response.data = [MagicMock(embedding=vector) for vector in vectors]
    return response


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> EmbeddingService:
    svc = EmbeddingService(api_key="test-key")
    fake_redis = FakeRedis()

    async def _get_redis_client() -> FakeRedis:
        return fake_redis

    monkeypatch.setattr("app.common.embeddings.get_redis_client", _get_redis_client)
    return svc


@pytest.mark.asyncio
async def test_embed_batch_chunks_by_batch_size_and_preserves_order(service: EmbeddingService):
    texts = [f"text-{i}" for i in range(130)]
    calls: list[list[str]] = []

    async def fake_create(*, model: str, input: list[str], dimensions: int):
        _ = model, dimensions
        calls.append(list(input))
        return _make_response([[float(len(t))] for t in input])

    with patch.object(service.client.embeddings, "create", side_effect=fake_create):
        results = await service.embed_batch(texts)

    assert [len(call) for call in calls] == [64, 64, 2]
    assert results == [[float(len(t))] for t in texts]


@pytest.mark.asyncio
async def test_embed_retries_on_rate_limit_then_succeeds(service: EmbeddingService):
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(429, request=request)
    error = RateLimitError("rate limited", response=response, body=None)

    call_count = 0

    async def fake_create(*, model: str, input: list[str], dimensions: int):
        _ = model, input, dimensions
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise error
        return _make_response([[1.0, 2.0]])

    with (
        patch.object(service.client.embeddings, "create", side_effect=fake_create),
        patch("app.common.embeddings.asyncio.sleep", new=AsyncMock()),
    ):
        result = await service.embed("hello")

    assert result == [1.0, 2.0]
    assert call_count == 2


@pytest.mark.asyncio
async def test_embed_raises_after_max_attempts(service: EmbeddingService):
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(500, request=request)
    error = InternalServerError("boom", response=response, body=None)
    call_count = 0

    async def fake_create(*, model: str, input: list[str], dimensions: int):
        _ = model, input, dimensions
        nonlocal call_count
        call_count += 1
        raise error

    with (
        patch.object(service.client.embeddings, "create", side_effect=fake_create),
        patch("app.common.embeddings.asyncio.sleep", new=AsyncMock()),
        pytest.raises(InternalServerError),
    ):
        await service.embed("hello")

    assert call_count == 3


@pytest.mark.asyncio
async def test_embed_cache_hit_skips_second_api_call(service: EmbeddingService):
    async def fake_create(*, model: str, input: list[str], dimensions: int):
        _ = model, input, dimensions
        return _make_response([[9.0]])

    with patch.object(service.client.embeddings, "create", side_effect=fake_create) as mocked:
        first = await service.embed("cache me")
        second = await service.embed("cache me")

    assert first == second == [9.0]
    assert mocked.call_count == 1
