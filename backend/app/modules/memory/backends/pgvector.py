"""PgVector memory backend — persistence and embedding via pgvector + SQLAlchemy."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.embeddings import EmbeddingService
from app.core.config import settings
from app.modules.memory.db_models import MemoryEntry
from app.modules.memory.repositories import MemoryRepository
from app.modules.memory.schemas import MemoryEntryResponse
from app.modules.memory.types import MemoryScope
from app.modules.tenants.service import TenantContext
from app.modules.usage.embedding_factory import create_embedding_service


class PgVectorMemoryBackend:
    """MemoryBackend implementation backed by pgvector + PostgreSQL.

    Moved 1:1 from the original MemoryService logic — zero change in
    SQL or behaviour.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MemoryRepository(db)
        self._embedding: EmbeddingService | None = None

    async def _embedder_for(self, tenant_id: str, user_id: str) -> EmbeddingService:
        if self._embedding is not None:
            return self._embedding
        tenant_ctx = TenantContext(
            user_id=user_id,
            tenant_id=tenant_id,
            tenant_role="member",
        )
        return await create_embedding_service(self.db, tenant_ctx=tenant_ctx)

    async def create(
        self,
        *,
        tenant_id: str,
        user_id: str,
        content: str,
        scope: str = MemoryScope.USER.value,
        agent_key: str | None = None,
        session_id: str | None = None,
        source: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[MemoryEntryResponse, str | None]:
        """Create a memory entry, deduping against near-identical content.

        Returns ``(entry, duplicate_of_id)``.  When content is a near-duplicate
        of an existing entry (cosine similarity >= AI_MEMORY_DEDUPE_THRESHOLD,
        scoped like retrieval by agent_key/session_id), no new row is written
        and ``duplicate_of_id`` carries the existing entry's id.
        """
        embedding = await (await self._embedder_for(tenant_id, user_id)).embed(content)

        existing = await self.repo.search_similar(
            tenant_id=tenant_id,
            user_id=user_id,
            embedding=embedding,
            agent_key=agent_key,
            session_id=session_id,
            limit=1,
            min_similarity=settings.ai.memory_dedupe_threshold,
        )
        if existing:
            duplicate_entry, similarity = existing[0]
            return self._to_response(duplicate_entry, similarity=similarity), duplicate_entry.id

        entry = await self.repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            scope=scope,
            content=content,
            embedding=embedding,
            source=source,
            agent_key=agent_key,
            session_id=session_id,
            metadata=metadata,
        )
        await self.db.commit()
        return self._to_response(entry), None

    async def search(
        self,
        *,
        tenant_id: str,
        user_id: str,
        query: str,
        agent_key: str | None = None,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntryResponse]:
        if not settings.ai.memory_enabled:
            return []

        embedding = await (await self._embedder_for(tenant_id, user_id)).embed(query)
        results = await self.repo.search_similar(
            tenant_id=tenant_id,
            user_id=user_id,
            embedding=embedding,
            agent_key=agent_key,
            session_id=session_id,
            limit=limit,
            min_similarity=settings.ai.memory_similarity_threshold,
        )

        if scope:
            results = [(entry, sim) for entry, sim in results if entry.scope == scope]

        return [self._to_response(entry, similarity=sim) for entry, sim in results]

    async def list_entries(
        self,
        *,
        tenant_id: str,
        user_id: str,
        scope: str | None = None,
        agent_key: str | None = None,
        session_id: str | None = None,
        search_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MemoryEntryResponse], int]:
        entries, total = await self.repo.list_entries(
            tenant_id=tenant_id,
            user_id=user_id,
            scope=scope,
            agent_key=agent_key,
            session_id=session_id,
            search_text=search_text,
            limit=limit,
            offset=offset,
        )
        return [self._to_response(entry) for entry in entries], total

    async def delete(
        self,
        *,
        entry_id: str,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        deleted = await self.repo.delete(
            entry_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if deleted:
            await self.db.commit()
        return deleted

    async def update(
        self,
        *,
        entry_id: str,
        tenant_id: str,
        user_id: str,
        content: str | None = None,
        scope: str | None = None,
        agent_key: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        update_metadata: bool = False,
    ) -> MemoryEntryResponse | None:
        """Partial update. Re-embeds only when content changes. Returns None if ACL miss."""
        existing = await self.repo.get_by_id(
            entry_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if existing is None:
            return None

        new_content: str | None = None
        if content is not None:
            new_content = content.strip()
            if not new_content:
                raise ValueError("content must not be empty")

        content_changed = new_content is not None and new_content != existing.content.strip()

        clear_agent_key = False
        clear_session_id = False
        next_agent_key: str | None = None
        next_session_id: str | None = None

        if scope is not None:
            if scope == MemoryScope.USER.value:
                clear_agent_key = True
                clear_session_id = True
            elif scope == MemoryScope.AGENT.value:
                if not agent_key:
                    raise ValueError("agentKey is required when scope is agent")
                next_agent_key = agent_key
                clear_session_id = True
            elif scope == MemoryScope.SESSION.value:
                if not session_id:
                    raise ValueError("sessionId is required when scope is session")
                next_session_id = session_id
                clear_agent_key = True
            else:
                raise ValueError(f"Invalid scope: {scope}")

        embedding: list[float] | None = None
        if content_changed and new_content is not None:
            embedding = await (await self._embedder_for(tenant_id, user_id)).embed(new_content)

        entry = await self.repo.update(
            entry_id,
            tenant_id=tenant_id,
            user_id=user_id,
            content=new_content,
            scope=scope,
            agent_key=next_agent_key,
            session_id=next_session_id,
            clear_agent_key=clear_agent_key,
            clear_session_id=clear_session_id,
            metadata=metadata,
            update_metadata=update_metadata,
            embedding=embedding,
        )
        if entry is None:
            return None

        await self.db.commit()
        return self._to_response(entry)

    @staticmethod
    def _to_response(
        entry: MemoryEntry,
        *,
        similarity: float | None = None,
    ) -> MemoryEntryResponse:
        return MemoryEntryResponse(
            id=entry.id,
            content=entry.content,
            scope=entry.scope,
            agentKey=entry.agent_key,
            sessionId=entry.session_id,
            source=entry.source,
            metadata=entry.entry_metadata,
            similarity=similarity,
            createdAt=entry.created_at,
            updatedAt=entry.updated_at,
        )
