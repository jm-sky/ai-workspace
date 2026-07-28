"""SSRF-safe URL validation and raw fetching for `web_fetch`.

The guard runs before *any* outbound request, including requests we delegate to
a third-party extraction API — an internal hostname must not leak to a provider
either.
"""

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse, urlsplit, urlunsplit

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnames that never resolve to something the agent should read.
BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localdomain", ".home.arpa")
BLOCKED_HOSTNAMES = frozenset({"localhost", "metadata.google.internal"})

# Content types `raw_fetch` can hand to the model without an HTML parser.
RAW_CONTENT_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "application/json",
        "application/ld+json",
        "text/csv",
    }
)
# Recognized but needing extraction we do not do ourselves (see UrlNotReadable).
MARKUP_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml", "application/xml", "text/xml"})

MAX_REDIRECTS = 3


class UrlNotAllowedError(Exception):
    """URL failed the SSRF / scheme / host checks."""


class UrlNotReadableError(Exception):
    """URL is reachable but we cannot extract text from it without a provider."""


def _is_forbidden_address(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def _resolve_addresses(hostname: str) -> list[str]:
    infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


async def assert_url_allowed(url: str) -> str:
    """Validate a URL for outbound fetching. Returns the normalized URL.

    Raises `UrlNotAllowedError` for a bad scheme, a blocked hostname, or a host
    that resolves (now) to a private/loopback/link-local/reserved address. DNS is
    resolved here rather than trusting the literal, which also catches rebinding
    of a public-looking name onto 127.0.0.1 or 169.254.169.254.
    """
    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UrlNotAllowedError(f"Only http and https URLs can be fetched, got: {parsed.scheme or 'no scheme'}")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise UrlNotAllowedError("URL has no host")

    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(BLOCKED_HOST_SUFFIXES):
        raise UrlNotAllowedError(f"Refusing to fetch an internal host: {hostname}")

    for blocked in settings.ai.web_fetch_blocked_hosts:
        if hostname == blocked or hostname.endswith(blocked if blocked.startswith(".") else f".{blocked}"):
            raise UrlNotAllowedError(f"Refusing to fetch a blocked host: {hostname}")

    if _is_forbidden_address(hostname):
        raise UrlNotAllowedError(f"Refusing to fetch a private or loopback address: {hostname}")

    try:
        addresses = await asyncio.to_thread(_resolve_addresses, hostname)
    except (OSError, socket.gaierror) as exc:
        raise UrlNotAllowedError(f"Could not resolve host: {hostname}") from exc

    if not addresses:
        raise UrlNotAllowedError(f"Could not resolve host: {hostname}")

    for address in addresses:
        if _is_forbidden_address(address):
            raise UrlNotAllowedError(f"Host {hostname} resolves to a private or loopback address ({address})")

    # Drop the fragment — it never reaches the server anyway.
    split = urlsplit(url)
    return urlunsplit((split.scheme, split.netloc, split.path, split.query, ""))


def _content_type_of(response: httpx.Response) -> str:
    return (response.headers.get("content-type") or "").split(";")[0].strip().lower()


async def raw_fetch(url: str, *, max_chars: int) -> tuple[str, str, bool]:
    """Fetch a URL that needs no HTML extraction.

    Returns `(final_url, content, truncated)`. Redirects are followed manually so
    every hop is re-validated. Raises `UrlNotReadableError` for markup or binary
    content — those need a provider (Tavily `/extract`, `openrouter:web_fetch`).
    """
    current = await assert_url_allowed(url)
    max_bytes = settings.ai.web_fetch_max_bytes

    async with httpx.AsyncClient(
        timeout=settings.ai.web_search_timeout,
        follow_redirects=False,
        headers={"User-Agent": "ai-workspace-web-fetch/1.0"},
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise UrlNotReadableError(f"Redirect without a Location header at {current}")
                    current = await assert_url_allowed(str(httpx.URL(current).join(location)))
                    continue

                response.raise_for_status()

                content_type = _content_type_of(response)
                if content_type in MARKUP_CONTENT_TYPES:
                    raise UrlNotReadableError(f"{current} is HTML; extracting it needs a web search provider (AI_WEB_SEARCH_MODE=local with a key, or mode=server)")
                if content_type and content_type not in RAW_CONTENT_TYPES:
                    raise UrlNotReadableError(f"Cannot read content type {content_type} from {current}")

                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= max_bytes:
                        break

                text = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
                truncated = size >= max_bytes or len(text) > max_chars
                return current, text[:max_chars], truncated

    raise UrlNotAllowedError(f"Too many redirects (>{MAX_REDIRECTS}) starting at {url}")
