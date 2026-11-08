from __future__ import annotations

from httpx import AsyncClient

from campus.core.config import Settings
from campus.core.security import create_access_token


async def test_invalid_token_is_rejected(client: AsyncClient, seed: dict[str, int]) -> None:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_expired_token_reports_token_expired(
    client: AsyncClient, seed: dict[str, int], app
) -> None:
    settings = Settings(
        app_env="test",
        jwt_secret=app.state.settings.jwt_secret,
        access_token_expire_minutes=-1,
    )
    token = create_access_token(1, "admin", settings)
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


async def test_change_password_checks_old_password(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("admin", "admin123")
    wrong = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "wrong123", "new_password": "newpass456"},
        headers=headers,
    )
    assert wrong.status_code == 401

    same = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin123", "new_password": "admin123"},
        headers=headers,
    )
    assert same.status_code == 403


async def test_student_only_endpoint_rejects_admin(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    response = await client.get("/api/v1/students/me", headers=admin)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_basic_auth_scheme_is_rejected(client: AsyncClient, seed: dict[str, int]) -> None:
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401
