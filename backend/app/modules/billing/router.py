"""FastAPI router for billing and subscription endpoints."""

import logging

import stripe
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.agent.dependencies import AgentTenantContext
from app.modules.auth.db_models import UserDB
from app.modules.auth.dependencies import AdminUser, CurrentUser

from ...core.config import settings
from .dependencies import BillingRepositoryDep, BillingServiceDep, StripeClientDep
from .exceptions import (
    BillingException,
    CannotDowngradeGrandfatheredError,
    InvalidBillingIntervalError,
    InvalidPlanTierError,
    StripeAPIError,
    StripeCustomerNotFoundError,
    StripeSubscriptionNotFoundError,
    SubscriptionAlreadyExistsError,
    SubscriptionNotFoundError,
    WebhookProcessingError,
    WebhookValidationError,
)
from .schemas import (
    AdminCancelSubscriptionRequest,
    AdminSubscriptionResponse,
    AdminSubscriptionStatsResponse,
    AdminUpdateSubscriptionRequest,
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
    MessageResponse,
    PortalSessionResponse,
    SubscriptionLimitsResponse,
    SubscriptionResponse,
    UpdateOpenRouterTokenRequest,
)
from .webhook_handler import WEBHOOK_HANDLERS

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user subscription",
    description="Get current user's subscription details",
)
async def get_subscription(
    current_user: CurrentUser,
    billing_service: BillingServiceDep,
) -> SubscriptionResponse:
    """
    Get current user's subscription details.

    Returns:
        Subscription details including plan tier, status, and billing info
    """
    try:
        return await billing_service.get_subscription(current_user.id)
    except SubscriptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        ) from None
    except BillingException as e:
        logger.error(f"Failed to get subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription",
        ) from e


@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create checkout session",
    description="Create a Stripe Checkout session for subscription purchase",
)
async def create_checkout_session(
    request_data: CreateCheckoutSessionRequest,
    current_user: CurrentUser,
    billing_service: BillingServiceDep,
    db: AsyncSession = Depends(get_db),
) -> CheckoutSessionResponse:
    """
    Create a Stripe Checkout session for subscription purchase.

    Args:
        request_data: Checkout session request with plan details

    Returns:
        Checkout session ID and URL to redirect user
    """
    try:
        # Get user email for Stripe customer
        user = await db.get(UserDB, current_user.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Create customer with email if needed
        session = await billing_service.create_checkout_session(
            user_id=current_user.id,
            plan_tier=request_data.planTier,
            billing_interval=request_data.billingInterval,
            success_url=str(request_data.successUrl),
            cancel_url=str(request_data.cancelUrl),
        )

        return session
    except InvalidPlanTierError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except InvalidBillingIntervalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except SubscriptionAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except StripeAPIError as e:
        logger.error(f"Stripe API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create checkout session",
        ) from e
    except BillingException as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        ) from e


@router.post(
    "/portal",
    response_model=PortalSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create portal session",
    description="Create a Stripe Billing Portal session for subscription management",
)
async def create_portal_session(
    request_data: CreatePortalSessionRequest,
    current_user: CurrentUser,
    billing_service: BillingServiceDep,
) -> PortalSessionResponse:
    """
    Create a Stripe Billing Portal session for subscription management.

    Args:
        request_data: Portal session request with return URL

    Returns:
        Portal session URL to redirect user
    """
    try:
        return await billing_service.create_portal_session(
            user_id=current_user.id,
            return_url=str(request_data.returnUrl),
        )
    except SubscriptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        ) from None
    except StripeCustomerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stripe customer not found",
        ) from None
    except CannotDowngradeGrandfatheredError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except StripeAPIError as e:
        logger.error(f"Stripe API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create portal session",
        ) from e
    except BillingException as e:
        logger.error(f"Failed to create portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session",
        ) from e


@router.post(
    "/cancel",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel subscription",
    description="Cancel user's subscription (at period end)",
)
async def cancel_subscription(
    current_user: CurrentUser,
    billing_service: BillingServiceDep,
) -> SubscriptionResponse:
    """
    Cancel user's subscription at period end.

    Returns:
        Updated subscription details
    """
    try:
        return await billing_service.cancel_subscription(current_user.id)
    except SubscriptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        ) from None
    except StripeSubscriptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stripe subscription not found",
        ) from None
    except CannotDowngradeGrandfatheredError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except StripeAPIError as e:
        logger.error(f"Stripe API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to cancel subscription",
        ) from e
    except BillingException as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription",
        ) from e


@router.put(
    "/openrouter-token",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Update OpenRouter token",
    description="Update user's OpenRouter API token (Free tier BYOK)",
)
async def update_openrouter_token(
    request_data: UpdateOpenRouterTokenRequest,
    current_user: CurrentUser,
    billing_service: BillingServiceDep,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Update user's OpenRouter API token (for Free tier BYOK).

    Args:
        request_data: OpenRouter token update request

    Returns:
        Success message
    """
    try:
        # Update user's OpenRouter token in database
        user = await db.get(UserDB, current_user.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        user.openrouter_api_token = request_data.openrouterApiToken
        await db.commit()

        logger.info(f"Updated OpenRouter token for user {current_user.id}")
        return MessageResponse(message="OpenRouter API token updated successfully")
    except BillingException as e:
        logger.error(f"Failed to update OpenRouter token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update OpenRouter token",
        ) from e


@router.get(
    "/limits",
    response_model=SubscriptionLimitsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get subscription limits",
    description="Get feature limits for user's subscription plan",
)
async def get_subscription_limits(
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    billing_service: BillingServiceDep,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionLimitsResponse:
    """
    Get feature limits for user's subscription plan.

    Returns:
        Subscription limits including AI tokens, storage, and feature flags
    """
    try:
        return await billing_service.get_subscription_limits(
            current_user.id,
            tenant_id=tenant_ctx.tenant_id,
            team_id=tenant_ctx.team_id,
            db=db,
        )
    except SubscriptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        ) from None
    except BillingException as e:
        logger.error(f"Failed to get subscription limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription limits",
        ) from e


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook",
    description="Handle Stripe webhook events",
    include_in_schema=False,  # Hide from API docs
)
@router.post(
    "/webhooks/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook (alias)",
    description="Handle Stripe webhook events (Stripe CLI default path)",
    include_in_schema=False,  # Hide from API docs
)
async def stripe_webhook(
    request: Request,
    stripe_client: StripeClientDep,
    repository: BillingRepositoryDep,
) -> dict:
    """
    Handle Stripe webhook events.

    This endpoint receives events from Stripe and processes them accordingly.
    Events are verified using webhook signature before processing.

    Returns:
        Success response
    """
    if not settings.stripe.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe integration is disabled",
        )

    # Get raw payload and signature header
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.error("Missing Stripe signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )

    try:
        # Verify webhook signature and construct Stripe Event
        event = stripe_client.construct_webhook_event(
            payload=payload,
            sig_header=sig_header,
        )
        logger.info(f"Webhook verified - Event type: {event.type}, ID: {event.id}")

        # Log webhook event
        await repository.create_webhook_event(
            stripe_event_id=event.id,
            event_type=event.type,
            payload=dict(event.data.object),
        )

        # Process event if handler exists
        handler = WEBHOOK_HANDLERS.get(event.type)
        if handler:
            try:
                await handler(event, repository)

                # Mark event as processed
                webhook_event = await repository.get_webhook_event_by_event_id(event.id)
                if webhook_event:
                    await repository.mark_webhook_event_processed(webhook_event.id)

                logger.info(f"Processed webhook event: {event.type} ({event.id})")
            except Exception as e:
                # Log error but don't fail (Stripe retries failed webhooks)
                logger.error(f"Failed to process webhook event {event.type}: {e}", exc_info=True)

                # Mark event as failed
                webhook_event = await repository.get_webhook_event_by_event_id(event.id)
                if webhook_event:
                    await repository.mark_webhook_event_failed(webhook_event.id, str(e))

                raise WebhookProcessingError(f"Failed to process webhook: {e}") from e
        else:
            logger.info(f"No handler for webhook event: {event.type}")

        return {"status": "success"}
    except WebhookValidationError as e:
        logger.error(f"Webhook validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        ) from e
    except WebhookProcessingError as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        ) from e
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Stripe signature verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook signature: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Unexpected webhook error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        ) from e


# ---------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------


@router.get(
    "/admin/subscriptions",
    response_model=list[AdminSubscriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all subscriptions (admin only)",
    description="Get list of all subscriptions with user details",
    tags=["Admin"],
)
async def get_all_subscriptions(
    _: AdminUser,
    billing_service: BillingServiceDep,
    skip: int = 0,
    limit: int = 100,
) -> list[AdminSubscriptionResponse]:
    """
    Get all subscriptions with user details (admin only).

    Returns:
        List of subscriptions with user information
    """
    try:
        subscriptions = await billing_service.get_all_subscriptions(skip=skip, limit=limit)
        return [AdminSubscriptionResponse(**sub) for sub in subscriptions]
    except BillingException as e:
        logger.error(f"Failed to get all subscriptions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscriptions",
        ) from e


@router.get(
    "/admin/subscriptions/stats",
    response_model=AdminSubscriptionStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get subscription statistics (admin only)",
    description="Get subscription statistics and revenue information",
    tags=["Admin"],
)
async def get_subscription_stats(
    _: AdminUser,
    billing_service: BillingServiceDep,
) -> AdminSubscriptionStatsResponse:
    """
    Get subscription statistics (admin only).

    Returns:
        Subscription statistics including user counts and revenue
    """
    try:
        stats = await billing_service.get_subscription_stats()
        return AdminSubscriptionStatsResponse(**stats)
    except BillingException as e:
        logger.error(f"Failed to get subscription stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics",
        ) from e


@router.patch(
    "/admin/subscriptions/{subscription_id}",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update subscription (admin only)",
    description="Manually update subscription details",
    tags=["Admin"],
)
async def admin_update_subscription(
    subscription_id: str,
    request_data: AdminUpdateSubscriptionRequest,
    _: AdminUser,
    billing_service: BillingServiceDep,
) -> SubscriptionResponse:
    """
    Admin endpoint to manually update subscription.

    Args:
        subscription_id: Subscription ID to update
        request_data: Update request with new values

    Returns:
        Updated subscription details
    """
    try:
        updated_subscription = await billing_service.admin_update_subscription(
            subscription_id=subscription_id,
            plan_tier=request_data.planTier,
            status=request_data.status,
            is_grandfathered=request_data.isGrandfathered,
            cancel_at_period_end=request_data.cancelAtPeriodEnd,
            reason=request_data.reason,
        )

        return updated_subscription
    except SubscriptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        ) from None
    except InvalidPlanTierError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except BillingException as e:
        logger.error(f"Failed to update subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update subscription",
        ) from e


@router.post(
    "/admin/subscriptions/{subscription_id}/cancel",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel subscription (admin only)",
    description="Immediately cancel subscription, downgrade to free, and cancel in Stripe if exists",
    tags=["Admin"],
)
async def admin_cancel_subscription(
    subscription_id: str,
    _: AdminUser,
    billing_service: BillingServiceDep,
    request_data: AdminCancelSubscriptionRequest | None = Body(None),
) -> SubscriptionResponse:
    """
    Admin endpoint to immediately cancel subscription.

    This endpoint:
    1. Cancels Stripe subscription if it exists
    2. Changes plan tier to 'free'
    3. Sets status to 'canceled'

    Args:
        subscription_id: Subscription ID to cancel
        request_data: Optional request with reason for cancellation

    Returns:
        Updated subscription details
    """
    logger.info(f"Admin cancel subscription request: subscription_id={subscription_id}")
    try:
        reason = request_data.reason if request_data else None
        updated_subscription = await billing_service.admin_cancel_subscription(
            subscription_id=subscription_id,
            reason=reason,
        )

        return updated_subscription
    except SubscriptionNotFoundError as e:
        logger.error(f"Subscription not found: {subscription_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        logger.error(f"Invalid subscription ID format: {subscription_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription ID format: {subscription_id}",
        ) from e
    except StripeAPIError as e:
        logger.error(f"Stripe API error while canceling subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to cancel Stripe subscription",
        ) from e
    except BillingException as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription",
        ) from e
