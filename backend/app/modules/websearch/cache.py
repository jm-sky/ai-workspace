"""Redis cache for web search results and fetched pages.

Web results are public data, so the cache is global rather than per-user — it
saves both latency and per-result billing. Every failure degrades silently: a
missing Redis must never break a search.
"""

import hashlib
import json
import logging
from typing import Any

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

CACHE_PREFIX = "websearch:v1"


def cache_key(kind: str, provider: str, payload: dict[str, Any]) -> str:
    """Stable key over the request shape (sorted, so arg order cannot matter)."""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"{CACHE_PREFIX}:{kind}:{provider}:{digest}"


async def cache_get(key: str) -> Any | None:
    try:
        client = await get_redis_client()
        raw = await client.get(key)
    except Exception:
        logger.debug("Web search cache read failed", exc_info=True)
        return None

    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    if ttl <= 0:
        return
    try:
        client = await get_redis_client()
        await client.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        logger.debug("Web search cache write failed", exc_info=True)
