"""Business logic facade for semantic memory — delegates to a MemoryBackend."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.memory.backends.pgvector import PgVectorMemoryBackend
from app.modules.memory.schemas import MemoryEntryResponse
from app.modules.memory.types import MemoryScope, MemorySource
from app.modules.tenants.service import TenantContext


def _create_backend(db: AsyncSession) -> PgVectorMemoryBackend:
    """Instantiate the configured memory backend.

    Raises ``ValueError`` for unknown backend types at construction time
    (not a silent fallback).
    """
    backend_type = settings.ai.memory_backend

    if backend_type == "pgvector":
        return PgVectorMemoryBackend(db)

    if backend_type == "graphiti":
        try:
            from app.modules.memory.backends.graphiti import GraphitiMemoryBackend
        except ImportError as exc:
            raise ImportError(
                "graphiti-core is not installed. "
                "Install it with: pip install graphiti-core"
            ) from exc
        return GraphitiMemoryBackend()  # type: ignore[return-value]

    raise ValueError(
        f"Unknown MEMORY_BACKEND: {backend_type!r}. "
        f"Allowed values: pgvector, graphiti"
    )


class MemoryService:
    """Create, search, and manage tenant-scoped memories.

    Thin facade over a :class:`MemoryBackend` implementation selected by
    ``settings.ai.memory_backend`` (default ``pgvector``).

    ``build_injection_context`` (prompt formatting) stays here — it is
    backend-agnostic.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._backend = _create_backend(db)

    # ------------------------------------------------------------------
    # Proxy properties — backward compatibility for tests that mock
    # service.repo / service._embedding on PgVectorMemoryBackend.
    # ------------------------------------------------------------------

    @property
    def repo(self):  # type: ignore[override]
        return self._backend.repo

    @repo.setter
    def repo(self, value):  # type: ignore[override]
        self._backend.repo = value

    @property
    def _embedding(self):
        return self._backend._embedding

    @_embedding.setter
    def _embedding(self, value):
        self._backend._embedding = value

    def _embedder(self):
        return self._backend._embedder()

    # ------------------------------------------------------------------
    # Public API — signatures unchanged from before the facade refactor
    # ------------------------------------------------------------------

    async def create_entry(
        self,
        *,
        tenant_ctx: TenantContext,
        content: str,
        scope: str = MemoryScope.USER.value,
        agent_key: str | None = None,
        session_id: str | None = None,
        source: str = MemorySource.USER.value,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[MemoryEntryResponse, str | None]:
        """Create a memory entry, deduping against near-identical content.

        Returns ``(entry, duplicate_of_id)``. When content is a near-duplicate
        of an existing entry (cosine similarity >= AI_MEMORY_DEDUPE_THRESHOLD,
        scoped like retrieval by agent_key/session_id), no new row is written
        and ``duplicate_of_id`` carries the existing entry's id (plan 009
        dec. #17) — ``content`` is unchanged from earlier idempotent writes.
        """
        return await self._backend.create(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            content=content,
            scope=scope,
            agent_key=agent_key,
            session_id=session_id,
            source=source,
            metadata=metadata,
        )

    async def search(
        self,
        *,
        tenant_ctx: TenantContext,
        query: str,
        agent_key: str | None = None,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntryResponse]:
        return await self._backend.search(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            query=query,
            agent_key=agent_key,
            session_id=session_id,
            scope=scope,
            limit=limit,
        )

    async def list_entries(
        self,
        *,
        tenant_ctx: TenantContext,
        scope: str | None = None,
        agent_key: str | None = None,
        session_id: str | None = None,
        search_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MemoryEntryResponse], int]:
        return await self._backend.list_entries(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            scope=scope,
            agent_key=agent_key,
            session_id=session_id,
            search_text=search_text,
            limit=limit,
            offset=offset,
        )

    async def delete_entry(
        self,
        *,
        tenant_ctx: TenantContext,
        entry_id: str,
    ) -> bool:
        return await self._backend.delete(
            entry_id=entry_id,
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
        )

    async def update_entry(
        self,
        *,
        tenant_ctx: TenantContext,
        entry_id: str,
        content: str | None = None,
        scope: str | None = None,
        agent_key: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        update_metadata: bool = False,
    ) -> MemoryEntryResponse | None:
        """Partial update. Re-embeds only when content changes. Returns None if ACL miss."""
        return await self._backend.update(
            entry_id=entry_id,
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            content=content,
            scope=scope,
            agent_key=agent_key,
            session_id=session_id,
            metadata=metadata,
            update_metadata=update_metadata,
        )

    async def build_injection_context(
        self,
        *,
        tenant_ctx: TenantContext,
        user_message: str,
        agent_key: str,
        session_id: str | None = None,
    ) -> str:
        """Return memories to prepend to the system prompt.

        Formatting stays on MemoryService — it is backend-agnostic.
        """
        if not settings.ai.memory_enabled:
            return ""

        matches = await self.search(
            tenant_ctx=tenant_ctx,
            query=user_message,
            agent_key=agent_key,
            session_id=session_id,
            limit=settings.ai.memory_injection_limit,
        )
        if not matches:
            return ""

        lines = ["## Relevant memories (auto-retrieved)", ""]
        for item in matches:
            scope_label = item.scope
            if item.agentKey:
                scope_label = f"{item.scope}/{item.agentKey}"
            sim = f" (similarity {item.similarity:.2f})" if item.similarity else ""
            lines.append(f"- [{scope_label}{sim}] {item.content}")
        lines.append("")
        return "\n".join(lines)
