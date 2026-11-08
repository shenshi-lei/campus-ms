from __future__ import annotations

from httpx import AsyncClient


async def test_enrollment_flow_and_score_lock(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    student = await auth_headers("s001", "student123")
    enrolled = await client.post(
        "/api/v1/enrollments", json={"course_id": seed["course_id"]}, headers=student
    )
    assert enrolled.status_code == 201, enrolled.text
    enrollment_id = enrolled.json()["id"]

    duplicate = await client.post(
        "/api/v1/enrollments", json={"course_id": seed["course_id"]}, headers=student
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ALREADY_ENROLLED"

    teacher = await auth_headers("t001", "teacher123")
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
    assert scored.status_code == 201, scored.text
    assert scored.json()[0]["final_score"] == 86.0

    locked = await client.delete(f"/api/v1/enrollments/{enrollment_id}", headers=student)
    assert locked.status_code == 409
    assert locked.json()["code"] == "SCORE_LOCKED"


async def test_course_capacity_is_enforced(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    second = await client.post(
        "/api/v1/students",
        json={"student_no": "S003", "name": "学生三", "class_id": seed["class_id"]},
        headers=admin,
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    first_enroll = await client.post(
        "/api/v1/enrollments",
        json={"course_id": seed["course_id"], "student_id": seed["student_id"]},
        headers=admin,
    )
    assert first_enroll.status_code == 201

    second_enroll = await client.post(
        "/api/v1/enrollments",
        json={"course_id": seed["course_id"], "student_id": second_id},
        headers=admin,
    )
    assert second_enroll.status_code == 201

    third = await client.post(
        "/api/v1/students",
        json={"student_no": "S004", "name": "学生四", "class_id": seed["class_id"]},
        headers=admin,
    )
    third_id = third.json()["id"]
    overflow = await client.post(
        "/api/v1/enrollments",
        json={"course_id": seed["course_id"], "student_id": third_id},
        headers=admin,
    )
    assert overflow.status_code == 409
    assert overflow.json()["code"] == "COURSE_FULL"


async def test_teacher_cannot_score_foreign_course(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    foreign = await client.post(
        "/api/v1/courses",
        json={"code": "CS999", "name": "外聘课程", "teacher_id": None},
        headers=admin,
    )
    assert foreign.status_code == 201
    course_id = foreign.json()["id"]

    student = await auth_headers("s001", "student123")
    enrolled = await client.post(
        "/api/v1/enrollments",
        json={"course_id": course_id, "student_id": seed["student_id"]},
        headers=student,
    )
    assert enrolled.status_code == 201

    teacher = await auth_headers("t001", "teacher123")
    response = await client.post(
        "/api/v1/scores",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "course_id": course_id,
                    "usual_score": 70,
                    "exam_score": 70,
                }
            ]
        },
        headers=teacher,
    )
    assert response.status_code == 403
