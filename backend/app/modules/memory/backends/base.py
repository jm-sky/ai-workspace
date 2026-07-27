"""MemoryBackend Protocol — abstraction over memory persistence."""

from typing import Any, Protocol, runtime_checkable

from app.modules.memory.schemas import MemoryEntryResponse


@runtime_checkable
class MemoryBackend(Protocol):
    """Pluggable memory storage backend.

    Implementations: PgVectorMemoryBackend (default), GraphitiMemoryBackend (spike).
    MemoryEntryResponse with ``similarity`` set serves as MemoryHit.
    """

    async def create(
        self,
        *,
        tenant_id: str,
        user_id: str,
        scope: str,
        content: str,
        agent_key: str | None,
        session_id: str | None,
        source: str,
        metadata: dict[str, Any] | None,
    ) -> tuple[MemoryEntryResponse, str | None]:
        """Create a memory entry with dedupe. Returns (entry, duplicate_of_id)."""
        ...

    async def search(
        self,
        *,
        tenant_id: str,
        user_id: str,
        query: str,
        agent_key: str | None,
        session_id: str | None,
        scope: str | None,
        limit: int,
    ) -> list[MemoryEntryResponse]:
        """Semantic search over memories. Returns entries with similarity set."""
        ...

    async def update(
        self,
        *,
        entry_id: str,
        tenant_id: str,
        user_id: str,
        content: str | None,
        scope: str | None,
        agent_key: str | None,
        session_id: str | None,
        metadata: dict[str, Any] | None,
        update_metadata: bool,
    ) -> MemoryEntryResponse | None:
        """Partial update. Re-embeds when content changes. Returns None on ACL miss."""
        ...

    async def delete(
        self,
        *,
        entry_id: str,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        """Delete a memory entry. Returns True if deleted."""
        ...

    async def list_entries(
        self,
        *,
        tenant_id: str,
        user_id: str,
        scope: str | None,
        agent_key: str | None,
        session_id: str | None,
        search_text: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MemoryEntryResponse], int]:
        """Paginated list with optional filters. Returns (entries, total)."""
        ...
