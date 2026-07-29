"""Usage summary business logic."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenants.service import TenantContext
from app.modules.usage.quota_resolver import EffectiveQuotaResolver
from app.modules.usage.repository import UsageRepository
from app.modules.usage.types import UsagePurposeGroup


@dataclass(frozen=True)
class PurposeBreakdownRow:
    purpose: str
    cost_usd: float
    tokens: int


@dataclass(frozen=True)
class UsageSummary:
    period_start: object
    period_end: object
    plan_tier: str
    monthly_included_usd: float
    used_usd: float
    web_search_used: int
    web_search_cap: int | None
    breakdown: list[PurposeBreakdownRow]


class UsageSummaryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.quota_resolver = EffectiveQuotaResolver(db)
        self.repo = UsageRepository(db)

    async def get_summary(self, tenant_ctx: TenantContext) -> UsageSummary:
        quota = await self.quota_resolver.resolve(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            team_id=tenant_ctx.team_id,
        )
        period = quota.period
        used_usd, _ = await self.repo.get_period_total(
            tenant_id=tenant_ctx.tenant_id,
            period_start=period.start,
            period_end=period.end,
            purpose_group=UsagePurposeGroup.PLATFORM,
        )
        _, web_used = await self.repo.get_period_total(
            tenant_id=tenant_ctx.tenant_id,
            period_start=period.start,
            period_end=period.end,
            purpose_group=UsagePurposeGroup.WEB_SEARCH,
        )
        breakdown_rows = await self.repo.breakdown_by_purpose(
            tenant_id=tenant_ctx.tenant_id,
            period_start=period.start,
            period_end=period.end,
        )
        return UsageSummary(
            period_start=period.start,
            period_end=period.end,
            plan_tier=period.plan_tier,
            monthly_included_usd=quota.monthly_included_usd,
            used_usd=used_usd,
            web_search_used=web_used,
            web_search_cap=quota.monthly_web_search_cap,
            breakdown=[
                PurposeBreakdownRow(purpose=p, cost_usd=c, tokens=t)
                for p, c, t in breakdown_rows
            ],
        )
