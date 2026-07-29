"""Billing service layer for business logic."""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from .exceptions import (
    CannotDowngradeGrandfatheredError,
    FreeTrierRequiresBYOKError,
    InvalidBillingIntervalError,
    InvalidPlanTierError,
    StripeAPIError,
    StripeCustomerNotFoundError,
    StripeSubscriptionNotFoundError,
    SubscriptionNotFoundError,
)
from .repository import BillingRepository
from .schemas import (
    CheckoutSessionResponse,
    PortalSessionResponse,
    SubscriptionLimitsResponse,
    SubscriptionResponse,
)
from .stripe_client import StripeClient

logger = logging.getLogger(__name__)


class BillingService:
    """Service class for billing and subscription operations."""

    def __init__(self, repository: BillingRepository, stripe_client: StripeClient):
        """
        Initialize billing service.

        Args:
            repository: Billing repository instance
            stripe_client: Stripe client instance
        """
        self.repository = repository
        self.stripe_client = stripe_client

    async def get_subscription(self, user_id: str) -> SubscriptionResponse:
        """
        Get user's subscription details.

        If subscription doesn't exist, automatically creates a FREE tier subscription.

        Args:
            user_id: User ID

        Returns:
            Subscription response
        """
        subscription = await self.repository.get_subscription_by_user_id(user_id)

        # Auto-create FREE subscription for new users
        if not subscription:
            logger.info(f"Creating default FREE subscription for user {user_id}")
            subscription = await self.repository.create_subscription(
                user_id=user_id,
                plan_tier="free",
                status="active",
            )

        return SubscriptionResponse.model_validate(subscription)

    async def create_checkout_session(
        self,
        user_id: str,
        plan_tier: str,
        billing_interval: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSessionResponse:
        """
        Create a Stripe Checkout session for subscription purchase.

        Args:
            user_id: User ID
            plan_tier: Subscription plan tier (pro or business)
            billing_interval: Billing interval (monthly or annual)
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled

        Returns:
            Checkout session response with session ID and URL

        Raises:
            InvalidPlanTierError: If plan tier is invalid
            InvalidBillingIntervalError: If billing interval is invalid
            SubscriptionAlreadyExistsError: If user already has paid subscription
            StripeAPIError: If Stripe API call fails
        """
        # Validate plan tier
        if plan_tier not in ["pro", "pro_plus"]:
            raise InvalidPlanTierError(f"Invalid plan tier: {plan_tier}")

        # Validate billing interval
        if billing_interval not in ["monthly", "annual"]:
            raise InvalidBillingIntervalError(f"Invalid billing interval: {billing_interval}")

        # Check if user already has a subscription
        subscription = await self.repository.get_subscription_by_user_id(user_id)

        # If user has active paid subscription, cancel it first to allow upgrade/downgrade
        if subscription and subscription.plan_tier in ["pro", "pro_plus"] and subscription.status == "active":
            logger.info(f"User {user_id} changing from {subscription.plan_tier} to {plan_tier}, canceling old subscription")

            # Cancel old Stripe subscription if it exists
            if subscription.stripe_subscription_id:
                try:
                    await self.stripe_client.cancel_subscription(subscription.stripe_subscription_id, cancel_at_period_end=False)  # Cancel immediately
                    logger.info(f"Canceled Stripe subscription {subscription.stripe_subscription_id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel old Stripe subscription: {e}")

            # Downgrade to free in database (will be upgraded after successful payment)
            await self.repository.update_subscription(
                subscription.id,
                plan_tier="free",
                billing_interval=None,
                status="active",
                stripe_subscription_id=None,
            )

        # Get or create Stripe customer
        if subscription and subscription.stripe_customer_id:
            customer_id = subscription.stripe_customer_id
        else:
            try:
                # Create Stripe customer (email will be fetched from user record in router)
                customer = await self.stripe_client.create_customer(user_id=user_id, email="", name="")
                customer_id = customer.id

                # Update subscription with customer ID
                if subscription:
                    await self.repository.update_subscription(
                        subscription.id,
                        stripe_customer_id=customer_id,
                    )
                else:
                    # Create initial subscription record
                    subscription = await self.repository.create_subscription(
                        user_id=user_id,
                        stripe_customer_id=customer_id,
                        plan_tier="free",
                        status="active",
                    )
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {e}")
                raise StripeAPIError(f"Failed to create Stripe customer: {e}") from e

        # Get price ID based on plan and billing interval
        price_id = self._get_price_id(plan_tier, billing_interval)

        # Create checkout session
        try:
            session = await self.stripe_client.create_checkout_session(
                customer_id=customer_id,
                price_id=price_id,
                success_url=success_url,
                cancel_url=cancel_url,
            )

            if not session.url:
                raise StripeAPIError("Checkout session created but URL is missing")

            logger.info(f"Created checkout session {session.id} for user {user_id}")
            return CheckoutSessionResponse(sessionId=session.id, sessionUrl=session.url)
        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise StripeAPIError(f"Failed to create checkout session: {e}") from e

    async def create_portal_session(self, user_id: str, return_url: str) -> PortalSessionResponse:
        """
        Create a Stripe Billing Portal session for subscription management.

        Args:
            user_id: User ID
            return_url: URL to redirect after portal session

        Returns:
            Portal session response with session URL

        Raises:
            SubscriptionNotFoundError: If subscription doesn't exist
            StripeCustomerNotFoundError: If Stripe customer doesn't exist
            StripeAPIError: If Stripe API call fails
        """
        subscription = await self.repository.get_subscription_by_user_id(user_id)
        if not subscription:
            raise SubscriptionNotFoundError(f"Subscription not found for user {user_id}")

        if not subscription.stripe_customer_id:
            raise StripeCustomerNotFoundError(f"Stripe customer not found for user {user_id}")

        # Grandfathered users cannot access portal (they have lifetime access)
        if subscription.is_grandfathered:
            raise CannotDowngradeGrandfatheredError("Grandfathered users have lifetime access and cannot modify their subscription")

        try:
            session = await self.stripe_client.create_portal_session(
                customer_id=subscription.stripe_customer_id,
                return_url=return_url,
            )

            logger.info(f"Created portal session for user {user_id}")
            return PortalSessionResponse(sessionUrl=session.url)
        except Exception as e:
            logger.error(f"Failed to create portal session: {e}")
            raise StripeAPIError(f"Failed to create portal session: {e}") from e

    async def cancel_subscription(self, user_id: str) -> SubscriptionResponse:
        """
        Cancel user's subscription (at period end).

        Args:
            user_id: User ID

        Returns:
            Updated subscription response

        Raises:
            SubscriptionNotFoundError: If subscription doesn't exist
            StripeSubscriptionNotFoundError: If Stripe subscription doesn't exist
            CannotDowngradeGrandfatheredError: If user is grandfathered
            StripeAPIError: If Stripe API call fails
        """
        subscription = await self.repository.get_subscription_by_user_id(user_id)
        if not subscription:
            raise SubscriptionNotFoundError(f"Subscription not found for user {user_id}")

        if subscription.is_grandfathered:
            raise CannotDowngradeGrandfatheredError("Grandfathered users have lifetime access and cannot cancel")

        if not subscription.stripe_subscription_id:
            raise StripeSubscriptionNotFoundError(f"Stripe subscription not found for user {user_id}")

        try:
            # Cancel subscription at period end
            stripe_sub = await self.stripe_client.cancel_subscription(subscription.stripe_subscription_id)

            # Update database
            updated_subscription = await self.repository.update_subscription(
                subscription.id,
                cancel_at_period_end=True,
                updated_at=datetime.now(UTC),
            )

            # Log history
            await self.repository.create_subscription_history(
                subscription_id=subscription.id,
                change_type="cancellation_scheduled",
                old_value=None,
                new_value=f"cancel_at_period_end={stripe_sub.cancel_at_period_end}",
                reason="User requested cancellation",
            )

            logger.info(f"Cancelled subscription for user {user_id}")
            return SubscriptionResponse.model_validate(updated_subscription)
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise StripeAPIError(f"Failed to cancel subscription: {e}") from e

    async def update_openrouter_token(self, user_id: str, token: str | None) -> SubscriptionResponse:
        """
        Update user's OpenRouter API token (for Free tier BYOK).

        Args:
            user_id: User ID
            token: OpenRouter API token (None to clear)

        Returns:
            Updated subscription response

        Raises:
            SubscriptionNotFoundError: If subscription doesn't exist
        """
        subscription = await self.repository.get_subscription_by_user_id(user_id)
        if not subscription:
            raise SubscriptionNotFoundError(f"Subscription not found for user {user_id}")

        # Update user's OpenRouter token (stored in users table)
        # This is handled in the router by updating the User model
        # Here we just return the subscription

        logger.info(f"Updated OpenRouter token for user {user_id}")
        return SubscriptionResponse.model_validate(subscription)

    async def get_subscription_limits(
        self,
        user_id: str,
        *,
        tenant_id: str | None = None,
        team_id: str | None = None,
        db: AsyncSession | None = None,
    ) -> SubscriptionLimitsResponse:
        """
        Get feature limits for user's subscription plan.

        Args:
            user_id: User ID

        Returns:
            Subscription limits response

        Raises:
            SubscriptionNotFoundError: If subscription doesn't exist
        """
        subscription = await self.repository.get_subscription_by_user_id(user_id)
        if not subscription:
            raise SubscriptionNotFoundError(f"Subscription not found for user {user_id}")

        plan_tier = subscription.plan_tier

        from app.modules.billing.entitlements import get_plan_entitlements
        from typing import Literal, cast

        plan_limits = {
            tier: {
                "aiMonthlyTokenLimit": get_plan_entitlements(tier).ai_monthly_token_limit,
                "storageLimit": get_plan_entitlements(tier).storage_limit_bytes,
                "canExportData": get_plan_entitlements(tier).can_export_data,
                "canUseAdvancedFeatures": get_plan_entitlements(tier).can_use_advanced_features,
                "requiresByok": get_plan_entitlements(tier).requires_byok,
                "itemsLimit": get_plan_entitlements(tier).items_limit,
                "containersLimit": get_plan_entitlements(tier).containers_limit,
            }
            for tier in ("free", "pro", "pro_plus")
        }

        plan_limits_entry = plan_limits.get(plan_tier, plan_limits["free"])
        plan_tier_typed = cast(Literal["free", "pro", "pro_plus"], plan_tier)

        workspace_monthly: float | None = None
        workspace_used: float | None = None
        period_start: datetime | None = None
        period_end: datetime | None = None
        web_used: int | None = None
        web_cap: int | None = None

        if tenant_id and db is not None:
            from app.modules.tenants.service import TenantContext
            from app.modules.usage.service import UsageSummaryService

            summary = await UsageSummaryService(db).get_summary(
                TenantContext(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    tenant_role="member",
                    team_id=team_id,
                )
            )
            workspace_monthly = summary.monthly_included_usd
            workspace_used = summary.used_usd
            period_start = summary.period_start  # type: ignore[assignment]
            period_end = summary.period_end  # type: ignore[assignment]
            web_used = summary.web_search_used
            web_cap = summary.web_search_cap

        return SubscriptionLimitsResponse(
            planTier=plan_tier_typed,
            aiMonthlyTokenLimit=plan_limits_entry["aiMonthlyTokenLimit"],
            storageLimit=plan_limits_entry["storageLimit"],
            canExportData=cast(bool, plan_limits_entry["canExportData"]),
            canUseAdvancedFeatures=cast(bool, plan_limits_entry["canUseAdvancedFeatures"]),
            requiresByok=cast(bool, plan_limits_entry["requiresByok"]),
            itemsLimit=plan_limits_entry["itemsLimit"],
            containersLimit=plan_limits_entry["containersLimit"],
            workspaceMonthlyIncludedUsd=workspace_monthly,
            workspaceUsedUsd=workspace_used,
            workspacePeriodStart=period_start,
            workspacePeriodEnd=period_end,
            webSearchUsed=web_used,
            webSearchCap=web_cap,
        )

    async def check_ai_access(self, user_id: str, openrouter_token: str | None = None) -> bool:
        """
        Check if user has access to AI features.

        Args:
            user_id: User ID
            openrouter_token: User's OpenRouter token (if Free tier)

        Returns:
            True if user has AI access, False otherwise

        Raises:
            FreeTrierRequiresBYOKError: If Free tier user has no token
        """
        subscription = await self.repository.get_subscription_by_user_id(user_id)
        if not subscription:
            return False

        # Paid tiers have AI access
        if subscription.plan_tier in ["pro", "pro_plus"]:
            return True

        # Free tier requires BYOK
        if subscription.plan_tier == "free":
            if not openrouter_token:
                raise FreeTrierRequiresBYOKError("Free tier users must provide OpenRouter API token")
            return True

        return False

    def _get_price_id(self, plan_tier: str, billing_interval: str) -> str:
        """
        Get Stripe price ID for plan tier and billing interval.

        Args:
            plan_tier: Plan tier (pro or business)
            billing_interval: Billing interval (monthly or annual)

        Returns:
            Stripe price ID

        Raises:
            InvalidPlanTierError: If plan tier is invalid
            InvalidBillingIntervalError: If billing interval is invalid
        """
        price_map = {
            "pro": {
                "monthly": settings.stripe.pro_monthly_price_id,
                "annual": settings.stripe.pro_annual_price_id,
            },
            "pro_plus": {
                "monthly": settings.stripe.pro_plus_monthly_price_id,
                "annual": settings.stripe.pro_plus_annual_price_id,
            },
        }

        if plan_tier not in price_map:
            raise InvalidPlanTierError(f"Invalid plan tier: {plan_tier}")

        if billing_interval not in price_map[plan_tier]:
            raise InvalidBillingIntervalError(f"Invalid billing interval: {billing_interval}")

        price_id = price_map[plan_tier][billing_interval]
        if not price_id:
            raise InvalidPlanTierError(f"Price ID not configured for {plan_tier}/{billing_interval}")

        return price_id

    # ---------------------------------------------------------
    # Admin Methods
    # ---------------------------------------------------------

    async def get_all_subscriptions(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get all subscriptions with user information (admin only).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of subscriptions with user details
        """

        from sqlalchemy import select

        from app.modules.auth.db_models import UserDB

        from .db_models import SubscriptionDB

        # Get all subscriptions with user info
        subscriptions = await self.repository.db.execute(select(SubscriptionDB).join(UserDB, SubscriptionDB.user_id == UserDB.id).offset(skip).limit(limit))

        results = []
        for sub in subscriptions.scalars().all():
            # Get user details (user_id is ULID, not UUID)
            user = await self.repository.db.get(UserDB, sub.user_id)

            results.append(
                {
                    "id": str(sub.id),
                    "user_id": sub.user_id,
                    "user_name": user.name if user else None,
                    "user_email": user.email if user else None,
                    "stripe_customer_id": sub.stripe_customer_id,
                    "stripe_subscription_id": sub.stripe_subscription_id,
                    "plan_tier": sub.plan_tier,
                    "billing_interval": sub.billing_interval,
                    "status": sub.status,
                    "current_period_start": sub.current_period_start,
                    "current_period_end": sub.current_period_end,
                    "cancel_at_period_end": sub.cancel_at_period_end,
                    "is_grandfathered": sub.is_grandfathered,
                    "created_at": sub.created_at,
                    "updated_at": sub.updated_at,
                }
            )

        return results

    async def get_subscription_stats(self) -> dict:
        """
        Get subscription statistics (admin only).

        Returns:
            Dictionary with subscription statistics
        """
        from sqlalchemy import func, select

        from .db_models import SubscriptionDB

        # Get all subscriptions
        subscriptions = (await self.repository.db.execute(select(SubscriptionDB))).scalars().all()

        total_subscriptions = len(subscriptions)

        # Count by status
        active_count = sum(1 for s in subscriptions if s.status == "active")
        canceled_count = sum(1 for s in subscriptions if s.status == "canceled")
        past_due_count = sum(1 for s in subscriptions if s.status == "past_due")

        # Count by plan tier
        free_count = sum(1 for s in subscriptions if s.plan_tier == "free")
        pro_count = sum(1 for s in subscriptions if s.plan_tier == "pro")
        pro_plus_count = sum(1 for s in subscriptions if s.plan_tier == "pro_plus")

        # Count grandfathered users
        grandfathered_count = sum(1 for s in subscriptions if s.is_grandfathered)

        # Calculate revenue (rough estimate based on plan tiers and billing intervals)
        monthly_revenue = 0.0
        annual_revenue = 0.0

        for sub in subscriptions:
            if sub.status == "active" and not sub.is_grandfathered:
                if sub.plan_tier == "pro":
                    if sub.billing_interval == "monthly":
                        monthly_revenue += 5.0
                    elif sub.billing_interval == "annual":
                        annual_revenue += 50.0
                elif sub.plan_tier == "pro_plus":
                    if sub.billing_interval == "monthly":
                        monthly_revenue += 15.0
                    elif sub.billing_interval == "annual":
                        annual_revenue += 150.0

        # Get total users count
        from app.modules.auth.db_models import UserDB

        total_users = (await self.repository.db.execute(select(func.count(UserDB.id)))).scalar() or 0

        return {
            "totalUsers": total_users,
            "totalSubscriptions": total_subscriptions,
            "activeSubscriptions": active_count,
            "canceledSubscriptions": canceled_count,
            "pastDueSubscriptions": past_due_count,
            "freeUsers": free_count,
            "proUsers": pro_count,
            "proPlusUsers": pro_plus_count,
            "grandfatheredUsers": grandfathered_count,
            "monthlyRevenue": monthly_revenue,
            "annualRevenue": annual_revenue,
        }

    async def admin_update_subscription(
        self,
        subscription_id: str,
        plan_tier: str | None = None,
        status: str | None = None,
        is_grandfathered: bool | None = None,
        cancel_at_period_end: bool | None = None,
        reason: str | None = None,
    ) -> SubscriptionResponse:
        """
        Admin method to manually update subscription (admin only).

        Args:
            subscription_id: Subscription ID
            plan_tier: New plan tier
            status: New status
            is_grandfathered: Grandfathered flag
            cancel_at_period_end: Cancel at period end flag
            reason: Reason for manual modification

        Returns:
            Updated subscription

        Raises:
            SubscriptionNotFoundError: If subscription not found
            InvalidPlanTierError: If plan tier is invalid
        """
        from uuid import UUID as PyUUID

        # Get subscription
        subscription = await self.repository.get_subscription_by_id(PyUUID(subscription_id))
        if not subscription:
            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found")

        # Track changes for audit log
        changes = []

        # Update fields
        if plan_tier is not None and plan_tier != subscription.plan_tier:
            if plan_tier not in ["free", "pro", "pro_plus"]:
                raise InvalidPlanTierError(f"Invalid plan tier: {plan_tier}")
            changes.append(("plan_tier", subscription.plan_tier, plan_tier))
            subscription.plan_tier = plan_tier

        if status is not None and status != subscription.status:
            changes.append(("status", subscription.status, status))
            subscription.status = status

        if is_grandfathered is not None and is_grandfathered != subscription.is_grandfathered:
            changes.append(
                (
                    "is_grandfathered",
                    str(subscription.is_grandfathered),
                    str(is_grandfathered),
                )
            )
            subscription.is_grandfathered = is_grandfathered

        if cancel_at_period_end is not None and cancel_at_period_end != subscription.cancel_at_period_end:
            changes.append(
                (
                    "cancel_at_period_end",
                    str(subscription.cancel_at_period_end),
                    str(cancel_at_period_end),
                )
            )
            subscription.cancel_at_period_end = cancel_at_period_end

        # Save changes
        if changes:
            updated_subscription = await self.repository.update_subscription(subscription_id=subscription.id)

            # Log changes to history
            for change_type, old_val, new_val in changes:
                await self.repository.create_subscription_history(
                    subscription_id=subscription.id,
                    change_type=f"admin_update_{change_type}",
                    old_value=old_val,
                    new_value=new_val,
                    reason=reason or "Manual admin modification",
                )

            return SubscriptionResponse.model_validate(updated_subscription)

        return SubscriptionResponse.model_validate(subscription)

    async def admin_cancel_subscription(
        self,
        subscription_id: str,
        reason: str | None = None,
    ) -> SubscriptionResponse:
        """
        Admin method to cancel subscription immediately (admin only).

        This method:
        1. Cancels Stripe subscription if it exists
        2. Changes plan tier to 'free'
        3. Sets status to 'canceled'
        4. Logs changes to history

        Args:
            subscription_id: Subscription ID
            reason: Reason for cancellation (for audit log)

        Returns:
            Updated subscription

        Raises:
            SubscriptionNotFoundError: If subscription not found
            StripeAPIError: If Stripe API call fails
        """
        from uuid import UUID as PyUUID

        # Try to get subscription - first try as UUID, then as user_id (ULID)
        subscription = None

        # Try as UUID first (normal case)
        try:
            subscription_uuid = PyUUID(subscription_id)
            subscription = await self.repository.get_subscription_by_id(subscription_uuid)
        except (ValueError, TypeError):
            # Not a UUID, might be ULID (user_id) - try to find by user_id
            subscription = await self.repository.get_subscription_by_user_id(subscription_id)

        if not subscription:
            logger.error(f"Subscription not found: {subscription_id} (tried as UUID and as user_id)")
            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found")

        # Cancel Stripe subscription if it exists
        if subscription.stripe_subscription_id:
            try:
                # Cancel immediately (not at period end)
                await self.stripe_client.cancel_subscription(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False,
                )
                logger.info(f"Cancelled Stripe subscription {subscription.stripe_subscription_id} for admin action")
            except Exception as e:
                logger.warning(f"Failed to cancel Stripe subscription {subscription.stripe_subscription_id}: {e}")
                # Continue with database update even if Stripe fails

        # Track changes for audit log
        changes = []

        # Change plan to free
        if subscription.plan_tier != "free":
            changes.append(("plan_tier", subscription.plan_tier, "free"))
            subscription.plan_tier = "free"

        # Set status to canceled
        if subscription.status != "canceled":
            changes.append(("status", subscription.status, "canceled"))
            subscription.status = "canceled"

        # Set cancel_at_period_end to False (already canceled)
        if subscription.cancel_at_period_end:
            changes.append(
                (
                    "cancel_at_period_end",
                    str(subscription.cancel_at_period_end),
                    "False",
                )
            )
            subscription.cancel_at_period_end = False

        # Save changes
        if changes:
            updated_subscription = await self.repository.update_subscription(subscription_id=subscription.id)

            # Log changes to history
            for change_type, old_val, new_val in changes:
                await self.repository.create_subscription_history(
                    subscription_id=subscription.id,
                    change_type=f"admin_cancel_{change_type}",
                    old_value=old_val,
                    new_value=new_val,
                    reason=reason or "Admin canceled subscription",
                )

            logger.info(f"Admin canceled subscription {subscription_id}")
            return SubscriptionResponse.model_validate(updated_subscription)

        return SubscriptionResponse.model_validate(subscription)
