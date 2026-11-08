from __future__ import annotations

from datetime import date

from httpx import AsyncClient


async def test_course_extended_fields_and_teacher_links(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    subject = await client.post(
        "/api/v1/org/subjects", json={"code": "PHY2", "name": "物理二"}, headers=admin
    )
    assert subject.status_code == 201

    created = await client.post(
        "/api/v1/courses",
        json={
            "code": "PHY201",
            "name": "大学物理",
            "subject_id": subject.json()["id"],
            "course_type": "required",
            "assessment_type": "exam",
            "grade_scheme": {"usual": 0.3, "midterm": 0.2, "exam": 0.5},
            "textbook": "《大学物理》",
            "grade_year": 2023,
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    course_id = created.json()["id"]
    assert created.json()["course_type"] == "required"
    assert created.json()["grade_scheme"]["midterm"] == 0.2

    set_teachers = await client.put(
        f"/api/v1/courses/{course_id}/teachers",
        json={"items": [{"teacher_id": seed["teacher_id"], "role": "assistant"}]},
        headers=admin,
    )
    assert set_teachers.status_code == 200, set_teachers.text
    assert set_teachers.json()[0]["role"] == "assistant"

    listed_teachers = await client.get(f"/api/v1/courses/{course_id}/teachers", headers=teacher)
    assert listed_teachers.status_code == 200
    assert listed_teachers.json()[0]["teacher_id"] == seed["teacher_id"]

    set_classes = await client.put(
        f"/api/v1/courses/{course_id}/classes",
        json={"items": [{"class_id": seed["class_id"]}]},
        headers=admin,
    )
    assert set_classes.status_code == 200
    assert set_classes.json()[0]["class_name"]

    denied = await client.put(
        f"/api/v1/courses/{course_id}/teachers",
        json={"items": []},
        headers=teacher,
    )
    assert denied.status_code == 403


async def test_grade_scheme_and_publish(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    course = await client.post(
        "/api/v1/courses",
        json={
            "code": "GS101",
            "name": "成绩构成测试",
            "grade_scheme": {"usual": 0.3, "midterm": 0.2, "exam": 0.5},
        },
        headers=admin,
    )
    assert course.status_code == 201
    course_id = course.json()["id"]
    await client.patch(
        f"/api/v1/courses/{course_id}",
        json={"teacher_id": seed["teacher_id"]},
        headers=admin,
    )
    enrolled = await client.post(
        "/api/v1/enrollments",
        json={"student_id": seed["student_id"], "course_id": course_id},
        headers=admin,
    )
    assert enrolled.status_code == 201

    recorded = await client.post(
        "/api/v1/scores",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "course_id": course_id,
                    "usual_score": 80,
                    "midterm_score": 90,
                    "exam_score": 100,
                }
            ]
        },
        headers=teacher,
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()[0]["final_score"] == 92.0

    before = await client.get("/api/v1/scores", headers=student)
    assert before.json()["total"] == 0

    published = await client.post(f"/api/v1/courses/{course_id}/publish-scores", headers=teacher)
    assert published.status_code == 200

    after = await client.get("/api/v1/scores", headers=student)
    assert after.json()["total"] == 1

    unpublish_denied = await client.post(
        f"/api/v1/courses/{course_id}/unpublish-scores", headers=teacher
    )
    assert unpublish_denied.status_code == 403

    unpublished = await client.post(f"/api/v1/courses/{course_id}/unpublish-scores", headers=admin)
    assert unpublished.status_code == 200
    assert (await client.get("/api/v1/scores", headers=student)).json()["total"] == 0


async def test_attendance_by_period(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    day = date.today().isoformat()
    bulk = await client.post(
        "/api/v1/attendance/bulk",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "course_id": seed["course_id"],
                    "date": day,
                    "period_no": 1,
                    "status": "present",
                },
                {
                    "student_id": seed["student_id"],
                    "course_id": seed["course_id"],
                    "date": day,
                    "period_no": 2,
                    "status": "late",
                },
            ]
        },
        headers=teacher,
    )
    assert bulk.status_code == 201, bulk.text
    periods = {item["period_no"] for item in bulk.json()}
    assert periods == {1, 2}

    listed = await client.get(f"/api/v1/attendance?student_id={seed['student_id']}", headers=admin)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2


async def test_schedule_change_request_and_admin_approval(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    created = await client.post(
        "/api/v1/schedules",
        json={
            "course_id": seed["course_id"],
            "weekday": 3,
            "start_period": 5,
            "end_period": 6,
            "classroom": "C301",
        },
        headers=teacher,
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]

    requested = await client.post(
        "/api/v1/schedule-changes",
        json={
            "schedule_id": schedule_id,
            "change_date": date.today().isoformat(),
            "kind": "cancel",
            "reason": "教师出差",
        },
        headers=teacher,
    )
    assert requested.status_code == 201, requested.text
    change_id = requested.json()["id"]
    assert requested.json()["status"] == "pending"

    denied = await client.post(
        f"/api/v1/schedule-changes/{change_id}/approve", json={}, headers=teacher
    )
    assert denied.status_code == 403

    approved = await client.post(
        f"/api/v1/schedule-changes/{change_id}/approve",
        json={"remark": "同意"},
        headers=admin,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    schedules = await client.get("/api/v1/schedules?weekday=3", headers=admin)
    target = next(item for item in schedules.json()["items"] if item["id"] == schedule_id)
    assert target["status"] == "cancelled"
