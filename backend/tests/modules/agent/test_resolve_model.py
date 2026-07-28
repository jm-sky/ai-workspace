"""Tests for agent model resolution against the workspace allow-list."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.agent.exceptions import (
    AgentNotConfiguredError,
    AgentToolsDisabledError,
)
from app.modules.agent.services.agent_run_service import AgentRunService
from app.modules.ai.utils.models_config import (
    clear_catalog_snapshot,
    set_catalog_snapshot,
)
from app.modules.workspace_config.types import EffectiveWorkspaceConfig

CURATED = "openai/gpt-4o-mini"
LIVE_ONLY = "mistralai/mistral-medium-3-5"


@pytest.fixture(autouse=True)
def _reset_snapshot():
    clear_catalog_snapshot()
    yield
    clear_catalog_snapshot()


def _service(effective: EffectiveWorkspaceConfig) -> AgentRunService:
    service = AgentRunService(db=MagicMock(), token_service=MagicMock())
    service.config_resolver = MagicMock()
    service.config_resolver.resolve = AsyncMock(return_value=effective)
    return service


async def _resolve(effective: EffectiveWorkspaceConfig, requested: str | None) -> str:
    model, _rag_enabled, _web_search_enabled = await _service(effective)._resolve_model(
        user_id="user-1",
        tenant_ctx=MagicMock(tenant_id="tenant-1", team_id=None),
        requested_model=requested,
    )
    return model


class TestNoCeiling:
    """An empty allowedModels list means the whole catalog is available."""

    @pytest.mark.asyncio
    async def test_honours_requested_model_outside_curated_list(self):
        """The regression this change exists to fix: no silent substitution."""
        set_catalog_snapshot([{"id": LIVE_ONLY, "cost_per_1m_input": 1.5, "cost_per_1m_output": 7.5}])
        config = EffectiveWorkspaceConfig(allowedModels=[], defaultModel=CURATED)

        assert await _resolve(config, LIVE_ONLY) == LIVE_ONLY

    @pytest.mark.asyncio
    async def test_falls_back_to_default_model(self):
        config = EffectiveWorkspaceConfig(allowedModels=[], defaultModel=CURATED)
        assert await _resolve(config, None) == CURATED

    @pytest.mark.asyncio
    async def test_rejects_model_the_catalog_does_not_know(self):
        set_catalog_snapshot([{"id": LIVE_ONLY}])
        config = EffectiveWorkspaceConfig(allowedModels=[], defaultModel=CURATED)

        with pytest.raises(AgentNotConfiguredError):
            await _resolve(config, "typo/not-a-model")

    @pytest.mark.asyncio
    async def test_passes_model_through_when_the_catalog_is_cold(self):
        """A failed warm-up must degrade, not reject every non-curated model."""
        config = EffectiveWorkspaceConfig(allowedModels=[], defaultModel=CURATED)
        assert await _resolve(config, LIVE_ONLY) == LIVE_ONLY

    @pytest.mark.asyncio
    async def test_rejects_when_nothing_is_configured(self):
        config = EffectiveWorkspaceConfig(allowedModels=[], defaultModel=None)
        with pytest.raises(AgentNotConfiguredError):
            await _resolve(config, None)


class TestWithCeiling:
    """A non-empty allowedModels list still narrows, exactly as before."""

    @pytest.mark.asyncio
    async def test_allows_model_on_the_list(self):
        config = EffectiveWorkspaceConfig(allowedModels=[CURATED, "a/b"], defaultModel="a/b")
        assert await _resolve(config, CURATED) == CURATED

    @pytest.mark.asyncio
    async def test_substitutes_model_off_the_list(self):
        """Governance still wins over the request when a ceiling is set."""
        set_catalog_snapshot([{"id": LIVE_ONLY}])
        config = EffectiveWorkspaceConfig(allowedModels=["a/b"], defaultModel="a/b")

        assert await _resolve(config, LIVE_ONLY) == "a/b"


@pytest.mark.asyncio
async def test_tools_disabled_short_circuits():
    config = EffectiveWorkspaceConfig(allowedModels=[], toolsEnabled=False)
    with pytest.raises(AgentToolsDisabledError):
        await _resolve(config, CURATED)
