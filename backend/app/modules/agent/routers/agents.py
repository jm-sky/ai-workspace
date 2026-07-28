"""List + tenant-admin CRUD for agent definitions."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.agent.db_models import AgentDB
from app.modules.agent.dependencies import AgentTenantContext
from app.modules.agent.schemas import (
    AgentAdminListResponse,
    AgentCreateRequest,
    AgentDetail,
    AgentListResponse,
    AgentSummary,
    AgentUpdateRequest,
)
from app.modules.agent.services.agent_definition_service import (
    AgentDefinitionError,
    AgentDefinitionService,
)
from app.modules.auth.dependencies import CurrentUser
from app.modules.tenants.repositories import TenantRepository, get_tenant_repository
from app.modules.tenants.service import TenantContext

router = APIRouter(tags=["agent-definitions"])

TOOL_BUCKETS = ("github", "gmail", "jira", "gitlab", "memory", "rag", "wiki", "web")


def _get_agent_def_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentDefinitionService:
    return AgentDefinitionService(db)


def _require_tenant_agent_admin(tenant_ctx: TenantContext, role: str) -> None:
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant owner or admin can manage agents",
        )


def _to_summary(row: AgentDB) -> AgentSummary:
    return AgentSummary(
        key=row.key,
        name=row.name,
        description=row.description or "",
        isDefault=bool(row.is_default),
        toolProfile=list(row.tool_profile or []),
    )


def _to_detail(row: AgentDB) -> AgentDetail:
    return AgentDetail(
        id=row.id,
        key=row.key,
        name=row.name,
        description=row.description or "",
        systemPrompt=row.system_prompt,
        model=row.model,
        effort=row.effort,
        toolProfile=list(row.tool_profile or []),
        memoryScopes=list(row.memory_scopes or []),
        ragEnabled=bool(row.rag_enabled),
        routingHints=dict(row.routing_hints or {}),
        isEnabled=bool(row.is_enabled),
        isDefault=bool(row.is_default),
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


async def _resolve_membership_role(
    tenant_ctx: TenantContext,
    tenant_repo: TenantRepository,
) -> str:
    membership = await tenant_repo.get_membership(tenant_ctx.tenant_id, tenant_ctx.user_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a tenant member",
        )
    return membership.role


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[AgentDefinitionService, Depends(_get_agent_def_service)],
) -> AgentListResponse:
    """Return enabled agents for the chat picker (meta only)."""
    _ = current_user
    rows = await service.list_summaries(tenant_ctx.tenant_id, enabled_only=True)
    return AgentListResponse(agents=[_to_summary(row) for row in rows])


@router.get("/agents/manage", response_model=AgentAdminListResponse)
async def list_agents_admin(
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[AgentDefinitionService, Depends(_get_agent_def_service)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> AgentAdminListResponse:
    """Full agent list for tenant admin editor."""
    _ = current_user
    role = await _resolve_membership_role(tenant_ctx, tenant_repo)
    _require_tenant_agent_admin(tenant_ctx, role)
    rows = await service.list_all(tenant_ctx.tenant_id)
    return AgentAdminListResponse(agents=[_to_detail(row) for row in rows])


@router.get("/agents/manage/{agent_id}", response_model=AgentDetail)
async def get_agent_admin(
    agent_id: str,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[AgentDefinitionService, Depends(_get_agent_def_service)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> AgentDetail:
    _ = current_user
    role = await _resolve_membership_role(tenant_ctx, tenant_repo)
    _require_tenant_agent_admin(tenant_ctx, role)
    row = await service.get_by_id(tenant_ctx.tenant_id, agent_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _to_detail(row)


@router.post("/agents", response_model=AgentDetail, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreateRequest,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[AgentDefinitionService, Depends(_get_agent_def_service)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> AgentDetail:
    role = await _resolve_membership_role(tenant_ctx, tenant_repo)
    _require_tenant_agent_admin(tenant_ctx, role)
    _validate_tool_profile(payload.toolProfile)
    try:
        row = await service.create(
            tenant_id=tenant_ctx.tenant_id,
            key=payload.key,
            name=payload.name,
            description=payload.description,
            system_prompt=payload.systemPrompt,
            model=payload.model,
            effort=payload.effort,
            tool_profile=payload.toolProfile,
            memory_scopes=payload.memoryScopes,
            rag_enabled=payload.ragEnabled,
            routing_hints=payload.routingHints,
            is_enabled=payload.isEnabled,
            is_default=payload.isDefault,
            created_by=current_user.id,
        )
    except AgentDefinitionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_detail(row)


@router.patch("/agents/{agent_id}", response_model=AgentDetail)
async def update_agent(
    agent_id: str,
    payload: AgentUpdateRequest,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[AgentDefinitionService, Depends(_get_agent_def_service)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> AgentDetail:
    _ = current_user
    role = await _resolve_membership_role(tenant_ctx, tenant_repo)
    _require_tenant_agent_admin(tenant_ctx, role)
    row = await service.get_by_id(tenant_ctx.tenant_id, agent_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    data = payload.model_dump(exclude_unset=True, by_alias=False)
    if "toolProfile" in data and data["toolProfile"] is not None:
        _validate_tool_profile(data["toolProfile"])

    # Map camelCase keys from dump to service kwargs
    kwargs: dict[str, Any] = {}
    field_map = {
        "name": "name",
        "description": "description",
        "systemPrompt": "system_prompt",
        "model": "model",
        "effort": "effort",
        "toolProfile": "tool_profile",
        "memoryScopes": "memory_scopes",
        "ragEnabled": "rag_enabled",
        "routingHints": "routing_hints",
        "isEnabled": "is_enabled",
        "isDefault": "is_default",
    }
    for src, dest in field_map.items():
        if src in data:
            kwargs[dest] = data[src]

    try:
        row = await service.update(row, **kwargs)
    except AgentDefinitionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_detail(row)


@router.post("/agents/{agent_id}/set-default", response_model=AgentDetail)
async def set_default_agent(
    agent_id: str,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[AgentDefinitionService, Depends(_get_agent_def_service)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> AgentDetail:
    _ = current_user
    role = await _resolve_membership_role(tenant_ctx, tenant_repo)
    _require_tenant_agent_admin(tenant_ctx, role)
    row = await service.get_by_id(tenant_ctx.tenant_id, agent_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    row = await service.set_default(row)
    return _to_detail(row)


def _validate_tool_profile(profile: list[str]) -> None:
    unknown = [p for p in profile if p not in TOOL_BUCKETS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown tool buckets: {', '.join(unknown)}",
        )
