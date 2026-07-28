"""HttpOnly cookie helpers for the refresh token.

The refresh token is issued as an HttpOnly/SameSite=Strict cookie
instead of being returned in the JSON body, so client-side JS (and any XSS)
can never read it. Secure is on in production only (same as CSRF) so local
HTTP (localhost / Cursor Browser) can persist the session across reloads.

Cookie name is derived from ``settings.app.name`` (``APP_NAME``), e.g.
``ai_workspace_refresh_token``, so localhost multi-app dev (shared cookie
jar / Cursor Browser) cannot collide with another project's bare
``refresh_token`` Path=/ cookie — Starlette keeps one value per name and a
foreign JWT would fail signature checks. Colons are not used: they are not
valid in cookie-name tokens (RFC 6265).

The cookie is scoped to the auth router's own mount path so it is never
attached to unrelated API requests.
"""

from __future__ import annotations

import re

from fastapi import Response

from ...core.config import settings

REFRESH_COOKIE_PATH = "/api/auth"
# Pre-config / short-lived names — clear on set/logout so leftovers cannot
# shadow the current cookie on our auth path.
_LEGACY_REFRESH_COOKIE_NAMES = ("refresh_token", "aw_refresh_token")


def refresh_cookie_name() -> str:
    """Return ``{app_name}_refresh_token`` with a cookie-safe app slug."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", settings.app.name).strip("_").lower()
    if not slug:
        slug = "app"
    return f"{slug}_refresh_token"


# Eager alias for call sites / tests that import a constant.
REFRESH_COOKIE_NAME = refresh_cookie_name()


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Attach the refresh token to the response as an HttpOnly cookie."""
    name = refresh_cookie_name()
    _clear_stale_refresh_cookies(response, current_name=name)
    response.set_cookie(
        key=name,
        value=refresh_token,
        httponly=True,
        secure=settings.is_production(),
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        max_age=settings.security.refresh_token_expires_days * 86400,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh token cookie (logout / invalidated session)."""
    name = refresh_cookie_name()
    _clear_stale_refresh_cookies(response, current_name=name)
    for secure_flag in (True, False):
        response.delete_cookie(
            key=name,
            path=REFRESH_COOKIE_PATH,
            httponly=True,
            secure=secure_flag,
            samesite="strict",
        )


def _clear_stale_refresh_cookies(response: Response, *, current_name: str) -> None:
    """Expire legacy / Secure-variant cookies on our auth path only.

    Do not clear Path=/ ``refresh_token`` — other localhost apps (e.g. portal
    klienta) may own that cookie and Cursor Browser shares the jar.
    """
    names = {current_name, *_LEGACY_REFRESH_COOKIE_NAMES}
    for name in names:
        for secure_flag in (True, False):
            response.delete_cookie(
                key=name,
                path=REFRESH_COOKIE_PATH,
                httponly=True,
                secure=secure_flag,
                samesite="strict",
            )
