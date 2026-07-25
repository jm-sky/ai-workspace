"""Postgres full-text-search config detection (plan 009 dec. #7).

`AI_RAG_FTS_CONFIG=auto` (the default) probes for the `polish` text-search
config and falls back to `simple` when the image's Postgres doesn't ship the
`polish` dictionary. Ingest must never fail because of this — only degrade.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

_detected_fts_config: str | None = None


async def resolve_fts_config(db: AsyncSession) -> str:
    """Return the tsvector config to use: explicit setting, or auto-detected."""
    configured = settings.ai.rag_fts_config
    if configured != "auto":
        return configured

    global _detected_fts_config
    if _detected_fts_config is None:
        result = await db.execute(text("SELECT 1 FROM pg_ts_config WHERE cfgname = 'polish'"))
        _detected_fts_config = "polish" if result.scalar() is not None else "simple"
    return _detected_fts_config
