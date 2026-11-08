from __future__ import annotations

from httpx import AsyncClient


async def test_course_crud_and_roster(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    created = await client.post(
        "/api/v1/courses",
        json={"code": "CS201", "name": "数据库原理", "capacity": 1, "semester": "2024-2025-2"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    course_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/courses/{course_id}", json={"capacity": 5}, headers=admin
    )
    assert patched.status_code == 200
    assert patched.json()["capacity"] == 5

    detail = await client.get(f"/api/v1/courses/{course_id}", headers=admin)
    assert detail.status_code == 200

    filtered = await client.get("/api/v1/courses?semester=2024-2025-2&keyword=CS201", headers=admin)
    assert filtered.json()["total"] == 1

    student = await auth_headers("s001", "student123")
    forbidden = await client.post(
        "/api/v1/courses", json={"code": "CS999", "name": "越权课程"}, headers=student
    )
    assert forbidden.status_code == 403

    enrolled = await client.post(
        "/api/v1/enrollments",
        json={"course_id": course_id, "student_id": seed["student_id"]},
        headers=admin,
    )
    assert enrolled.status_code == 201

    roster = await client.get(f"/api/v1/courses/{course_id}/roster", headers=admin)
    assert roster.status_code == 200
    assert roster.json()[0]["student_no"] == "S001"

    blocked = await client.delete(f"/api/v1/courses/{course_id}", headers=admin)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "REFERENCE_EXISTS"


async def test_course_delete_without_enrollments(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    created = await client.post(
        "/api/v1/courses", json={"code": "CS301", "name": "临时课程"}, headers=admin
    )
    course_id = created.json()["id"]
    deleted = await client.delete(f"/api/v1/courses/{course_id}", headers=admin)
    assert deleted.status_code == 200


async def test_enrollment_listing_and_permissions(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    student = await auth_headers("s001", "student123")

    enrolled = await client.post(
        "/api/v1/enrollments",
        json={"course_id": seed["course_id"], "student_id": seed["student_id"]},
        headers=admin,
    )
    assert enrolled.status_code == 201
    enrollment_id = enrolled.json()["id"]

    own_list = await client.get("/api/v1/enrollments", headers=student)
    assert own_list.status_code == 200
    assert own_list.json()["total"] == 1

    admin_list = await client.get(
        f"/api/v1/enrollments?course_id={seed['course_id']}", headers=admin
    )
    assert admin_list.json()["total"] == 1

    missing_student = await client.post(
        "/api/v1/enrollments", json={"course_id": seed["course_id"]}, headers=admin
    )
    assert missing_student.status_code == 409
    assert missing_student.json()["code"] == "CONFLICT"

    second = await client.post(
        "/api/v1/students",
        json={"student_no": "S200", "name": "其他学生"},
        headers=admin,
    )
    second_id = second.json()["id"]
    other_enrollment = await client.post(
        "/api/v1/enrollments",
        json={"course_id": seed["course_id"], "student_id": second_id},
        headers=admin,
    )
    assert other_enrollment.status_code == 201

    forbidden = await client.delete(
        f"/api/v1/enrollments/{other_enrollment.json()['id']}", headers=student
    )
    assert forbidden.status_code == 403

    dropped = await client.delete(f"/api/v1/enrollments/{enrollment_id}", headers=admin)
    assert dropped.status_code == 200

    missing = await client.delete("/api/v1/enrollments/9999", headers=admin)
    assert missing.status_code == 404


async def test_score_listing_and_update(
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
    recorded = await client.post(
        "/api/v1/scores",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "course_id": seed["course_id"],
                    "usual_score": 70,
                    "exam_score": 80,
                }
            ]
        },
        headers=teacher,
    )
    assert recorded.status_code == 201
    score_id = recorded.json()[0]["id"]

    student_before = await client.get("/api/v1/scores", headers=student)
    assert student_before.status_code == 200
    assert student_before.json()["total"] == 0

    published = await client.post(
        f"/api/v1/courses/{seed['course_id']}/publish-scores", headers=teacher
    )
    assert published.status_code == 200, published.text

    student_list = await client.get("/api/v1/scores", headers=student)
    assert student_list.status_code == 200
    assert student_list.json()["total"] == 1

    filtered = await client.get(
        f"/api/v1/scores?course_id={seed['course_id']}&semester=2024-2025-1",
        headers=admin,
    )
    assert filtered.json()["total"] == 1

    patched = await client.patch(
        f"/api/v1/scores/{score_id}",
        json={"usual_score": 90, "exam_score": 80},
        headers=teacher,
    )
    assert patched.status_code == 200
    assert patched.json()["final_score"] == 84.0

    student_forbidden = await client.patch(
        f"/api/v1/scores/{score_id}", json={"usual_score": 100}, headers=student
    )
    assert student_forbidden.status_code == 403

    missing = await client.patch("/api/v1/scores/9999", json={"usual_score": 100}, headers=teacher)
    assert missing.status_code == 404


async def test_score_requires_enrollment(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    second = await client.post(
        "/api/v1/students", json={"student_no": "S201", "name": "未选课学生"}, headers=admin
    )
    second_id = second.json()["id"]

    response = await client.post(
        "/api/v1/scores",
        json={
            "items": [
                {
                    "student_id": second_id,
                    "course_id": seed["course_id"],
                    "usual_score": 60,
                    "exam_score": 60,
                }
            ]
        },
        headers=teacher,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


async def test_validation_error_shape(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    response = await client.post("/api/v1/students", json={"student_no": "X"}, headers=admin)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["details"]
