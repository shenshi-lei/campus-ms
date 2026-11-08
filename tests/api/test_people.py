from __future__ import annotations

from httpx import AsyncClient


async def test_teacher_lifecycle(client: AsyncClient, seed: dict[str, int], auth_headers) -> None:
    admin = await auth_headers("admin", "admin123")
    created = await client.post(
        "/api/v1/teachers",
        json={"teacher_no": "T002", "name": "教师二", "title": "副教授", "department": "软件"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    teacher_id = created.json()["id"]

    listing = await client.get("/api/v1/teachers?keyword=T002", headers=admin)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = await client.get(f"/api/v1/teachers/{teacher_id}", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["teacher_no"] == "T002"

    updated = await client.patch(
        f"/api/v1/teachers/{teacher_id}", json={"name": "教师二号"}, headers=admin
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "教师二号"

    deactivated = await client.delete(f"/api/v1/teachers/{teacher_id}", headers=admin)
    assert deactivated.status_code == 200

    duplicate = await client.post(
        "/api/v1/teachers", json={"teacher_no": "T002", "name": "重复工号"}, headers=admin
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_KEY"


async def test_class_lifecycle_and_guards(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    created = await client.post(
        "/api/v1/classes",
        json={"name": "软件2302", "grade": "2023", "major": "软件"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    class_id = created.json()["id"]

    listing = await client.get("/api/v1/classes", headers=admin)
    assert listing.status_code == 200
    assert any(item["id"] == class_id for item in listing.json())

    updated = await client.patch(
        f"/api/v1/classes/{class_id}", json={"major": "软件工程"}, headers=admin
    )
    assert updated.status_code == 200
    assert updated.json()["major"] == "软件工程"

    duplicate = await client.post("/api/v1/classes", json={"name": "软件2302"}, headers=admin)
    assert duplicate.status_code == 409

    deleted = await client.delete(f"/api/v1/classes/{class_id}", headers=admin)
    assert deleted.status_code == 200

    blocked = await client.delete(f"/api/v1/classes/{seed['class_id']}", headers=admin)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "REFERENCE_EXISTS"


async def test_student_update_filters_and_deactivate(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")

    updated = await client.patch(
        f"/api/v1/students/{seed['student_id']}",
        json={"phone": "13900000000"},
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "13900000000"

    filtered = await client.get(
        f"/api/v1/students?class_id={seed['class_id']}&is_active=true", headers=admin
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 1

    missing_class = await client.post(
        "/api/v1/students",
        json={"student_no": "S100", "name": "无班级", "class_id": 9999},
        headers=admin,
    )
    assert missing_class.status_code == 404

    deactivated = await client.delete(f"/api/v1/students/{seed['student_id']}", headers=admin)
    assert deactivated.status_code == 200

    inactive = await client.get("/api/v1/students?is_active=false", headers=admin)
    assert inactive.json()["total"] == 1


async def test_transcript_flow(client: AsyncClient, seed: dict[str, int], auth_headers) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    enrolled = await client.post(
        "/api/v1/enrollments",
        json={"course_id": seed["course_id"], "student_id": seed["student_id"]},
        headers=admin,
    )
    assert enrolled.status_code == 201

    scored = await client.post(
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
    assert scored.status_code == 201

    transcript = await client.get(
        f"/api/v1/students/{seed['student_id']}/transcript", headers=teacher
    )
    assert transcript.status_code == 200
    assert transcript.json()[0]["final_score"] == 86.0

    own = await client.get(f"/api/v1/students/{seed['student_id']}/transcript", headers=student)
    assert own.status_code == 200

    missing = await client.get("/api/v1/students/9999/transcript", headers=admin)
    assert missing.status_code == 404


async def test_student_cannot_list_students(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    student = await auth_headers("s001", "student123")
    response = await client.get("/api/v1/students", headers=student)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
