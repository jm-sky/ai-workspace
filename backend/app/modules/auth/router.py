"""FastAPI router for authentication endpoints.

This module provides authentication endpoints with security features:
- Rate limiting (ENABLED by default - essential security)
- reCAPTCHA protection (decorators present, DISABLED by default)

To enable reCAPTCHA (optional but recommended):
1. Set RECAPTCHA_ENABLED=true in .env
2. Configure RECAPTCHA_SECRET_KEY and RECAPTCHA_SITE_KEY
3. Decorators are already applied - they become active when enabled

To disable rate limiting (NOT recommended):
- Comment out @rate_limit decorators
- Set RATE_LIMIT_ENABLED=false in .env
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import get_token_blacklist_service
from app.core.auth.token_blacklist import TokenBlacklistService
from app.core.csrf import CSRF_COOKIE_NAME
from app.core.database import get_db
from app.core.email.i18n import determine_email_locale, get_translations

from .auth_utils import verify_token
from .cookies import REFRESH_COOKIE_NAME, clear_refresh_cookie, set_refresh_cookie
from .decorators import rate_limit, recaptcha_protected
from .dependencies import AuthServiceDep, CurrentUser, get_current_token
from .exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from .schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    LoginResponse,
    MessageResponse,
    OAuthAuthUrlRequest,
    OAuthAuthUrlResponse,
    OAuthCallbackRequest,
    OAuthConnectionResponse,
    OAuthConnectionsListResponse,
    ResendEmailVerificationRequest,
    ResetPasswordRequest,
    UserLogin,
    UserRegister,
    UserResponse,
)

logger = logging.getLogger(__name__)

# Import 2FA response type if available for union type
try:
    from app.modules.two_factor.schemas import TwoFactorRequiredResponse

    type LoginResponseType = LoginResponse | TwoFactorRequiredResponse
except ImportError:
    type LoginResponseType = LoginResponse  # type: ignore[no-redef]

# Create router
router = APIRouter()


@router.get(
    "/csrf-token",
    summary="Get CSRF token",
    description="Ensure a CSRF cookie is set and return its value for the X-CSRF-Token header",
    tags=["Authentication"],
)
async def get_csrf_token(request: Request) -> dict[str, str]:
    """Return the double-submit CSRF token (CSRFMiddleware issues the cookie if missing)."""
    token = request.cookies.get(CSRF_COOKIE_NAME) or request.state.csrf_token
    return {"csrf_token": token}


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account and send email verification link",
    tags=["Authentication"],
)
@rate_limit("5/minute")  # Prevent registration abuse
@recaptcha_protected("register")  # Disabled by default, enable via RECAPTCHA_ENABLED=true
async def register(
    user_data: UserRegister,
    auth_service: AuthServiceDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Register a new user.

    Security features:
    - ✅ Rate limiting: 5 requests/minute (enabled)
    - ⚪ reCAPTCHA: Disabled by default (enable via RECAPTCHA_ENABLED=true)
    - 💡 Recommendation: Add email verification in production
    """
    try:
        # Determine locale for email
        accept_language = request.headers.get("Accept-Language")
        locale = await determine_email_locale(db=db, user_id=None, accept_language=accept_language)
        translations = get_translations(locale)

        await auth_service.register_user(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name,
            locale=locale,
            translations=translations,
        )
        return MessageResponse(message="Registration successful. Please check your email to verify your account.")
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        ) from None


@router.post(
    "/login",
    response_model=LoginResponseType,
    response_model_exclude={"refreshToken"},
    summary="Login user",
    description="Authenticate user and return JWT tokens or 2FA challenge",
    tags=["Authentication"],
)
@rate_limit("10/minute")  # CRITICAL: Prevent brute force attacks
@recaptcha_protected("login")  # Disabled by default, enable via RECAPTCHA_ENABLED=true
async def login(credentials: UserLogin, auth_service: AuthServiceDep, request: Request, response: Response) -> LoginResponseType:
    """
    Login user and return tokens or 2FA challenge.

    If user has 2FA enabled, returns TwoFactorRequiredResponse.
    Otherwise, returns LoginResponse with tokens. The refresh token is never
    returned in the body — it's set as an HttpOnly cookie.

    Security features:
    - ✅ Rate limiting: 10 requests/minute (enabled - CRITICAL)
    - ⚪ reCAPTCHA: Disabled by default (enable via RECAPTCHA_ENABLED=true)
    - 💡 Recommendation: Implement account lockout after N failed attempts
    """
    try:
        # Debug: Log what type of auth service we're using
        logger.info(f"Login attempt for {credentials.email}, auth_service type: {type(auth_service).__name__}")

        result = await auth_service.login_user(email=credentials.email, password=credentials.password)

        # Debug: Log what we're returning
        if hasattr(result, "requiresTwoFactor"):
            logger.info("Login response: TwoFactorRequiredResponse (2FA required)")
        elif hasattr(result, "accessToken"):
            logger.info("Login response: LoginResponse (normal login, no 2FA)")
            set_refresh_cookie(response, result.refreshToken)
        else:
            logger.warning(f"Login response: Unknown type: {type(result)}")

        return result
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@router.post(
    "/refresh",
    response_model=dict,
    summary="Refresh access token",
    description="Get new access token using the HttpOnly refresh token cookie",
    tags=["Authentication"],
)
@rate_limit("20/minute")  # Prevent token refresh abuse
async def refresh_token(auth_service: AuthServiceDep, request: Request, response: Response) -> dict:
    """
    Refresh access token using the refresh token cookie.

    Rotates the refresh token on every call: a fresh HttpOnly cookie is set
    and the old session is superseded.

    Security features:
    - ✅ Rate limiting: 20 requests/minute (enabled)
    - ✅ Refresh token rotation (new refresh token + jti issued every call)
    """
    refresh_token_value = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        result = await auth_service.refresh_access_token(refresh_token_value)
        set_refresh_cookie(response, str(result.pop("refreshToken")))
        return result
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout user",
    description="Logout current user",
    tags=["Authentication"],
)
async def logout(
    current_user: CurrentUser,
    token: Annotated[str, Depends(get_current_token)],
    blacklist: Annotated[TokenBlacklistService, Depends(get_token_blacklist_service)],
    response: Response,
) -> MessageResponse:
    """
    Logout current user by blacklisting the access token.

    Security features:
    - ✅ Authentication required (JWT token via CurrentUser)
    - ✅ Token invalidation (blacklisted in Redis)
    - ✅ Refresh token cookie cleared; the session's jti (shared by the
      access and refresh token) is revoked, so a copy of the refresh token
      cookie can no longer be used at /auth/refresh either.

    Note:
        The token is blacklisted until its natural expiration.
    """
    # Verify and extract payload to get expiration and JTI
    payload = verify_token(token)
    expires_at = payload.get("exp")

    if not expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token: missing expiration",
        )

    # Blacklist the token (hash-based, legacy path)
    await blacklist.blacklist_token(
        token=token,
        expires_at=expires_at,
        reason="logout",
    )

    # Revoke session by JTI (removes from active sessions sorted set).
    # The refresh token minted alongside this access token shares the same
    # jti, so this also blocks that refresh token at /auth/refresh.
    jti = payload.get("jti")
    if jti:
        await blacklist.revoke_session(
            user_id=current_user.id,
            jti=jti,
            expires_at=expires_at,
            reason="logout",
        )

    clear_refresh_cookie(response)

    return MessageResponse(message="Logged out successfully")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset",
    description="Request a password reset email (development: token is printed to console)",
    tags=["Authentication"],
)
@rate_limit("3/minute")  # CRITICAL: Prevent email enumeration and spam
@recaptcha_protected("forgot_password")  # Disabled by default, enable via RECAPTCHA_ENABLED=true
async def forgot_password(
    request_data: ForgotPasswordRequest,
    auth_service: AuthServiceDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Request password reset.

    Security features:
    - ✅ Rate limiting: 3 requests/minute (enabled - CRITICAL)
    - ⚪ reCAPTCHA: Disabled by default, RECOMMENDED (enable via RECAPTCHA_ENABLED=true)
    - ✅ Generic response message (prevents email enumeration)
    """
    # Determine locale for email
    accept_language = request.headers.get("Accept-Language")
    # Get user_id from email if user exists (for locale detection)
    user = await auth_service.user_repository.get_user_by_email(request_data.email)
    user_id = user.id if user else None
    locale = await determine_email_locale(db=db, user_id=user_id, accept_language=accept_language)
    translations = get_translations(locale)

    # Always return success message to prevent email enumeration
    await auth_service.request_password_reset(
        request_data.email,
        locale=locale,
        translations=translations,
    )
    return MessageResponse(message="If the email exists, a password reset link has been sent")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password",
    description="Reset password using reset token",
    tags=["Authentication"],
)
@rate_limit("5/minute")  # Prevent token brute force
async def reset_password(request_data: ResetPasswordRequest, auth_service: AuthServiceDep, request: Request) -> MessageResponse:
    """
    Reset password with token.

    Security features:
    - ✅ Rate limiting: 5 requests/minute (enabled)
    - ✅ Token is single-use and short-lived (1 hour)
    """
    try:
        await auth_service.reset_password(request_data.token, request_data.newPassword)
        return MessageResponse(message="Password has been reset successfully")
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from None


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password",
    description="Change password for authenticated user",
    tags=["Authentication"],
)
@rate_limit("3/minute")  # Prevent password change abuse
async def change_password(
    request_data: ChangePasswordRequest,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Change password for authenticated user.

    Security features:
    - ✅ Rate limiting: 3 requests/minute (enabled)
    - ✅ Authentication required (JWT token)
    - ✅ Current password verification required
    """
    try:
        # Determine locale for email
        accept_language = request.headers.get("Accept-Language")
        locale = await determine_email_locale(db=db, user_id=current_user.id, accept_language=accept_language)
        translations = get_translations(locale)

        # Get client IP address for security notification
        client_ip = request.client.host if request.client else None
        await auth_service.change_password(
            user_id=current_user.id,
            current_password=request_data.currentPassword,
            new_password=request_data.newPassword,
            ip_address=client_ip,
            locale=locale,
            translations=translations,
        )
        return MessageResponse(message="Password changed successfully")
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from None
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get currently authenticated user information",
    tags=["Authentication"],
)
async def get_current_user_info(current_user: CurrentUser) -> UserResponse:
    """
    Get current user information.

    Security features:
    - ✅ Authentication required (JWT token via CurrentUser)
    - ⚪ Rate limiting: Not needed (read-only, already auth-protected)
    """
    return UserResponse(**current_user.to_response())


@router.post(
    "/email/verify",
    response_model=MessageResponse,
    summary="Verify email address",
    description="Confirm email using verification token sent after registration",
    tags=["Authentication"],
)
async def verify_email(
    request_data: EmailVerificationRequest,
    auth_service: AuthServiceDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        # Determine locale for email (before verification, try to get user from token)
        accept_language = request.headers.get("Accept-Language")
        # Try to peek at user from token without verifying yet (for locale detection)
        # If this fails, we'll use default locale
        user_id = None
        try:
            from app.modules.auth.auth_utils import verify_token

            payload = verify_token(request_data.token)
            user_id = payload.get("sub")
        except Exception:
            pass  # Will use default locale

        locale = await determine_email_locale(db=db, user_id=user_id, accept_language=accept_language)
        translations = get_translations(locale)

        await auth_service.verify_email(
            request_data.token,
            locale=locale,
            translations=translations,
        )
        return MessageResponse(message="Email address verified successfully.")
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        ) from None


@router.post(
    "/email/resend",
    response_model=MessageResponse,
    summary="Resend email verification link",
    description="Resend verification link to the provided email address",
    tags=["Authentication"],
)
@rate_limit("3/hour")
async def resend_email_verification(
    request_data: ResendEmailVerificationRequest,
    auth_service: AuthServiceDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    # Determine locale for email
    accept_language = request.headers.get("Accept-Language")
    # Get user_id from email if user exists (for locale detection)
    user = await auth_service.user_repository.get_user_by_email(request_data.email)
    user_id = user.id if user else None
    locale = await determine_email_locale(db=db, user_id=user_id, accept_language=accept_language)
    translations = get_translations(locale)

    await auth_service.resend_email_verification(
        request_data.email,
        locale=locale,
        translations=translations,
    )
    return MessageResponse(message="If the email exists, a new verification link has been sent.")


@router.delete(
    "/account",
    response_model=MessageResponse,
    summary="Delete account",
    description="Delete current user's account (soft delete by default)",
    tags=["Authentication"],
)
@rate_limit("1/day")  # Prevent abuse - only allow one deletion per day
async def delete_account(
    request_data: DeleteAccountRequest,
    current_user: CurrentUser,
    token: Annotated[str, Depends(get_current_token)],
    blacklist: Annotated[TokenBlacklistService, Depends(get_token_blacklist_service)],
    auth_service: AuthServiceDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Delete current user's account.

    Security features:
    - ✅ Rate limiting: 1 request/day (enabled - CRITICAL)
    - ✅ Authentication required (JWT token)
    - ✅ Password verification (optional but recommended)
    - ✅ Confirmation phrase required
    - ✅ Soft delete by default (GDPR compliant with data anonymization)
    - ✅ Token invalidation (blacklisted after deletion)
    """
    try:
        # Determine locale for email (before account is deleted)
        accept_language = request.headers.get("Accept-Language")
        locale = await determine_email_locale(db=db, user_id=current_user.id, accept_language=accept_language)
        translations = get_translations(locale)

        # Delete all user images from storage (before account deletion)
        try:
            from app.modules.gear.repository import GearRepository
            from app.modules.gear.service import GearService

            gear_repository = GearRepository(db)
            gear_service = GearService(gear_repository)
            deleted_images_count = await gear_service.delete_all_user_images(current_user.id)
            if deleted_images_count > 0:
                logger.info(f"Deleted {deleted_images_count} image(s) for user {current_user.id} during account deletion")
        except Exception as e:
            # Log error but don't fail account deletion if image deletion fails
            logger.error(f"Failed to delete user images during account deletion (user_id={current_user.id}): {e}")

        await auth_service.delete_account(
            user_id=current_user.id,
            password=request_data.password,
            confirmation=request_data.confirmation,
            soft_delete=True,
            locale=locale,
            translations=translations,
        )

        # Blacklist current token after successful deletion
        payload = verify_token(token)
        expires_at = payload.get("exp")
        if expires_at:
            await blacklist.blacklist_token(
                token=token,
                expires_at=expires_at,
                reason="account_deleted",
            )
            logger.info(f"Token blacklisted after account deletion: user_id={current_user.id}")
        return MessageResponse(message="Account has been deleted successfully")
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None


# OAuth Endpoints


@router.post(
    "/oauth/auth-url",
    response_model=OAuthAuthUrlResponse,
    summary="Get OAuth authorization URL",
    description="Generate OAuth authorization URL for the specified provider",
    tags=["Authentication", "OAuth"],
)
@rate_limit("10/minute")
async def get_oauth_auth_url(request_data: OAuthAuthUrlRequest, request: Request) -> OAuthAuthUrlResponse:
    """
    Generate OAuth authorization URL.

    Returns authorization URL and CSRF state parameter. The state is also
    persisted server-side (short TTL, single-use) so the callback can verify
    it instead of trusting only the frontend's copy.
    """
    from app.core.oauth import oauth_service
    from app.core.oauth_state_store import get_oauth_state_store

    state = oauth_service.generate_state()
    auth_url = oauth_service.get_authorization_url(request_data.provider, state)

    state_store = await get_oauth_state_store()
    await state_store.store_state(state, request_data.provider)

    return OAuthAuthUrlResponse(authUrl=auth_url, state=state)


@router.post(
    "/oauth/callback/{provider}",
    response_model=LoginResponseType,
    response_model_exclude={"refreshToken"},
    summary="OAuth callback handler",
    description="Handle OAuth callback and login/register user",
    tags=["Authentication", "OAuth"],
)
@rate_limit("10/minute")
@recaptcha_protected("oauth_callback")  # Optional reCAPTCHA protection
async def oauth_callback(
    provider: str,
    callback_data: OAuthCallbackRequest,
    auth_service: AuthServiceDep,
    request: Request,
    response: Response,
) -> LoginResponseType:
    """
    Handle OAuth callback and authenticate user.

    Security features:
    - ✅ Rate limiting: 10 requests/minute
    - ✅ CSRF protection via state parameter (verified + consumed server-side)
    - ⚪ reCAPTCHA: Optional (enable via RECAPTCHA_ENABLED=true)
    """
    from app.core.oauth import oauth_service
    from app.core.oauth_state_store import get_oauth_state_store

    state_store = await get_oauth_state_store()
    if not await state_store.consume_state(callback_data.state, provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    try:
        # Exchange code for token
        logger.info(f"OAuth callback: Exchanging code for token (provider: {provider})")
        token_response = await oauth_service.exchange_code_for_token(provider, callback_data.code)
        logger.info("OAuth callback: Token exchange successful")

        # Get user info from provider
        logger.info(f"OAuth callback: Fetching user info from {provider}")
        user_info = await oauth_service.get_user_info(provider, token_response.accessToken)
        logger.info(f"OAuth callback: User info received - email: {user_info.email}, provider_id: {user_info.providerId}")

        # Login or register user via OAuth
        logger.info("OAuth callback: Calling auth_service.login_with_oauth")
        # Convert Pydantic model to dict for compatibility
        user_info_dict = user_info.model_dump()
        logger.debug(f"OAuth callback: user_info_dict = {user_info_dict}")
        result = await auth_service.login_with_oauth(provider, user_info_dict)
        logger.info("OAuth callback: login_with_oauth completed successfully")
        if hasattr(result, "accessToken"):
            set_refresh_cookie(response, result.refreshToken)
        return result

    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication failed: {str(e)}",
        ) from e


@router.get(
    "/oauth/connections",
    response_model=OAuthConnectionsListResponse,
    summary="Get OAuth connections",
    description="Get all OAuth providers linked to the current user's account",
    tags=["Authentication", "OAuth"],
)
async def get_oauth_connections(
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
) -> OAuthConnectionsListResponse:
    """
    Get all OAuth connections for the current user.

    Security features:
    - ✅ Authentication required (JWT token via CurrentUser)
    """
    connections = await auth_service.user_repository.get_oauth_connections(current_user.id)
    return OAuthConnectionsListResponse(connections=[OAuthConnectionResponse(**conn) for conn in connections])


@router.delete(
    "/oauth/connections/{provider}",
    response_model=MessageResponse,
    summary="Delete OAuth connection",
    description="Remove an OAuth provider from the current user's account",
    tags=["Authentication", "OAuth"],
)
@rate_limit("10/minute")
async def delete_oauth_connection(
    provider: str,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
    request: Request,
) -> MessageResponse:
    """
    Delete an OAuth connection for the current user.

    Security features:
    - ✅ Authentication required (JWT token)
    - ✅ Rate limiting: 10 requests/minute
    """
    deleted = await auth_service.user_repository.delete_oauth_connection(current_user.id, provider)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth connection for provider '{provider}' not found",
        )
    return MessageResponse(message=f"OAuth connection for {provider} has been removed successfully")
