"""Web search contracts and provider resolution."""

import logging
from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class WebSearchError(Exception):
    """Provider could not satisfy the request (surfaced to the model as a message)."""


@dataclass(frozen=True)
class WebSearchResult:
    """Single search hit as handed to the model."""

    index: int
    title: str
    url: str
    snippet: str = ""
    published_at: str | None = None

    def to_source(self) -> dict[str, object]:
        """Shape consumed by the `sources` rich block."""
        payload: dict[str, object] = {
            "index": self.index,
            "url": self.url,
            "title": self.title,
        }
        if self.snippet:
            payload["snippet"] = self.snippet
        if self.published_at:
            payload["publishedAt"] = self.published_at
        return payload


@dataclass(frozen=True)
class WebPage:
    """Fetched page content, already extracted to plain text/markdown."""

    url: str
    title: str
    content: str
    truncated: bool = False


class WebSearchProvider(Protocol):
    """Search the public web and read pages found there."""

    @property
    def name(self) -> str: ...

    @property
    def available(self) -> bool: ...

    async def search(
        self,
        query: str,
        *,
        max_results: int,
        recency_days: int | None = None,
        domains: list[str] | None = None,
    ) -> list[WebSearchResult]: ...

    async def fetch(self, url: str, *, max_chars: int) -> WebPage: ...


class NoopWebSearchProvider:
    """Placeholder used when no provider is configured.

    Raises `WebSearchError` so the tool can turn it into a soft message rather
    than an `error` key (which the agent loop escalates to `AgentToolError`).
    """

    @property
    def name(self) -> str:
        return "none"

    @property
    def available(self) -> bool:
        return False

    async def search(
        self,
        query: str,
        *,
        max_results: int,
        recency_days: int | None = None,
        domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        raise WebSearchError("No web search provider is configured (set AI_WEB_SEARCH_API_KEY or use AI_WEB_SEARCH_MODE=server)")

    async def fetch(self, url: str, *, max_chars: int) -> WebPage:
        raise WebSearchError("No web search provider is configured (set AI_WEB_SEARCH_API_KEY or use AI_WEB_SEARCH_MODE=server)")


def resolve_web_search_provider() -> WebSearchProvider:
    """Build the configured provider for local mode (Noop when unconfigured)."""
    ai = settings.ai
    if ai.web_search_mode != "local":
        return NoopWebSearchProvider()

    if ai.web_search_provider == "tavily" and ai.web_search_api_key:
        from app.modules.websearch.providers.tavily import TavilyProvider

        return TavilyProvider(
            api_key=ai.web_search_api_key,
            base_url=ai.web_search_base_url,
            timeout=ai.web_search_timeout,
        )

    logger.warning(
        "AI_WEB_SEARCH_MODE=local but provider %r is not configured; web tools will degrade",
        ai.web_search_provider,
    )
    return NoopWebSearchProvider()
