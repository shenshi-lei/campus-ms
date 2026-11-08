from __future__ import annotations

from httpx import AsyncClient


async def test_org_crud_and_guards(client: AsyncClient, seed: dict[str, int], auth_headers) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    created = await client.post(
        "/api/v1/org/departments",
        json={"code": "ART", "name": "艺术学院", "kind": "college"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    department_id = created.json()["id"]

    denied = await client.post(
        "/api/v1/org/departments",
        json={"code": "ART2", "name": "艺术学院二"},
        headers=teacher,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"

    subject = await client.post(
        "/api/v1/org/subjects",
        json={"code": "ART101", "name": "素描", "department_id": department_id},
        headers=admin,
    )
    assert subject.status_code == 201
    assert subject.json()["department_id"] == department_id

    duplicate = await client.post(
        "/api/v1/org/subjects",
        json={"code": "ART101", "name": "素描二"},
        headers=admin,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_KEY"

    listed = await client.get("/api/v1/org/departments", headers=teacher)
    assert listed.status_code == 200
    assert any(item["code"] == "ART" for item in listed.json())


async def test_semester_switch_keeps_single_current(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")

    first = await client.post(
        "/api/v1/org/semesters",
        json={
            "name": "2024-2025-1",
            "start_date": "2024-09-01",
            "end_date": "2025-01-15",
            "is_current": True,
        },
        headers=admin,
    )
    assert first.status_code == 201, first.text
    assert first.json()["is_current"] is True

    second = await client.post(
        "/api/v1/org/semesters",
        json={
            "name": "2024-2025-2",
            "start_date": "2025-02-20",
            "end_date": "2025-07-10",
            "is_current": True,
        },
        headers=admin,
    )
    assert second.status_code == 201

    listed = await client.get("/api/v1/org/semesters", headers=admin)
    current = [item for item in listed.json() if item["is_current"]]
    assert len(current) == 1
    assert current[0]["name"] == "2024-2025-2"

    invalid = await client.post(
        "/api/v1/org/semesters",
        json={
            "name": "2025-2026-1",
            "start_date": "2025-09-01",
            "end_date": "2025-08-01",
        },
        headers=admin,
    )
    assert invalid.status_code == 409
    assert invalid.json()["code"] == "CONFLICT"


async def test_student_profile_fields_and_masking(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    updated = await client.patch(
        f"/api/v1/students/{seed['student_id']}",
        json={
            "status": "active",
            "enroll_date": "2023-09-01",
            "seat_no": 7,
            "guardian_name": "学生家长",
            "guardian_phone": "13900001111",
            "address": "杭州市示例路 1 号",
            "id_card_masked": "3301**********1234",
            "class_role": "monitor",
            "residence_type": "day",
        },
        headers=admin,
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["seat_no"] == 7
    assert body["guardian_name"] == "学生家长"
    assert body["class_role"] == "monitor"

    head_view = await client.get(f"/api/v1/students/{seed['student_id']}", headers=teacher)
    assert head_view.status_code == 200
    assert head_view.json()["id_card_masked"] == "3301**********1234"

    own = await client.get("/api/v1/students/me", headers=student)
    assert own.status_code == 200
    assert own.json()["guardian_phone"] == "13900001111"


async def test_teacher_profile_extended_fields(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")

    subject = await client.post(
        "/api/v1/org/subjects",
        json={"code": "PHY", "name": "物理"},
        headers=admin,
    )
    assert subject.status_code == 201

    updated = await client.patch(
        f"/api/v1/teachers/{seed['teacher_id']}",
        json={
            "subject_id": subject.json()["id"],
            "position": "教研组长",
            "hire_date": "2015-09-01",
            "employment_status": "active",
            "staff_type": "permanent",
            "education": "master",
            "office": "实验楼 302",
            "workload_limit": 14,
        },
        headers=admin,
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["position"] == "教研组长"
    assert body["office"] == "实验楼 302"
    assert body["workload_limit"] == 14

    missing = await client.patch(
        f"/api/v1/teachers/{seed['teacher_id']}",
        json={"subject_id": 9999},
        headers=admin,
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"
