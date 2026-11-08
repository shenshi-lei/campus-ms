from __future__ import annotations

from httpx import AsyncClient


async def test_login_success_returns_token(client: AsyncClient, seed: dict[str, int]) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"
    assert body["expires_in"] > 0


async def test_login_with_wrong_password_returns_401(
    client: AsyncClient, seed: dict[str, int]
) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-pass"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_me_requires_token(client: AsyncClient, seed: dict[str, int]) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"

    body = response.json()
    assert "password_hash" not in body


async def test_change_password_then_login(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("admin", "admin123")
    response = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin123", "new_password": "newpass456"},
        headers=headers,
    )
    assert response.status_code == 200

    relogin = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "newpass456"}
    )
    assert relogin.status_code == 200


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
