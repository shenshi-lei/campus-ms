from __future__ import annotations

from httpx import AsyncClient


async def test_group_crud_and_expand(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    created = await client.post(
        "/api/v1/groups",
        json={
            "code": "demo_group",
            "name": "演示群组",
            "description": "测试群组",
            "members": [
                {"member_type": "student", "member_id": seed["student_id"]},
                {"member_type": "class", "member_id": seed["class_id"]},
            ],
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    group_id = created.json()["id"]
    assert created.json()["member_count"] == 2

    listed = await client.get("/api/v1/groups", headers=admin)
    assert listed.status_code == 200
    assert any(item["id"] == group_id for item in listed.json())

    expanded = await client.get(f"/api/v1/groups/{group_id}/expand", headers=admin)
    assert expanded.status_code == 200
    assert seed["student_user_id"] in expanded.json()["user_ids"]
    assert expanded.json()["user_count"] >= 1

    updated = await client.patch(
        f"/api/v1/groups/{group_id}",
        json={"description": "更新后的描述"},
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "更新后的描述"

    denied = await client.post(
        "/api/v1/groups",
        json={"code": "teacher_group", "name": "教师群组"},
        headers=teacher,
    )
    assert denied.status_code == 403

    notice = await client.post(
        "/api/v1/notices",
        json={
            "title": "群组通知",
            "content": "仅群组成员可见",
            "audience": "group",
            "group_id": group_id,
        },
        headers=admin,
    )
    assert notice.status_code == 201, notice.text

    student = await auth_headers("s001", "student123")
    student_notices = await client.get("/api/v1/notices?page_size=100", headers=student)
    assert any(item["title"] == "群组通知" for item in student_notices.json()["items"])
    teacher_notices = await client.get("/api/v1/notices?page_size=100", headers=teacher)
    assert all(item["title"] != "群组通知" for item in teacher_notices.json()["items"])

    teacher_notice = await client.post(
        "/api/v1/notices",
        json={
            "title": "教师群组通知",
            "audience": "group",
            "group_id": group_id,
        },
        headers=teacher,
    )
    assert teacher_notice.status_code == 403

    deleted = await client.delete(f"/api/v1/groups/{group_id}", headers=admin)
    assert deleted.status_code == 200
