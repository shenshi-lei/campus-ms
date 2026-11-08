from __future__ import annotations

from httpx import AsyncClient


async def test_create_student_requires_admin(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("s001", "student123")
    response = await client.post(
        "/api/v1/students",
        json={"student_no": "S999", "name": "越权同学"},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_admin_creates_student_and_lists(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("admin", "admin123")
    created = await client.post(
        "/api/v1/students",
        json={"student_no": "S002", "name": "学生二", "class_id": seed["class_id"]},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["student_no"] == "S002"

    listing = await client.get("/api/v1/students?page=1&page_size=10", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 2
    assert body["page_size"] == 10


async def test_duplicate_student_no_returns_409(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("admin", "admin123")
    response = await client.post(
        "/api/v1/students",
        json={"student_no": "S001", "name": "重复学号"},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_KEY"


async def test_student_reads_own_profile(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("s001", "student123")
    response = await client.get("/api/v1/students/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["student_no"] == "S001"


async def test_transcript_of_other_student_is_forbidden(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("s001", "student123")
    response = await client.get(
        f"/api/v1/students/{seed['student_id'] + 1}/transcript", headers=headers
    )
    assert response.status_code == 403
