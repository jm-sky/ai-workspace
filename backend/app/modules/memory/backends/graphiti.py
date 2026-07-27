"""Graphiti memory backend — temporal knowledge graph via FalkorDB.

Spike implementation for plan 011 stage 2 gate evaluation.
Requires: pip install graphiti-core
"""

from typing import Any

try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodeType

    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False

from app.modules.memory.schemas import MemoryEntryResponse
from app.modules.memory.types import MemoryScope


def _require_graphiti() -> None:
    if not GRAPHITI_AVAILABLE:
        raise ImportError(
            "graphiti-core is not installed. "
            "Install it with: pip install graphiti-core\n"
            "FalkorDB must also be running (see docker-compose.graphiti.yml)."
        )


class GraphitiMemoryBackend:
    """MemoryBackend backed by Graphiti (temporal knowledge graph on FalkorDB).

    Minimal implementation for the spike: ``create`` and ``search`` are
    functional; ``update``, ``delete``, and ``list_entries`` raise
    ``NotImplementedError`` (Graphiti manages facts through episode
    ingestion, not row-level CRUD).

    ``group_id`` = ``f"{tenant_id}:{user_id}"`` — hard isolation boundary.
    ``MemoryScope`` is stored as an episode attribute for filtering.
    """

    def __init__(
        self,
        *,
        bolt_url: str = "bolt://localhost:6383",
        llm_client: Any | None = None,
        embedder: Any | None = None,
    ):
        _require_graphiti()
        self._bolt_url = bolt_url
        self._llm_client = llm_client
        self._embedder = embedder
        self._client: Any | None = None

    @staticmethod
    def _group_id(tenant_id: str, user_id: str) -> str:
        return f"{tenant_id}:{user_id}"

    async def _get_client(self) -> Any:
        """Lazy-init Graphiti client."""
        if self._client is None:
            _require_graphiti()
            self._client = Graphiti(
                self._bolt_url,
                llm_client=self._llm_client,
                embedder=self._embedder,
            )
            await self._client.build_indices_and_constraints()
        return self._client

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
        """Ingest content as an episode into Graphiti."""
        client = await self._get_client()
        group_id = self._group_id(tenant_id, user_id)

        episode_body = content
        source_description = f"memory/{scope}"
        if agent_key:
            source_description += f"/{agent_key}"

        episode = await client.add_episode(
            name=f"memory-{source}",
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description=source_description,
            group_id=group_id,
            reference_time=None,
        )

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        entry = MemoryEntryResponse(
            id=str(getattr(episode, "uuid", "graphiti-episode")),
            content=content,
            scope=scope,
            agentKey=agent_key,
            sessionId=session_id,
            source=source,
            metadata=metadata,
            similarity=None,
            createdAt=now,
            updatedAt=now,
        )
        return entry, None

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
        """Search Graphiti for relevant facts."""
        client = await self._get_client()
        group_id = self._group_id(tenant_id, user_id)

        results = await client.search(
            query=query,
            group_ids=[group_id],
            num_results=limit,
        )

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        entries: list[MemoryEntryResponse] = []
        for fact in results:
            fact_text = getattr(fact, "fact", None) or getattr(fact, "content", str(fact))
            score = getattr(fact, "score", None)
            entries.append(
                MemoryEntryResponse(
                    id=str(getattr(fact, "uuid", "unknown")),
                    content=str(fact_text),
                    scope=scope or MemoryScope.USER.value,
                    source="graphiti",
                    similarity=float(score) if score is not None else None,
                    createdAt=now,
                    updatedAt=now,
                )
            )
        return entries

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
        raise NotImplementedError(
            "Graphiti updates facts via new episodes, not row-level UPDATE. "
            "Re-ingest corrected content as a new episode instead."
        )

    async def delete(
        self,
        *,
        entry_id: str,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        raise NotImplementedError(
            "Graphiti manages fact lifecycle through temporal invalidation, "
            "not explicit DELETE. Use episode-based correction instead."
        )

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
        raise NotImplementedError(
            "Graphiti does not support paginated listing. "
            "Use search instead."
        )

    async def close(self) -> None:
        """Clean up Graphiti client resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None
