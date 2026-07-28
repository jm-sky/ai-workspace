"""Tests for the web_search / web_fetch agent tools (plan 013)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.agent.tools.web import WebFetchTool, WebSearchTool, wrap_untrusted
from app.modules.websearch.types import WebPage, WebSearchError, WebSearchResult


class _StubProvider:
    """Provider double recording calls, with scripted results or an error."""

    def __init__(self, *, results=None, page=None, error: Exception | None = None, available: bool = True):
        self._results = results or []
        self._page = page
        self._error = error
        self._available = available
        self.search_calls: list[dict] = []
        self.fetch_calls: list[dict] = []

    @property
    def name(self) -> str:
        return "stub"

    @property
    def available(self) -> bool:
        return self._available

    async def search(self, query, *, max_results, recency_days=None, domains=None):
        self.search_calls.append({"query": query, "max_results": max_results, "recency_days": recency_days, "domains": domains})
        if self._error:
            raise self._error
        return self._results

    async def fetch(self, url, *, max_chars):
        self.fetch_calls.append({"url": url, "max_chars": max_chars})
        if self._error:
            raise self._error
        return self._page


def _no_cache():
    """Bypass Redis so tests never depend on a running instance."""
    return (
        patch("app.modules.agent.tools.web.cache_get", AsyncMock(return_value=None)),
        patch("app.modules.agent.tools.web.cache_set", AsyncMock()),
    )


def _dns_ok():
    """Let the SSRF guard pass: `.example` hosts do not resolve for real."""
    return patch("app.modules.websearch.fetcher._resolve_addresses", return_value=["93.184.216.34"])


@pytest.mark.asyncio
async def test_disabled_returns_soft_message_not_error():
    """A disabled capability must not raise AgentToolError in the loop."""
    tool = WebSearchTool(web_search_enabled=False, provider=_StubProvider())

    result = await tool.execute({"query": "anything"})

    assert result["message"] == "Web search is disabled for this workspace"
    assert result["results"] == []
    assert "error" not in result


@pytest.mark.asyncio
async def test_missing_query_is_an_error():
    tool = WebSearchTool(web_search_enabled=True, provider=_StubProvider())

    assert await tool.execute({"query": "   "}) == {"error": "query is required"}


@pytest.mark.asyncio
async def test_search_returns_results_and_sources_numbered_from_one():
    provider = _StubProvider(
        results=[
            WebSearchResult(index=99, title="First", url="https://a.example", snippet="s1"),
            WebSearchResult(index=99, title="Second", url="https://b.example", snippet="s2", published_at="2026-07-01"),
        ]
    )
    tool = WebSearchTool(web_search_enabled=True, provider=provider)

    get_patch, set_patch = _no_cache()
    with get_patch, set_patch:
        result = await tool.execute({"query": "vue 3.6"})

    assert result["total"] == 2
    assert result["cached"] is False
    # Provider indices are ignored; the block and the [n] markers must agree.
    assert [item["index"] for item in result["results"]] == [1, 2]
    assert result["sources"] == result["results"]
    assert result["results"][1]["publishedAt"] == "2026-07-01"


@pytest.mark.asyncio
async def test_max_results_is_clamped():
    provider = _StubProvider(results=[])
    tool = WebSearchTool(web_search_enabled=True, provider=provider)

    get_patch, set_patch = _no_cache()
    with get_patch, set_patch:
        await tool.execute({"query": "q", "max_results": 500})

    assert provider.search_calls[0]["max_results"] == 10


@pytest.mark.asyncio
async def test_cache_hit_short_circuits_the_provider():
    provider = _StubProvider(results=[])
    tool = WebSearchTool(web_search_enabled=True, provider=provider)
    cached = [{"index": 1, "url": "https://a.example", "title": "A"}]

    with patch("app.modules.agent.tools.web.cache_get", AsyncMock(return_value=cached)):
        result = await tool.execute({"query": "q"})

    assert result["cached"] is True
    assert result["results"] == cached
    assert provider.search_calls == []


@pytest.mark.asyncio
async def test_provider_failure_degrades_instead_of_failing_the_run():
    provider = _StubProvider(error=WebSearchError("provider exploded"))
    tool = WebSearchTool(web_search_enabled=True, provider=provider)

    get_patch, set_patch = _no_cache()
    with get_patch, set_patch:
        result = await tool.execute({"query": "q"})

    assert result["message"] == "provider exploded"
    assert "error" not in result


@pytest.mark.asyncio
async def test_unexpected_provider_exception_is_also_soft():
    provider = _StubProvider(error=RuntimeError("boom"))
    tool = WebSearchTool(web_search_enabled=True, provider=provider)

    get_patch, set_patch = _no_cache()
    with get_patch, set_patch:
        result = await tool.execute({"query": "q"})

    assert result["message"] == "Web search is temporarily unavailable"
    assert "error" not in result


@pytest.mark.asyncio
async def test_fetch_wraps_content_as_untrusted_and_reports_a_source():
    provider = _StubProvider(page=WebPage(url="https://a.example/post", title="Post", content="body text", truncated=False))
    tool = WebFetchTool(web_search_enabled=True, provider=provider)

    get_patch, set_patch = _no_cache()
    with get_patch, set_patch, _dns_ok():
        result = await tool.execute({"url": "https://a.example/post"})

    assert result["content"].startswith('<web_page url="https://a.example/post" untrusted="true">')
    assert "body text" in result["content"]
    assert result["sources"] == [{"index": 1, "url": "https://a.example/post", "title": "Post"}]


@pytest.mark.asyncio
async def test_fetch_rejects_a_blocked_url_softly():
    tool = WebFetchTool(web_search_enabled=True, provider=_StubProvider())

    result = await tool.execute({"url": "http://localhost/admin"})

    assert "internal host" in result["message"]
    assert result["content"] == ""
    assert "error" not in result


def test_wrap_untrusted_marks_the_payload_as_data():
    wrapped = wrap_untrusted("https://a.example", "hello")

    assert wrapped == '<web_page url="https://a.example" untrusted="true">\nhello\n</web_page>'
