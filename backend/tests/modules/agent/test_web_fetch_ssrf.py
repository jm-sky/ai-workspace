"""SSRF guard for web_fetch (plan 013).

The guard is the only thing standing between a model-chosen URL and the
container's own network, so every rejection path gets a test.
"""

from unittest.mock import patch

import pytest

from app.modules.websearch.fetcher import UrlNotAllowedError, assert_url_allowed


def _resolves_to(*addresses: str):
    """Patch DNS so a public-looking hostname maps to the given addresses."""
    return patch("app.modules.websearch.fetcher._resolve_addresses", return_value=list(addresses))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "gopher://example.com",
    ],
)
async def test_rejects_non_http_schemes(url):
    with pytest.raises(UrlNotAllowedError, match="http and https"):
        await assert_url_allowed(url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://db.internal/dump",
        "http://printer.local",
    ],
)
async def test_rejects_internal_hostnames(url):
    with pytest.raises(UrlNotAllowedError, match="internal host"):
        await assert_url_allowed(url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8003/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.16.0.5/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
    ],
)
async def test_rejects_private_ip_literals(url):
    with pytest.raises(UrlNotAllowedError, match="private or loopback"):
        await assert_url_allowed(url)


@pytest.mark.asyncio
async def test_rejects_a_public_name_that_resolves_into_private_space():
    """DNS rebinding: the literal looks fine, the resolved address does not."""
    with _resolves_to("127.0.0.1"):
        with pytest.raises(UrlNotAllowedError, match="resolves to a private"):
            await assert_url_allowed("https://evil.example/")


@pytest.mark.asyncio
async def test_rejects_when_any_resolved_address_is_private():
    """One public A record must not launder a private one."""
    with _resolves_to("93.184.216.34", "169.254.169.254"):
        with pytest.raises(UrlNotAllowedError, match="resolves to a private"):
            await assert_url_allowed("https://mixed.example/")


@pytest.mark.asyncio
async def test_rejects_unresolvable_hosts():
    with patch("app.modules.websearch.fetcher._resolve_addresses", side_effect=OSError("nxdomain")):
        with pytest.raises(UrlNotAllowedError, match="Could not resolve"):
            await assert_url_allowed("https://nope.example/")


@pytest.mark.asyncio
async def test_rejects_configured_blocked_hosts():
    with patch("app.modules.websearch.fetcher.settings") as mock_settings, _resolves_to("93.184.216.34"):
        mock_settings.ai.web_fetch_blocked_hosts = ["corp.example"]
        with pytest.raises(UrlNotAllowedError, match="blocked host"):
            await assert_url_allowed("https://wiki.corp.example/secret")


@pytest.mark.asyncio
async def test_allows_a_public_url_and_drops_the_fragment():
    with _resolves_to("93.184.216.34"):
        assert await assert_url_allowed("https://example.com/a?b=1#frag") == "https://example.com/a?b=1"


@pytest.mark.asyncio
async def test_rejects_a_url_without_a_host():
    with pytest.raises(UrlNotAllowedError, match="no host"):
        await assert_url_allowed("https:///path-only")
