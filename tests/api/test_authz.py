from __future__ import annotations

import pytest
from httpx import AsyncClient

from campus.services.authz import AuthzService


@pytest.fixture
async def authz_seed(app: object) -> None:
    """把权限表写入测试库，验证数据库授权链路。"""
    factory = app.state.session_factory
    async with factory() as session:
        await AuthzService(session).sync_defaults()


async def test_me_returns_permissions_nav_and_scope(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("s001", "student123")
    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "学生一"
    assert "student:self:read" in body["permissions"]
    assert "student:manage" not in body["permissions"]
    assert body["scope"]["student_id"] == seed["student_id"]
    nav_ids = {item["id"] for group in body["nav"] for item in group["items"]}
    assert "students" not in nav_ids
    assert "dashboard" in nav_ids


async def test_admin_nav_contains_settings(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("admin", "admin123")
    body = (await client.get("/api/v1/auth/me", headers=headers)).json()

    nav_ids = {item["id"] for group in body["nav"] for item in group["items"]}
    assert {"settings", "students", "teachers", "fees"} <= nav_ids
    assert "role:manage" in body["permissions"]


async def test_teacher_nav_hides_settings(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("t001", "teacher123")
    body = (await client.get("/api/v1/auth/me", headers=headers)).json()

    nav_ids = {item["id"] for group in body["nav"] for item in group["items"]}
    assert "settings" not in nav_ids
    assert "students" in nav_ids
    assert body["scope"]["teacher_id"] == seed["teacher_id"]


async def test_teacher_only_sees_own_scope_students(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    other_class = await client.post(
        "/api/v1/classes", json={"name": "网络2309", "grade": "2023"}, headers=admin
    )
    assert other_class.status_code == 201
    other = await client.post(
        "/api/v1/students",
        json={
            "student_no": "S900",
            "name": "范围外学生",
            "class_id": other_class.json()["id"],
        },
        headers=admin,
    )
    assert other.status_code == 201

    listing = await client.get("/api/v1/students?page_size=100", headers=teacher)
    assert listing.status_code == 200
    numbers = {item["student_no"] for item in listing.json()["items"]}
    assert numbers == {"S001"}

    denied = await client.get(f"/api/v1/students/{other.json()['id']}", headers=teacher)
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"


async def test_student_teacher_list_masks_contact(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    student = await auth_headers("s001", "student123")
    response = await client.get("/api/v1/teachers", headers=student)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["phone"] is None
    assert item["email"] is None


async def test_role_permission_change_takes_effect_immediately(
    client: AsyncClient, seed: dict[str, int], auth_headers, authz_seed: None
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    roles = (await client.get("/api/v1/authz/roles", headers=admin)).json()
    teacher_role = next(item for item in roles if item["code"] == "teacher")
    codes = [code for code in teacher_role["permissions"] if code != "student:read"]

    updated = await client.put(
        f"/api/v1/authz/roles/{teacher_role['id']}/permissions",
        json={"permissions": codes},
        headers=admin,
    )
    assert updated.status_code == 200

    denied = await client.get("/api/v1/students", headers=teacher)
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"


async def test_teacher_cannot_manage_roles(
    client: AsyncClient, seed: dict[str, int], auth_headers, authz_seed: None
) -> None:
    teacher = await auth_headers("t001", "teacher123")
    response = await client.get("/api/v1/authz/roles", headers=teacher)

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_user_override_can_grant_permission(
    client: AsyncClient, seed: dict[str, int], auth_headers, authz_seed: None
) -> None:
    admin = await auth_headers("admin", "admin123")
    student = await auth_headers("s001", "student123")

    initial = await client.get("/api/v1/students", headers=student)
    assert initial.status_code == 403

    granted = await client.put(
        f"/api/v1/authz/users/{seed['student_user_id']}/permissions",
        json={"items": [{"code": "student:read", "effect": "allow"}]},
        headers=admin,
    )
    assert granted.status_code == 200

    allowed = await client.get("/api/v1/students", headers=student)
    assert allowed.status_code == 200
    assert allowed.json()["total"] == 1
