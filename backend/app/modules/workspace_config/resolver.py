"""Cascade resolver for workspace configuration."""

from typing import Any

from app.core.config import settings
from app.modules.workspace_config.repositories import WorkspaceConfigRepository
from app.modules.workspace_config.types import (
    ConfigKey,
    ConfigScope,
    EffectiveWorkspaceConfig,
)


def _entries_to_map(entries: list) -> dict[str, Any]:
    return {entry.config_key: entry.config_value for entry in entries}


def _intersect_models(base: list[str] | None, override: list[str] | None) -> list[str] | None:
    """Narrow an allow-list by one cascade level.

    `None` means "no ceiling at this level yet" — the first level that declares
    an allow-list defines the set; every level below can only narrow it.
    """
    if override is None:
        return base
    if base is None:
        return list(override)
    override_set = set(override)
    return [model for model in base if model in override_set]


def _min_int(base: int | None, override: int | None) -> int | None:
    if base is None:
        return override
    if override is None:
        return base
    return min(base, override)


def _and_bool(base: bool, override: bool | None) -> bool:
    if override is None:
        return base
    return base and override


class WorkspaceConfigResolver:
    """Resolves effective config from app → tenant → team → user cascade."""

    def __init__(self, repo: WorkspaceConfigRepository):
        self.repo = repo

    def _app_defaults(self) -> EffectiveWorkspaceConfig:
        ws = settings.workspace
        return EffectiveWorkspaceConfig(
            allowedModels=list(ws.default_allowed_models),
            defaultModel=ws.default_model or None,
            maxTokens=ws.default_max_tokens,
            ragEnabled=ws.default_rag_enabled,
            toolsEnabled=ws.default_tools_enabled,
            webSearchEnabled=ws.default_web_search_enabled,
        )

    async def resolve(
        self,
        *,
        user_id: str,
        tenant_id: str,
        team_id: str | None = None,
    ) -> EffectiveWorkspaceConfig:
        app_entries = await self.repo.get_entries_for_scope(scope=ConfigScope.APP, scope_id=None)
        tenant_entries = await self.repo.get_entries_for_scope(scope=ConfigScope.TENANT, scope_id=tenant_id)
        team_entries: list = []
        if team_id:
            team_entries = await self.repo.get_entries_for_scope(scope=ConfigScope.TEAM, scope_id=team_id)
        user_entries = await self.repo.get_entries_for_scope(
            scope=ConfigScope.USER,
            scope_id=user_id,
            tenant_id=tenant_id,
        )

        app_map = _entries_to_map(app_entries)
        tenant_map = _entries_to_map(tenant_entries)
        team_map = _entries_to_map(team_entries)
        user_map = _entries_to_map(user_entries)

        base = self._app_defaults()

        # An empty app-level allow-list means "no ceiling": the whole catalog is
        # available unless a tenant/team/user narrows it.
        allowed: list[str] | None = base.allowedModels or None
        allowed = _intersect_models(allowed, tenant_map.get(ConfigKey.ALLOWED_MODELS.value))
        allowed = _intersect_models(allowed, team_map.get(ConfigKey.ALLOWED_MODELS.value))
        allowed = _intersect_models(allowed, user_map.get(ConfigKey.ALLOWED_MODELS.value))

        default_model = user_map.get(ConfigKey.DEFAULT_MODEL.value) or team_map.get(ConfigKey.DEFAULT_MODEL.value) or tenant_map.get(ConfigKey.DEFAULT_MODEL.value) or app_map.get(ConfigKey.DEFAULT_MODEL.value) or base.defaultModel
        if allowed is not None and default_model and default_model not in allowed:
            default_model = allowed[0] if allowed else None

        max_tokens = base.maxTokens
        max_tokens = _min_int(max_tokens, tenant_map.get(ConfigKey.MAX_TOKENS.value))
        max_tokens = _min_int(max_tokens, team_map.get(ConfigKey.MAX_TOKENS.value))
        max_tokens = _min_int(max_tokens, user_map.get(ConfigKey.MAX_TOKENS.value))

        rag_enabled = base.ragEnabled
        rag_enabled = _and_bool(rag_enabled, tenant_map.get(ConfigKey.RAG_ENABLED.value))
        rag_enabled = _and_bool(rag_enabled, team_map.get(ConfigKey.RAG_ENABLED.value))
        rag_enabled = _and_bool(rag_enabled, user_map.get(ConfigKey.RAG_ENABLED.value))

        tools_enabled = base.toolsEnabled
        tools_enabled = _and_bool(tools_enabled, tenant_map.get(ConfigKey.TOOLS_ENABLED.value))
        tools_enabled = _and_bool(tools_enabled, team_map.get(ConfigKey.TOOLS_ENABLED.value))
        tools_enabled = _and_bool(tools_enabled, user_map.get(ConfigKey.TOOLS_ENABLED.value))

        web_search_enabled = base.webSearchEnabled
        web_search_enabled = _and_bool(web_search_enabled, tenant_map.get(ConfigKey.WEB_SEARCH_ENABLED.value))
        web_search_enabled = _and_bool(web_search_enabled, team_map.get(ConfigKey.WEB_SEARCH_ENABLED.value))
        web_search_enabled = _and_bool(web_search_enabled, user_map.get(ConfigKey.WEB_SEARCH_ENABLED.value))

        return EffectiveWorkspaceConfig(
            allowedModels=allowed or [],
            defaultModel=default_model,
            maxTokens=max_tokens,
            ragEnabled=rag_enabled,
            toolsEnabled=tools_enabled,
            webSearchEnabled=web_search_enabled,
        )
