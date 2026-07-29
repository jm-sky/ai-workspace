"""Tests for usage metering, quotas, and guards."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.billing.entitlements import get_plan_entitlements
from app.modules.usage.guard import UsageGuard
from app.modules.usage.quota_resolver import _min_optional_float, _min_optional_int
from app.modules.usage.recorder import extract_cost_from_usage
from app.modules.usage.types import FundingSource
from app.modules.tenants.service import TenantContext


def test_min_optional_float():
    assert _min_optional_float(10.0, 5.0) == 5.0
    assert _min_optional_float(10.0, None) == 10.0


def test_min_optional_int():
    assert _min_optional_int(100, 50) == 50
    assert _min_optional_int(None, 50) == 50


def test_extract_cost_fallback_when_no_api_cost():
    usage = MagicMock()
    usage.model_dump.return_value = {"prompt_tokens": 10, "completion_tokens": 5}
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    api_cost, billed = extract_cost_from_usage(
        usage,
        model="unknown/model",
        prompt_tokens=10,
        completion_tokens=5,
    )
    assert api_cost is None
    assert billed == 0.0


@pytest.mark.asyncio
async def test_guard_byok_skips_platform_cap():
    db = AsyncMock()
    guard = UsageGuard(db)
    tenant_ctx = TenantContext(user_id="u1", tenant_id="t1", tenant_role="owner")

    with patch(
        "app.modules.usage.guard.resolve_funding",
        new_callable=AsyncMock,
        return_value=MagicMock(source=FundingSource.BYOK, api_key="sk-byok"),
    ):
        await guard.assert_agent_run_allowed(tenant_ctx)


@pytest.mark.asyncio
async def test_guard_blocks_zero_included_platform():
    db = AsyncMock()
    guard = UsageGuard(db)
    tenant_ctx = TenantContext(user_id="u1", tenant_id="t1", tenant_role="owner")
    period = MagicMock()
    period.start = datetime.now(UTC)
    period.end = datetime.now(UTC)
    quota = MagicMock()
    quota.period = period
    quota.monthly_included_usd = 0.0
    quota.funding_requires_byok = True

    with (
        patch(
            "app.modules.usage.guard.resolve_funding",
            new_callable=AsyncMock,
            return_value=MagicMock(source=FundingSource.PLATFORM, api_key="sk"),
        ),
        patch.object(guard.quota_resolver, "resolve", new_callable=AsyncMock, return_value=quota),
        patch.object(guard.repo, "get_period_total", new_callable=AsyncMock, return_value=(0.0, 0)),
    ):
        from app.modules.usage.exceptions import UsageLimitExceededError

        with pytest.raises(UsageLimitExceededError):
            await guard.assert_agent_run_allowed(tenant_ctx)


def test_plan_entitlements_pro_includes_usd():
    ent = get_plan_entitlements("pro")
    assert ent.monthly_included_usd == 1.0
    assert ent.requires_byok is False
