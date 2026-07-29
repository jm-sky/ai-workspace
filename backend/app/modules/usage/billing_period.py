"""Resolve billing periods and funding source for usage."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.db_models import UserDB
from app.modules.billing.entitlements import PlanEntitlements, get_plan_entitlements
from app.modules.billing.repository import BillingRepository
from app.modules.tenants.db_models import TenantDB
from app.modules.usage.types import FundingSource


@dataclass(frozen=True)
class BillingPeriod:
    start: datetime
    end: datetime
    plan_tier: str
    entitlements: PlanEntitlements
    billing_owner_user_id: str


def calendar_month_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    """UTC calendar month [start, end)."""
    now = now or datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


async def resolve_billing_period(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> BillingPeriod:
    """Interim: plan tier from tenant owner's subscription; period from Stripe or calendar month."""
    tenant = await db.get(TenantDB, tenant_id)
    if tenant is None:
        raise ValueError(f"Unknown tenant: {tenant_id}")

    owner_id = tenant.owner_id
    billing_repo = BillingRepository(db)
    subscription = await billing_repo.get_subscription_by_user_id(owner_id)
    plan_tier = subscription.plan_tier if subscription else "free"

    if subscription and subscription.current_period_start and subscription.current_period_end:
        period_start = subscription.current_period_start
        period_end = subscription.current_period_end
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=UTC)
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=UTC)
    else:
        period_start, period_end = calendar_month_period()

    return BillingPeriod(
        start=period_start,
        end=period_end,
        plan_tier=plan_tier,
        entitlements=get_plan_entitlements(plan_tier),
        billing_owner_user_id=owner_id,
    )


@dataclass(frozen=True)
class FundingResolution:
    source: FundingSource
    api_key: str | None
    requires_platform_pool: bool


async def resolve_funding(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    platform_api_key: str,
) -> FundingResolution:
    """Choose platform vs BYOK key and whether usage counts against tenant pool."""
    period = await resolve_billing_period(db, tenant_id=tenant_id)
    entitlements = period.entitlements

    if entitlements.requires_byok:
        user = await db.get(UserDB, user_id)
        token = user.openrouter_api_token if user else None
        if token:
            return FundingResolution(
                source=FundingSource.BYOK,
                api_key=token,
                requires_platform_pool=False,
            )
        return FundingResolution(
            source=FundingSource.PLATFORM,
            api_key=platform_api_key or None,
            requires_platform_pool=True,
        )

    return FundingResolution(
        source=FundingSource.PLATFORM,
        api_key=platform_api_key or None,
        requires_platform_pool=True,
    )
