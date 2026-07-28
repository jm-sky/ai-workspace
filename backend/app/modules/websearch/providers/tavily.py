"""Tavily adapter — search (`/search`) and page extraction (`/extract`).

Tavily is used because a single key covers both halves of the job: its
`/extract` endpoint returns already-cleaned page text, so the backend needs no
HTML parsing dependency.
"""

import logging
from typing import Any

import httpx

from app.modules.websearch.fetcher import assert_url_allowed
from app.modules.websearch.types import WebPage, WebSearchError, WebSearchResult

logger = logging.getLogger(__name__)


class TavilyProvider:
    """Thin client over the Tavily REST API."""

    def __init__(self, *, api_key: str, base_url: str, timeout: float):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "tavily"

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}{path}",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "ai-workspace-websearch/1.0",
                    },
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Web search provider unreachable: {exc}") from exc

        if response.status_code in (401, 403):
            raise WebSearchError("Web search provider rejected the API key")
        if response.status_code == 429:
            raise WebSearchError("Web search provider rate limit reached")
        if response.status_code >= 400:
            raise WebSearchError(f"Web search provider error {response.status_code}: {response.text[:200]}")

        try:
            return dict(response.json())
        except ValueError as exc:
            raise WebSearchError("Web search provider returned a malformed response") from exc

    async def search(
        self,
        query: str,
        *,
        max_results: int,
        recency_days: int | None = None,
        domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        payload: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        if recency_days is not None:
            payload["days"] = recency_days
            payload["topic"] = "news"
        if domains:
            payload["include_domains"] = domains

        data = await self._post("/search", payload)

        results: list[WebSearchResult] = []
        for position, item in enumerate(data.get("results") or [], start=1):
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                WebSearchResult(
                    index=position,
                    title=str(item.get("title") or url),
                    url=url,
                    snippet=str(item.get("content") or "")[:600],
                    published_at=item.get("published_date") or None,
                )
            )
        return results

    async def fetch(self, url: str, *, max_chars: int) -> WebPage:
        safe_url = await assert_url_allowed(url)

        data = await self._post("/extract", {"urls": [safe_url]})

        entries = data.get("results") or []
        if not entries:
            failed = data.get("failed_results") or []
            reason = str(failed[0].get("error")) if failed and isinstance(failed[0], dict) else "no content returned"
            raise WebSearchError(f"Could not read {safe_url}: {reason}")

        entry = entries[0]
        content = str(entry.get("raw_content") or entry.get("content") or "")
        if not content.strip():
            raise WebSearchError(f"Could not read {safe_url}: the page had no extractable text")

        return WebPage(
            url=str(entry.get("url") or safe_url),
            title=str(entry.get("title") or safe_url),
            content=content[:max_chars],
            truncated=len(content) > max_chars,
        )
