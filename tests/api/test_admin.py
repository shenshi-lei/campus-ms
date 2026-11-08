from __future__ import annotations

from httpx import AsyncClient


async def test_write_actions_are_audited(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")

    created = await client.post(
        "/api/v1/courses", json={"code": "AUD101", "name": "审计测试课"}, headers=admin
    )
    assert created.status_code == 201

    logs = await client.get("/api/v1/audit-logs?path=/api/v1/courses", headers=admin)
    assert logs.status_code == 200, logs.text
    assert logs.json()["total"] >= 1
    item = logs.json()["items"][0]
    assert item["method"] == "POST"
    assert item["username"] == "admin"
    assert item["status_code"] == 201


async def test_teacher_cannot_read_audit_logs(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    teacher = await auth_headers("t001", "teacher123")
    response = await client.get("/api/v1/audit-logs", headers=teacher)
    assert response.status_code == 403


async def test_account_management(client: AsyncClient, seed: dict[str, int], auth_headers) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    listed = await client.get("/api/v1/accounts", headers=admin)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 3

    denied = await client.get("/api/v1/accounts", headers=teacher)
    assert denied.status_code == 403

    reset = await client.post(
        f"/api/v1/accounts/{seed['student_user_id']}/reset-password",
        json={"new_password": "newpass12345"},
        headers=admin,
    )
    assert reset.status_code == 200
    relogin = await client.post(
        "/api/v1/auth/login",
        json={"username": "s001", "password": "newpass12345"},
    )
    assert relogin.status_code == 200

    self_disable = await client.patch(
        "/api/v1/accounts/1", json={"is_active": False}, headers=admin
    )
    assert self_disable.status_code == 409

    disabled = await client.patch(
        f"/api/v1/accounts/{seed['student_user_id']}",
        json={"is_active": False},
        headers=admin,
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False


async def test_student_csv_export_scope_and_import(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    exported = await client.get("/api/v1/transfer/export/students", headers=admin)
    assert exported.status_code == 200
    assert "student_no" in exported.text
    assert "S001" in exported.text

    other_class = await client.post(
        "/api/v1/classes", json={"name": "网络2401", "grade": "2024"}, headers=admin
    )
    await client.post(
        "/api/v1/students",
        json={
            "student_no": "S901",
            "name": "范围外学生",
            "class_id": other_class.json()["id"],
        },
        headers=admin,
    )
    teacher_export = await client.get("/api/v1/transfer/export/students", headers=teacher)
    assert "S001" in teacher_export.text
    assert "S901" not in teacher_export.text

    csv_text = (
        "student_no,name,gender,status,class_id,phone\n"
        "S001,学生一改,male,active,1,13800000001\n"
        "S999,导入学生,female,active,1,13900009999\n"
    )
    imported = await client.post(
        "/api/v1/transfer/import/students", json={"csv": csv_text}, headers=admin
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created"] == 1
    assert imported.json()["updated"] == 1

    listed = await client.get("/api/v1/students?keyword=S999", headers=admin)
    assert listed.json()["total"] == 1

    denied = await client.post(
        "/api/v1/transfer/import/students", json={"csv": csv_text}, headers=teacher
    )
    assert denied.status_code == 403


async def test_score_export_only_published_for_student(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    await client.post(
        "/api/v1/enrollments",
        json={"course_id": seed["course_id"], "student_id": seed["student_id"]},
        headers=admin,
    )
    await client.post(
        "/api/v1/scores",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "course_id": seed["course_id"],
                    "usual_score": 80,
                    "exam_score": 90,
                }
            ]
        },
        headers=teacher,
    )

    before = await client.get("/api/v1/transfer/export/scores", headers=student)
    assert before.status_code == 200
    assert "CS101" not in before.text

    await client.post(f"/api/v1/courses/{seed['course_id']}/publish-scores", headers=teacher)
    after = await client.get("/api/v1/transfer/export/scores", headers=student)
    assert "CS101" in after.text

    logs = await client.get("/api/v1/audit-logs?path=transfer&page_size=50", headers=admin)
    assert any(item["path"].endswith("/transfer/export/scores") for item in logs.json()["items"])
