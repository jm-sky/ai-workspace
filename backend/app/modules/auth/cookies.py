"""HttpOnly cookie helpers for the refresh token.

The refresh token is issued as an HttpOnly/SameSite=Strict cookie
instead of being returned in the JSON body, so client-side JS (and any XSS)
can never read it. Secure is on in production only (same as CSRF) so local
HTTP (localhost / Cursor Browser) can persist the session across reloads.
The cookie is scoped to the auth router's own mount path so it is never
attached to unrelated API requests.
"""

from fastapi import Response

from ...core.config import settings

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Attach the refresh token to the response as an HttpOnly cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.is_production(),
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        max_age=settings.security.refresh_token_expires_days * 86400,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh token cookie (logout / invalidated session)."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.is_production(),
        samesite="strict",
    )
