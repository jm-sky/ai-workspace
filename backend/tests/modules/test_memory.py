"""Tests for memory embedding utilities and update lifecycle."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.modules.memory.db_models import MemoryEntry
from app.modules.memory.repositories import MemoryRepository
from app.modules.memory.schemas import MemoryEntryUpdate
from app.common.embeddings import EmbeddingService
from app.modules.memory.services.memory_service import MemoryService
from app.modules.memory.types import MemoryScope
from app.modules.tenants.service import TenantContext


def test_vector_to_pg_literal():
    vector = [0.1, 0.2, 0.3]
    literal = EmbeddingService.vector_to_pg_literal(vector)
    assert literal == "[0.10000000,0.20000000,0.30000000]"


def test_scope_filter_sql_with_agent_and_session():
    sql = MemoryRepository._scope_filter_sql("github-workspace", "run-1")
    assert "agent_key = :agent_key" in sql
    assert "session_id = :session_id" in sql
    assert "IS NULL" not in sql


def test_scope_filter_sql_without_optional_filters():
    sql = MemoryRepository._scope_filter_sql(None, None)
    assert "scope = 'agent'" in sql
    assert "scope = 'session'" in sql
    assert "agent_key =" not in sql
    assert "session_id =" not in sql


def test_memory_entry_update_requires_field():
    with pytest.raises(ValidationError):
        MemoryEntryUpdate()


def test_memory_entry_update_accepts_content_only():
    payload = MemoryEntryUpdate(content="Updated fact")
    assert payload.content == "Updated fact"
    assert payload.scope is None


def _make_entry(
    *,
    entry_id: str = "mem-1",
    content: str = "Old fact",
    scope: str = "user",
    agent_key: str | None = None,
    session_id: str | None = None,
) -> MemoryEntry:
    now = datetime.now(UTC)
    return MemoryEntry(
        id=entry_id,
        tenant_id="tenant-a",
        user_id="user-a",
        scope=scope,
        agent_key=agent_key,
        session_id=session_id,
        content=content,
        source="user",
        entry_metadata=None,
        created_at=now,
        updated_at=now,
    )


def _tenant_ctx(tenant_id: str = "tenant-a", user_id: str = "user-a") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, user_id=user_id, tenant_role="member")


@pytest.mark.asyncio
async def test_update_entry_reembeds_when_content_changes():
    existing = _make_entry()
    updated = _make_entry(content="New fact")
    db = AsyncMock()
    service = MemoryService(db)
    service.repo = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=existing)
    service.repo.update = AsyncMock(return_value=updated)
    embedder = MagicMock()
    embedder.embed = AsyncMock(return_value=[0.1, 0.2])
    service._embedding = embedder

    result = await service.update_entry(
        tenant_ctx=_tenant_ctx(),
        entry_id="mem-1",
        content="New fact",
    )

    assert result is not None
    assert result.content == "New fact"
    embedder.embed.assert_awaited_once_with("New fact")
    call_kwargs = service.repo.update.await_args.kwargs
    assert call_kwargs["embedding"] == [0.1, 0.2]
    assert call_kwargs["content"] == "New fact"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_entry_skips_embed_when_only_scope_changes():
    existing = _make_entry(scope="user")
    updated = _make_entry(scope="agent", agent_key="github-workspace")
    db = AsyncMock()
    service = MemoryService(db)
    service.repo = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=existing)
    service.repo.update = AsyncMock(return_value=updated)
    embedder = MagicMock()
    embedder.embed = AsyncMock(return_value=[0.1])
    service._embedding = embedder

    result = await service.update_entry(
        tenant_ctx=_tenant_ctx(),
        entry_id="mem-1",
        scope=MemoryScope.AGENT.value,
        agent_key="github-workspace",
    )

    assert result is not None
    embedder.embed.assert_not_awaited()
    call_kwargs = service.repo.update.await_args.kwargs
    assert call_kwargs["embedding"] is None
    assert call_kwargs["scope"] == "agent"
    assert call_kwargs["agent_key"] == "github-workspace"
    assert call_kwargs["clear_session_id"] is True


@pytest.mark.asyncio
async def test_update_entry_acl_miss_returns_none():
    db = AsyncMock()
    service = MemoryService(db)
    service.repo = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=None)
    embedder = MagicMock()
    embedder.embed = AsyncMock()
    service._embedding = embedder

    result = await service.update_entry(
        tenant_ctx=_tenant_ctx(tenant_id="other", user_id="other"),
        entry_id="mem-1",
        content="Hacked",
    )

    assert result is None
    embedder.embed.assert_not_awaited()
    service.repo.update.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_entry_agent_scope_requires_agent_key():
    existing = _make_entry()
    db = AsyncMock()
    service = MemoryService(db)
    service.repo = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=existing)

    with pytest.raises(ValueError, match="agentKey"):
        await service.update_entry(
            tenant_ctx=_tenant_ctx(),
            entry_id="mem-1",
            scope=MemoryScope.AGENT.value,
        )


@pytest.mark.asyncio
async def test_memory_update_tool_validation_errors():
    from app.modules.agent.tools.memory import MemoryUpdateTool

    tool = MemoryUpdateTool(
        tenant_ctx=_tenant_ctx(),
        db=AsyncMock(),
        agent_key="github-workspace",
        session_id="sess-1",
    )

    assert await tool.execute({}) == {"error": "id is required"}
    assert await tool.execute({"id": "mem-1"}) == {
        "error": "at least one of content or scope is required"
    }


@pytest.mark.asyncio
async def test_memory_update_tool_not_found():
    from app.modules.agent.tools.memory import MemoryUpdateTool

    tool = MemoryUpdateTool(
        tenant_ctx=_tenant_ctx(),
        db=AsyncMock(),
        agent_key="github-workspace",
    )
    with patch.object(
        tool.memory_service,
        "update_entry",
        new=AsyncMock(return_value=None),
    ):
        result = await tool.execute({"id": "missing", "content": "x"})
    assert result == {"error": "Memory not found"}


@pytest.mark.asyncio
async def test_memory_update_tool_disabled():
    from app.modules.agent.tools.memory import MemoryUpdateTool

    tool = MemoryUpdateTool(
        tenant_ctx=_tenant_ctx(),
        db=AsyncMock(),
        agent_key="github-workspace",
    )
    with patch("app.modules.agent.tools.memory.settings") as mock_settings:
        mock_settings.ai.memory_enabled = False
        result = await tool.execute({"id": "mem-1", "content": "x"})
    assert result == {"updated": False, "message": "Memory is disabled"}


@pytest.mark.asyncio
async def test_create_entry_saves_when_no_similar_entry_exists():
    db = AsyncMock()
    service = MemoryService(db)
    service.repo = MagicMock()
    service.repo.search_similar = AsyncMock(return_value=[])
    service.repo.create = AsyncMock(return_value=_make_entry(entry_id="mem-new"))
    service._embedding = MagicMock()
    service._embedding.embed = AsyncMock(return_value=[0.1, 0.2])

    entry, duplicate_of = await service.create_entry(tenant_ctx=_tenant_ctx(), content="New fact")

    assert duplicate_of is None
    assert entry.id == "mem-new"
    service.repo.create.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_entry_dedupes_against_near_identical_content():
    db = AsyncMock()
    service = MemoryService(db)
    service.repo = MagicMock()
    existing = _make_entry(entry_id="mem-existing", content="The sky is blue")
    service.repo.search_similar = AsyncMock(return_value=[(existing, 0.97)])
    service.repo.create = AsyncMock()
    service._embedding = MagicMock()
    service._embedding.embed = AsyncMock(return_value=[0.1, 0.2])

    entry, duplicate_of = await service.create_entry(tenant_ctx=_tenant_ctx(), content="The sky is blue")

    assert duplicate_of == "mem-existing"
    assert entry.id == "mem-existing"
    service.repo.create.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_memory_save_tool_reports_duplicate():
    from app.modules.agent.tools.memory import MemorySaveTool

    tool = MemorySaveTool(tenant_ctx=_tenant_ctx(), db=AsyncMock(), agent_key="github-workspace")
    tool.memory_service = MagicMock()
    tool.memory_service.create_entry = AsyncMock(
        return_value=(MagicMock(id="mem-existing", scope="user"), "mem-existing")
    )

    result = await tool.execute({"content": "The sky is blue"})

    assert result["saved"] is False
    assert result["duplicateOf"] == "mem-existing"


@pytest.mark.asyncio
async def test_memory_save_tool_saved_when_not_duplicate():
    from app.modules.agent.tools.memory import MemorySaveTool

    tool = MemorySaveTool(tenant_ctx=_tenant_ctx(), db=AsyncMock(), agent_key="github-workspace")
    tool.memory_service = MagicMock()
    tool.memory_service.create_entry = AsyncMock(
        return_value=(MagicMock(id="mem-new", scope="user"), None)
    )

    result = await tool.execute({"content": "A brand new fact"})

    assert result == {"saved": True, "id": "mem-new", "scope": "user"}
