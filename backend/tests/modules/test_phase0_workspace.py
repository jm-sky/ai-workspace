"""Tests for Phase 0: workspace config cascade, tenant context, integration tokens."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from app.modules.auth.auth_utils import create_access_token, verify_token
from app.modules.auth.models import User
from app.modules.integrations.crypto import (
    decrypt_integration_token,
    encrypt_integration_token,
)
from app.modules.integrations.service import IntegrationTokenService
from app.modules.tenants.db_models import TenantDB, TenantMembershipDB
from app.modules.tenants.service import TenantWorkspaceService
from app.modules.workspace_config.resolver import WorkspaceConfigResolver
from app.modules.workspace_config.types import ConfigKey


def _config_entry(key: str, value):
    entry = MagicMock()
    entry.config_key = key
    entry.config_value = value
    return entry


def _patch_workspace_defaults(
    monkeypatch,
    *,
    allowed_models: list[str],
    default_model: str = "",
    max_tokens: int | None = 32000,
    rag_enabled: bool = False,
    tools_enabled: bool = True,
    web_search_enabled: bool = True,
):
    prefix = "app.modules.workspace_config.resolver.settings.workspace"
    monkeypatch.setattr(f"{prefix}.default_allowed_models", allowed_models)
    monkeypatch.setattr(f"{prefix}.default_model", default_model)
    monkeypatch.setattr(f"{prefix}.default_max_tokens", max_tokens)
    monkeypatch.setattr(f"{prefix}.default_rag_enabled", rag_enabled)
    monkeypatch.setattr(f"{prefix}.default_tools_enabled", tools_enabled)
    monkeypatch.setattr(f"{prefix}.default_web_search_enabled", web_search_enabled)


class TestWorkspaceConfigResolver:
    """Cascade resolver unit tests."""

    @pytest.mark.asyncio
    async def test_intersects_allowed_models_and_applies_ceiling(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_allowed_models",
            ["model-a", "model-b", "model-c"],
        )
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_model",
            "model-a",
        )
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_max_tokens",
            32000,
        )
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_rag_enabled",
            True,
        )
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_tools_enabled",
            True,
        )

        repo = AsyncMock()
        repo.get_entries_for_scope.side_effect = [
            [],
            [_config_entry(ConfigKey.ALLOWED_MODELS.value, ["model-a", "model-b"])],
            [_config_entry(ConfigKey.ALLOWED_MODELS.value, ["model-b"])],
            [_config_entry(ConfigKey.DEFAULT_MODEL.value, "model-b")],
        ]

        resolver = WorkspaceConfigResolver(repo)
        result = await resolver.resolve(
            user_id="user-1",
            tenant_id="tenant-1",
            team_id="team-1",
        )

        assert result.allowedModels == ["model-b"]
        assert result.defaultModel == "model-b"
        assert result.maxTokens == 32000
        assert result.ragEnabled is True
        assert result.toolsEnabled is True

    @pytest.mark.asyncio
    async def test_empty_app_allow_list_means_no_ceiling(self, monkeypatch):
        """An empty app-level list must not clamp the tenant's choice to nothing."""
        _patch_workspace_defaults(monkeypatch, allowed_models=[], default_model="model-z")

        repo = AsyncMock()
        repo.get_entries_for_scope.side_effect = [[], [], [], []]

        result = await WorkspaceConfigResolver(repo).resolve(
            user_id="user-1",
            tenant_id="tenant-1",
        )

        assert result.allowedModels == []
        # The default survives instead of being clamped away to None.
        assert result.defaultModel == "model-z"

    @pytest.mark.asyncio
    async def test_tenant_defines_the_set_when_app_sets_no_ceiling(self, monkeypatch):
        _patch_workspace_defaults(monkeypatch, allowed_models=[], default_model="model-a")

        repo = AsyncMock()
        # No team_id below, so only app / tenant / user scopes are queried.
        repo.get_entries_for_scope.side_effect = [
            [],
            [_config_entry(ConfigKey.ALLOWED_MODELS.value, ["model-a", "model-b"])],
            [_config_entry(ConfigKey.ALLOWED_MODELS.value, ["model-b"])],
        ]

        result = await WorkspaceConfigResolver(repo).resolve(
            user_id="user-1",
            tenant_id="tenant-1",
        )

        # Tenant defines the set, user narrows it further.
        assert result.allowedModels == ["model-b"]
        assert result.defaultModel == "model-b"

    @pytest.mark.asyncio
    async def test_tools_disabled_when_team_turns_off(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_allowed_models",
            ["model-a"],
        )
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_tools_enabled",
            True,
        )
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_rag_enabled",
            False,
        )
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_max_tokens",
            None,
        )
        monkeypatch.setattr(
            "app.modules.workspace_config.resolver.settings.workspace.default_model",
            "",
        )

        repo = AsyncMock()
        repo.get_entries_for_scope.side_effect = [
            [],
            [],
            [_config_entry(ConfigKey.TOOLS_ENABLED.value, False)],
            [],
        ]

        resolver = WorkspaceConfigResolver(repo)
        result = await resolver.resolve(
            user_id="user-1",
            tenant_id="tenant-1",
            team_id="team-1",
        )

        assert result.toolsEnabled is False


class TestTenantWorkspaceService:
    """Tenant switching and workspace claims."""

    @pytest.fixture
    def user(self) -> User:
        return User(
            id="user-1",
            email="u@example.com",
            name="User",
            hashedPassword="hash",
            isActive=True,
            isEmailVerified=True,
            createdAt=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_auto_select_single_tenant(self, user: User):
        tenant = TenantDB(
            id="tenant-1",
            name="Acme",
            description=None,
            owner_id="user-1",
            created_at=datetime.now(UTC),
        )
        membership = TenantMembershipDB(
            tenant_id="tenant-1",
            user_id="user-1",
            role="owner",
            created_at=datetime.now(UTC),
        )

        tenant_repo = AsyncMock()
        tenant_repo.list_for_user.return_value = [(tenant, membership)]
        team_repo = AsyncMock()
        user_repo = AsyncMock()
        user_repo.set_active_workspace.return_value = user

        service = TenantWorkspaceService(tenant_repo, team_repo, user_repo)
        workspace = await service.resolve_workspace_for_user(user)

        assert workspace is not None
        assert workspace.tenant_id == "tenant-1"
        assert workspace.tenant_role == "owner"
        user_repo.set_active_workspace.assert_awaited_once_with("user-1", "tenant-1", None)

    @pytest.mark.asyncio
    async def test_ensure_personal_workspace_creates_tenant(self, user: User):
        tenant = TenantDB(
            id="tenant-new",
            name="User's Workspace",
            description=None,
            owner_id="user-1",
            created_at=datetime.now(UTC),
        )
        membership = TenantMembershipDB(
            tenant_id="tenant-new",
            user_id="user-1",
            role="owner",
            created_at=datetime.now(UTC),
        )

        tenant_repo = AsyncMock()
        tenant_repo.list_for_user.return_value = []
        tenant_repo.create_tenant.return_value = (tenant, membership)
        team_repo = AsyncMock()
        user_repo = AsyncMock()

        service = TenantWorkspaceService(tenant_repo, team_repo, user_repo)
        workspace = await service.ensure_personal_workspace(user)

        assert workspace is not None
        assert workspace.tenant_id == "tenant-new"
        tenant_repo.create_tenant.assert_awaited_once()
        user_repo.set_active_workspace.assert_awaited_once_with("user-1", "tenant-new", None)

    @pytest.mark.asyncio
    async def test_workspace_claims_include_team(self, user: User):
        service = TenantWorkspaceService(AsyncMock(), AsyncMock(), AsyncMock())
        from app.modules.tenants.service import TenantContext

        claims = service.workspace_claims(
            TenantContext(
                user_id="user-1",
                tenant_id="tenant-1",
                tenant_role="admin",
                team_id="team-1",
            )
        )

        assert claims == {"tid": "tenant-1", "trol": "admin", "tmid": "team-1"}

    def test_access_token_carries_tenant_claims(self):
        token = create_access_token(data={"sub": "user-1", "tid": "tenant-1", "trol": "owner", "tmid": "team-1"})
        payload = verify_token(token)
        assert payload["tid"] == "tenant-1"
        assert payload["trol"] == "owner"
        assert payload["tmid"] == "team-1"


class TestIntegrationTokenService:
    """Integration OAuth token vault."""

    def test_encrypt_decrypt_roundtrip(self, monkeypatch):
        test_key = Fernet.generate_key().decode()
        monkeypatch.setattr(
            "app.modules.integrations.crypto.settings.integrations.token_encryption_key",
            test_key,
        )

        encrypted = encrypt_integration_token("access-token-xyz")
        assert decrypt_integration_token(encrypted) == "access-token-xyz"

    @pytest.mark.asyncio
    async def test_get_access_token_decrypts(self, monkeypatch):
        test_key = Fernet.generate_key().decode()
        monkeypatch.setattr(
            "app.modules.integrations.crypto.settings.integrations.token_encryption_key",
            test_key,
        )

        token_row = MagicMock()
        token_row.expires_at = None
        token_row.encrypted_refresh_token = None
        token_row.encrypted_access_token = encrypt_integration_token("secret-token")

        repo = MagicMock()
        repo.find_user_scoped = AsyncMock(return_value=token_row)
        repo.decrypt_access_token.return_value = "secret-token"

        service = IntegrationTokenService(repo)
        result = await service.get_access_token("user-1", "jira")

        assert result == "secret-token"

    @pytest.mark.asyncio
    async def test_resolve_access_token_prefers_personal(self, monkeypatch):
        test_key = Fernet.generate_key().decode()
        monkeypatch.setattr(
            "app.modules.integrations.crypto.settings.integrations.token_encryption_key",
            test_key,
        )

        personal = MagicMock()
        personal.expires_at = None
        personal.encrypted_refresh_token = None
        personal.encrypted_access_token = encrypt_integration_token("personal-token")
        personal.provider = "github"

        team = MagicMock()
        team.expires_at = None
        team.encrypted_refresh_token = None
        team.encrypted_access_token = encrypt_integration_token("team-token")

        repo = MagicMock()
        repo.find_user_scoped = AsyncMock(return_value=personal)
        repo.find_team_scoped = AsyncMock(return_value=team)
        repo.find_tenant_scoped = AsyncMock(return_value=None)
        repo.decrypt_access_token.side_effect = lambda row: ("personal-token" if row is personal else "team-token")

        service = IntegrationTokenService(repo)
        result = await service.resolve_access_token(
            user_id="user-1",
            tenant_id="tenant-1",
            team_id="team-1",
            provider="github",
        )

        assert result == "personal-token"
        repo.find_team_scoped.assert_not_called()


class TestWebSearchCascade:
    """web_search_enabled narrows like rag_enabled: any level can only turn it off."""

    @pytest.mark.asyncio
    async def test_on_by_default_when_no_scope_overrides(self, monkeypatch):
        _patch_workspace_defaults(monkeypatch, allowed_models=[])
        repo = AsyncMock()
        repo.get_entries_for_scope.side_effect = [[], [], [], []]

        result = await WorkspaceConfigResolver(repo).resolve(
            user_id="user-1",
            tenant_id="tenant-1",
            team_id="team-1",
        )

        assert result.webSearchEnabled is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scope_index", [1, 2, 3], ids=["tenant", "team", "user"])
    async def test_any_scope_can_disable_it(self, monkeypatch, scope_index):
        _patch_workspace_defaults(monkeypatch, allowed_models=[])
        entries: list[list] = [[], [], [], []]
        entries[scope_index] = [_config_entry(ConfigKey.WEB_SEARCH_ENABLED.value, False)]

        repo = AsyncMock()
        repo.get_entries_for_scope.side_effect = entries

        result = await WorkspaceConfigResolver(repo).resolve(
            user_id="user-1",
            tenant_id="tenant-1",
            team_id="team-1",
        )

        assert result.webSearchEnabled is False

    @pytest.mark.asyncio
    async def test_a_lower_scope_cannot_re_enable_it(self, monkeypatch):
        """AND-narrowing: a user cannot opt back into what the tenant switched off."""
        _patch_workspace_defaults(monkeypatch, allowed_models=[])
        repo = AsyncMock()
        repo.get_entries_for_scope.side_effect = [
            [],
            [_config_entry(ConfigKey.WEB_SEARCH_ENABLED.value, False)],
            [],
            [_config_entry(ConfigKey.WEB_SEARCH_ENABLED.value, True)],
        ]

        result = await WorkspaceConfigResolver(repo).resolve(
            user_id="user-1",
            tenant_id="tenant-1",
            team_id="team-1",
        )

        assert result.webSearchEnabled is False

    @pytest.mark.asyncio
    async def test_app_level_off_wins_over_everything(self, monkeypatch):
        _patch_workspace_defaults(monkeypatch, allowed_models=[], web_search_enabled=False)
        repo = AsyncMock()
        repo.get_entries_for_scope.side_effect = [
            [],
            [_config_entry(ConfigKey.WEB_SEARCH_ENABLED.value, True)],
            [],
            [],
        ]

        result = await WorkspaceConfigResolver(repo).resolve(
            user_id="user-1",
            tenant_id="tenant-1",
            team_id="team-1",
        )

        assert result.webSearchEnabled is False
