"""Agent definition service — CRUD + resolve for runtime."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.db_models import AgentDB
from app.modules.agent.exceptions import AgentNotConfiguredError
from app.modules.agent.registry import BUILTIN_AGENTS, AgentDefinition, get_default_agent_key
from app.modules.agent.repositories.agent_repository import AgentRepository

AGENT_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class AgentDefinitionError(Exception):
    """Validation / conflict for agent definitions."""


class AgentDefinitionService:
    """Tenant-scoped agent definitions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AgentRepository(db)

    @staticmethod
    def to_definition(row: AgentDB) -> AgentDefinition:
        return AgentDefinition(
            key=row.key,
            name=row.name,
            description=row.description or "",
            system_prompt=row.system_prompt,
            tool_profile=tuple(row.tool_profile or ()),
            memory_scopes=tuple(row.memory_scopes or ("session", "user", "agent")),
            rag_enabled=bool(row.rag_enabled),
            model=row.model,
            effort=row.effort,
            routing_hints=dict(row.routing_hints or {}),
            is_default=bool(row.is_default),
            is_enabled=bool(row.is_enabled),
        )

    async def list_summaries(self, tenant_id: str, *, enabled_only: bool = True) -> list[AgentDB]:
        rows = await self.repo.list_for_tenant(tenant_id, enabled_only=enabled_only)
        if rows:
            return rows
        # Bootstrap gap: seed builtins then re-list
        await self.seed_builtins_for_tenant(tenant_id)
        await self.db.commit()
        return await self.repo.list_for_tenant(tenant_id, enabled_only=enabled_only)

    async def list_all(self, tenant_id: str) -> list[AgentDB]:
        rows = await self.repo.list_for_tenant(tenant_id, enabled_only=False)
        if not rows:
            await self.seed_builtins_for_tenant(tenant_id)
            await self.db.commit()
            rows = await self.repo.list_for_tenant(tenant_id, enabled_only=False)
        return rows

    async def require_definition(self, tenant_id: str, key: str) -> AgentDefinition:
        row = await self.repo.get_by_key(tenant_id, key)
        if row is None:
            # Try seed once for existing tenants created before migration
            await self.seed_builtins_for_tenant(tenant_id)
            await self.db.commit()
            row = await self.repo.get_by_key(tenant_id, key)
        if row is None or not row.is_enabled:
            raise AgentNotConfiguredError(f"Unknown agent: {key}")
        return self.to_definition(row)

    async def get_default_key(self, tenant_id: str) -> str:
        row = await self.repo.get_default(tenant_id)
        if row:
            return row.key
        await self.seed_builtins_for_tenant(tenant_id)
        await self.db.commit()
        row = await self.repo.get_default(tenant_id)
        return row.key if row else get_default_agent_key()

    async def get_by_id(self, tenant_id: str, agent_id: str) -> AgentDB | None:
        return await self.repo.get_by_id(agent_id, tenant_id=tenant_id)

    async def create(
        self,
        *,
        tenant_id: str,
        key: str,
        name: str,
        description: str = "",
        system_prompt: str,
        model: str | None = None,
        effort: str | None = None,
        tool_profile: list[str] | None = None,
        memory_scopes: list[str] | None = None,
        rag_enabled: bool = False,
        routing_hints: dict[str, Any] | None = None,
        is_enabled: bool = True,
        is_default: bool = False,
        created_by: str | None = None,
    ) -> AgentDB:
        self._validate_key(key)
        if not name.strip():
            raise AgentDefinitionError("name is required")
        if not system_prompt.strip():
            raise AgentDefinitionError("system_prompt is required")

        if is_default:
            await self.repo.clear_default(tenant_id)

        try:
            agent = await self.repo.create(
                tenant_id=tenant_id,
                key=key.strip(),
                name=name.strip(),
                description=description.strip(),
                system_prompt=system_prompt,
                model=model,
                effort=effort,
                tool_profile=tool_profile,
                memory_scopes=memory_scopes,
                rag_enabled=rag_enabled,
                routing_hints=routing_hints,
                is_enabled=is_enabled,
                is_default=is_default,
                created_by=created_by,
            )
            await self.db.commit()
            await self.db.refresh(agent)
            return agent
        except IntegrityError as exc:
            await self.db.rollback()
            raise AgentDefinitionError(f"Agent key already exists: {key}") from exc

    async def update(
        self,
        agent: AgentDB,
        *,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        model: str | None = ...,  # type: ignore[assignment]
        effort: str | None = ...,  # type: ignore[assignment]
        tool_profile: list[str] | None = None,
        memory_scopes: list[str] | None = None,
        rag_enabled: bool | None = None,
        routing_hints: dict[str, Any] | None = None,
        is_enabled: bool | None = None,
        is_default: bool | None = None,
    ) -> AgentDB:
        if name is not None:
            if not name.strip():
                raise AgentDefinitionError("name is required")
            agent.name = name.strip()
        if description is not None:
            agent.description = description.strip()
        if system_prompt is not None:
            if not system_prompt.strip():
                raise AgentDefinitionError("system_prompt is required")
            agent.system_prompt = system_prompt
        if model is not ...:
            agent.model = model
        if effort is not ...:
            agent.effort = effort
        if tool_profile is not None:
            agent.tool_profile = tool_profile
        if memory_scopes is not None:
            agent.memory_scopes = memory_scopes
        if rag_enabled is not None:
            agent.rag_enabled = rag_enabled
        if routing_hints is not None:
            agent.routing_hints = routing_hints
        if is_enabled is not None:
            agent.is_enabled = is_enabled
        if is_default is True:
            await self.repo.clear_default(agent.tenant_id, except_id=agent.id)
            agent.is_default = True
        elif is_default is False:
            agent.is_default = False

        await self.repo.touch(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def set_default(self, agent: AgentDB) -> AgentDB:
        await self.repo.clear_default(agent.tenant_id, except_id=agent.id)
        agent.is_default = True
        agent.is_enabled = True
        await self.repo.touch(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def seed_builtins_for_tenant(self, tenant_id: str, *, created_by: str | None = None) -> int:
        """Insert missing built-in agents for a tenant. Idempotent."""
        created = 0
        for builtin in BUILTIN_AGENTS.values():
            existing = await self.repo.get_by_key(tenant_id, builtin.key)
            if existing is not None:
                continue
            if builtin.is_default:
                await self.repo.clear_default(tenant_id)
            await self.repo.create(
                tenant_id=tenant_id,
                key=builtin.key,
                name=builtin.name,
                description=builtin.description,
                system_prompt=builtin.system_prompt,
                model=builtin.model,
                effort=builtin.effort,
                tool_profile=list(builtin.tool_profile),
                memory_scopes=list(builtin.memory_scopes),
                rag_enabled=builtin.rag_enabled,
                routing_hints=dict(builtin.routing_hints or {}),
                is_enabled=builtin.is_enabled,
                is_default=builtin.is_default,
                created_by=created_by,
            )
            created += 1
        return created

    @staticmethod
    def _validate_key(key: str) -> None:
        if not key or len(key) > 100 or not AGENT_KEY_PATTERN.match(key):
            raise AgentDefinitionError(
                "key must be a lowercase slug (a-z, 0-9, hyphens), max 100 chars"
            )
