"""Plan entitlements catalog (shared by billing UI and usage limits)."""

from dataclasses import dataclass
from typing import Literal

PlanTier = Literal["free", "pro", "pro_plus"]


@dataclass(frozen=True)
class PlanEntitlements:
    """Included AI workspace capabilities per subscription tier."""

    plan_tier: PlanTier
    monthly_included_usd: float
    monthly_token_soft_cap: int | None
    web_search_monthly_cap: int | None
    requires_byok: bool
    can_use_advanced_features: bool
    # Gear-stack legacy limits (billing /limits endpoint)
    ai_monthly_token_limit: int
    storage_limit_bytes: int
    items_limit: int
    containers_limit: int
    can_export_data: bool


PLAN_ENTITLEMENTS: dict[PlanTier, PlanEntitlements] = {
    "free": PlanEntitlements(
        plan_tier="free",
        monthly_included_usd=0.0,
        monthly_token_soft_cap=None,
        web_search_monthly_cap=0,
        requires_byok=True,
        can_use_advanced_features=False,
        ai_monthly_token_limit=0,
        storage_limit_bytes=100 * 1024 * 1024,
        items_limit=2000,
        containers_limit=100,
        can_export_data=True,
    ),
    "pro": PlanEntitlements(
        plan_tier="pro",
        monthly_included_usd=1.0,
        monthly_token_soft_cap=1_000_000,
        web_search_monthly_cap=500,
        requires_byok=False,
        can_use_advanced_features=True,
        ai_monthly_token_limit=1_000_000,
        storage_limit_bytes=5 * 1024 * 1024 * 1024,
        items_limit=10000,
        containers_limit=250,
        can_export_data=True,
    ),
    "pro_plus": PlanEntitlements(
        plan_tier="pro_plus",
        monthly_included_usd=10.0,
        monthly_token_soft_cap=10_000_000,
        web_search_monthly_cap=None,
        requires_byok=False,
        can_use_advanced_features=True,
        ai_monthly_token_limit=10_000_000,
        storage_limit_bytes=50 * 1024 * 1024 * 1024,
        items_limit=50000,
        containers_limit=500,
        can_export_data=True,
    ),
}


def get_plan_entitlements(plan_tier: str) -> PlanEntitlements:
    """Return entitlements for a tier, defaulting to free."""
    return PLAN_ENTITLEMENTS.get(plan_tier, PLAN_ENTITLEMENTS["free"])
