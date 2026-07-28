"""Integration tests for the refresh-token HttpOnly cookie migration.

Regression guard: the refresh token must never appear in a JSON response body
(it's set as an HttpOnly cookie instead), /auth/refresh must read the cookie
rather than a request body, and /auth/logout must clear it.
"""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.auth.dependencies import get_token_blacklist_service
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.modules.auth.auth_utils import create_refresh_token
from app.modules.auth.cookies import refresh_cookie_name
from app.modules.auth.dependencies import get_auth_service, get_current_token, get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginResponse, UserResponse
from app.modules.auth.service import AuthService
from main import app

REFRESH_COOKIE_NAME = refresh_cookie_name()


@pytest.fixture
def sample_user() -> User:
    return User(
        id="user-123",
        email="test@example.com",
        name="Test User",
        hashedPassword="hashed",
        isActive=True,
        isEmailVerified=True,
        createdAt=datetime.now(UTC),
    )


@pytest.fixture
def sample_login_response(sample_user: User) -> LoginResponse:
    return LoginResponse(
        user=UserResponse(**sample_user.to_response()),
        accessToken="access-token-value",
        refreshToken="refresh-token-value",
        tokenType="bearer",
        expiresIn=1800,
        requiresEmailVerification=False,
    )


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf-token")
    assert response.status_code == status.HTTP_200_OK
    token = response.cookies.get(CSRF_COOKIE_NAME) or response.json()["csrf_token"]
    return {CSRF_HEADER_NAME: token}


class TestLoginSetsRefreshCookie:
    def test_login_sets_httponly_cookie_and_omits_refresh_token_from_body(
        self,
        client: TestClient,
        sample_login_response: LoginResponse,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.core.config import settings

        # Prod containers often have RECAPTCHA_ENABLED=true; this test only
        # covers cookie/body behavior, so disable verification for the call.
        monkeypatch.setattr(settings.recaptcha, "enabled", False)

        fake_service = AsyncMock(spec=AuthService)
        fake_service.login_user.return_value = sample_login_response
        app.dependency_overrides[get_auth_service] = lambda: fake_service

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
            headers=_csrf_headers(client),
        )

        assert response.status_code == status.HTTP_200_OK
        assert "refreshToken" not in response.json()
        assert response.json()["accessToken"] == "access-token-value"

        set_cookie = response.headers.get("set-cookie", "")
        assert f"{REFRESH_COOKIE_NAME}=refresh-token-value" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=strict" in set_cookie
        assert "Path=/api/auth" in set_cookie


class TestRefreshEndpointUsesCookie:
    def test_refresh_without_cookie_is_rejected(self, client: TestClient) -> None:
        response = client.post("/api/auth/refresh", headers=_csrf_headers(client))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_reads_cookie_and_rotates_it(self, client: TestClient, sample_user: User) -> None:
        refresh_token = create_refresh_token(data={"sub": sample_user.id, "email": sample_user.email})

        fake_service = AsyncMock(spec=AuthService)
        fake_service.refresh_access_token.return_value = {
            "accessToken": "new-access-token",
            "refreshToken": "new-refresh-token",
            "tokenType": "bearer",
            "expiresIn": 1800,
        }
        app.dependency_overrides[get_auth_service] = lambda: fake_service

        headers = _csrf_headers(client)
        client.cookies.set(REFRESH_COOKIE_NAME, refresh_token, path="/api/auth")
        response = client.post("/api/auth/refresh", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert "refreshToken" not in response.json()
        assert response.json()["accessToken"] == "new-access-token"
        fake_service.refresh_access_token.assert_awaited_once_with(refresh_token)

        set_cookie = response.headers.get("set-cookie", "")
        assert f"{REFRESH_COOKIE_NAME}=new-refresh-token" in set_cookie
        assert "HttpOnly" in set_cookie


class TestLogoutClearsCookie:
    def test_logout_clears_refresh_cookie(self, client: TestClient, sample_user: User) -> None:
        from app.modules.auth.auth_utils import create_access_token

        access_token = create_access_token(data={"sub": sample_user.id, "email": sample_user.email, "jti": "session-jti"})

        app.dependency_overrides[get_current_user] = lambda: sample_user
        app.dependency_overrides[get_current_token] = lambda: access_token
        fake_blacklist = AsyncMock()
        app.dependency_overrides[get_token_blacklist_service] = lambda: fake_blacklist

        headers = _csrf_headers(client)
        headers["Authorization"] = f"Bearer {access_token}"
        client.cookies.set(REFRESH_COOKIE_NAME, "some-refresh-token", path="/api/auth")
        response = client.post("/api/auth/logout", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        fake_blacklist.blacklist_token.assert_awaited_once()
        fake_blacklist.revoke_session.assert_awaited_once()

        set_cookie = response.headers.get("set-cookie", "")
        assert set_cookie.startswith(f"{REFRESH_COOKIE_NAME}=")
        assert "max-age=0" in set_cookie.lower()
