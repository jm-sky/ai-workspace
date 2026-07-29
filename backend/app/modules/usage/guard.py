"""Preflight checks against effective quotas."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.exceptions import FreeTrierRequiresBYOKError
from app.modules.tenants.service import TenantContext
from app.modules.usage.billing_period import resolve_funding
from app.modules.usage.exceptions import UsageLimitExceededError
from app.modules.usage.quota_resolver import EffectiveQuotaResolver
from app.modules.usage.repository import UsageRepository
from app.modules.usage.types import FundingSource, UsagePurposeGroup


class UsageGuard:
    """Enforce platform usage limits before expensive OpenRouter calls."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.quota_resolver = EffectiveQuotaResolver(db)
        self.repo = UsageRepository(db)

    async def assert_agent_run_allowed(self, tenant_ctx: TenantContext) -> None:
        funding = await resolve_funding(
            self.db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            platform_api_key="",
        )
        if funding.source == FundingSource.BYOK:
            return

        quota = await self.quota_resolver.resolve(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            team_id=tenant_ctx.team_id,
        )
        if quota.funding_requires_byok and funding.api_key is None:
            raise FreeTrierRequiresBYOKError("Free tier users must provide OpenRouter API token")

        period = quota.period
        used_cost, _ = await self.repo.get_period_total(
            tenant_id=tenant_ctx.tenant_id,
            period_start=period.start,
            period_end=period.end,
            purpose_group=UsagePurposeGroup.PLATFORM,
        )
        limit = quota.monthly_included_usd
        if limit <= 0:
            raise UsageLimitExceededError()
        if used_cost >= limit:
            raise UsageLimitExceededError()

    async def assert_embedding_allowed(self, tenant_ctx: TenantContext) -> None:
        await self.assert_agent_run_allowed(tenant_ctx)

    async def is_web_search_allowed(self, tenant_ctx: TenantContext) -> bool:
        funding = await resolve_funding(
            self.db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            platform_api_key="",
        )
        if funding.source == FundingSource.BYOK:
            return True

        quota = await self.quota_resolver.resolve(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            team_id=tenant_ctx.team_id,
        )
        cap = quota.monthly_web_search_cap
        if cap is None:
            return True
        if cap <= 0:
            return False

        period = quota.period
        _, used_ops = await self.repo.get_period_total(
            tenant_id=tenant_ctx.tenant_id,
            period_start=period.start,
            period_end=period.end,
            purpose_group=UsagePurposeGroup.WEB_SEARCH,
        )
        return used_ops < cap
