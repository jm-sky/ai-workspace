"""Memory tools for the agent loop (search + save + update)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.agent.tools.base import AgentTool, AgentToolDefinition
from app.modules.memory.services.memory_service import MemoryService
from app.modules.memory.types import MemoryScope, MemorySource
from app.modules.tenants.service import TenantContext


class MemorySearchTool(AgentTool):
    """Semantic search over user memories."""

    def __init__(
        self,
        *,
        tenant_ctx: TenantContext,
        db: AsyncSession,
        agent_key: str,
        session_id: str | None = None,
    ):
        self.tenant_ctx = tenant_ctx
        self.memory_service = MemoryService(db)
        self.agent_key = agent_key
        self.session_id = session_id

    @property
    def definition(self) -> AgentToolDefinition:
        return AgentToolDefinition(
            name="memory_search",
            description=("Search stored memories semantically. Use when prior context, " "preferences, or facts may help answer the user."),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["user", "agent", "session"],
                        "description": "Optional scope filter",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 5)",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not settings.ai.memory_enabled:
            return {"memories": [], "message": "Memory is disabled"}

        query = str(arguments.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}

        limit = int(arguments.get("limit") or 5)
        scope = arguments.get("scope")

        results = await self.memory_service.search(
            tenant_ctx=self.tenant_ctx,
            query=query,
            agent_key=self.agent_key,
            session_id=self.session_id,
            scope=scope,
            limit=min(limit, 20),
        )
        return {
            "total": len(results),
            "memories": [
                {
                    "id": item.id,
                    "content": item.content,
                    "scope": item.scope,
                    "similarity": item.similarity,
                }
                for item in results
            ],
        }


class MemorySaveTool(AgentTool):
    """Persist a fact or note to long-term memory."""

    def __init__(
        self,
        *,
        tenant_ctx: TenantContext,
        db: AsyncSession,
        agent_key: str,
        session_id: str | None = None,
    ):
        self.tenant_ctx = tenant_ctx
        self.memory_service = MemoryService(db)
        self.agent_key = agent_key
        self.session_id = session_id

    @property
    def definition(self) -> AgentToolDefinition:
        return AgentToolDefinition(
            name="memory_save",
            description=("Save an important fact, preference, or note to memory for future sessions. " "Use scope 'user' for personal facts, 'agent' for agent-specific context, " "'session' for this chat only."),
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Concise memory to store (one fact per call)",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["user", "agent", "session"],
                        "description": "Memory scope (default user)",
                    },
                },
                "required": ["content"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not settings.ai.memory_enabled:
            return {"saved": False, "message": "Memory is disabled"}

        content = str(arguments.get("content", "")).strip()
        if not content:
            return {"error": "content is required"}

        scope = str(arguments.get("scope") or MemoryScope.USER.value)
        agent_key = self.agent_key if scope == MemoryScope.AGENT.value else None
        session_id = self.session_id if scope == MemoryScope.SESSION.value else None

        entry, duplicate_of = await self.memory_service.create_entry(
            tenant_ctx=self.tenant_ctx,
            content=content,
            scope=scope,
            agent_key=agent_key,
            session_id=session_id,
            source=MemorySource.AGENT.value,
        )
        if duplicate_of is not None:
            return {
                "saved": False,
                "duplicateOf": duplicate_of,
                "message": "Near-identical memory already exists; use memory_update to refine it instead.",
            }
        return {"saved": True, "id": entry.id, "scope": entry.scope}


class MemoryUpdateTool(AgentTool):
    """Update an existing memory entry (correct or refine a fact)."""

    def __init__(
        self,
        *,
        tenant_ctx: TenantContext,
        db: AsyncSession,
        agent_key: str,
        session_id: str | None = None,
    ):
        self.tenant_ctx = tenant_ctx
        self.memory_service = MemoryService(db)
        self.agent_key = agent_key
        self.session_id = session_id

    @property
    def definition(self) -> AgentToolDefinition:
        return AgentToolDefinition(
            name="memory_update",
            description=(
                "Update an existing memory by id after memory_search. "
                "Use to correct or refine a fact instead of saving a duplicate."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Memory entry id from memory_search",
                    },
                    "content": {
                        "type": "string",
                        "description": "Updated memory text",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["user", "agent", "session"],
                        "description": "Optional new scope",
                    },
                },
                "required": ["id"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not settings.ai.memory_enabled:
            return {"updated": False, "message": "Memory is disabled"}

        entry_id = str(arguments.get("id", "")).strip()
        if not entry_id:
            return {"error": "id is required"}

        content_raw = arguments.get("content")
        content = str(content_raw).strip() if content_raw is not None else None
        if content_raw is not None and not content:
            return {"error": "content must not be empty"}

        scope = arguments.get("scope")
        if scope is not None:
            scope = str(scope)

        if content is None and scope is None:
            return {"error": "at least one of content or scope is required"}

        agent_key = self.agent_key if scope == MemoryScope.AGENT.value else None
        session_id = self.session_id if scope == MemoryScope.SESSION.value else None

        try:
            entry = await self.memory_service.update_entry(
                tenant_ctx=self.tenant_ctx,
                entry_id=entry_id,
                content=content,
                scope=scope,
                agent_key=agent_key,
                session_id=session_id,
            )
        except ValueError as exc:
            return {"error": str(exc)}

        if entry is None:
            return {"error": "Memory not found"}

        return {
            "updated": True,
            "id": entry.id,
            "scope": entry.scope,
            "content": entry.content,
        }
