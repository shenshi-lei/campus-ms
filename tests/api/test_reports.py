from __future__ import annotations

from httpx import AsyncClient


async def test_workload_report_and_scope(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    all_rows = await client.get("/api/v1/reports/workload", headers=admin)
    assert all_rows.status_code == 200, all_rows.text
    assert len(all_rows.json()) >= 1
    item = all_rows.json()[0]
    assert {"teacher_no", "course_count", "weekly_periods", "student_count"} <= set(item)

    own = await client.get("/api/v1/reports/workload", headers=teacher)
    assert own.status_code == 200
    assert [row["teacher_id"] for row in own.json()] == [seed["teacher_id"]]

    denied = await client.get("/api/v1/reports/workload", headers=student)
    assert denied.status_code == 403


async def test_subject_and_class_reports(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    subject = await client.post(
        "/api/v1/org/subjects", json={"code": "RPT", "name": "报表学科"}, headers=admin
    )
    assert subject.status_code == 201
    patched = await client.patch(
        f"/api/v1/courses/{seed['course_id']}",
        json={"subject_id": subject.json()["id"]},
        headers=admin,
    )
    assert patched.status_code == 200

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
                    "usual_score": 70,
                    "exam_score": 90,
                }
            ]
        },
        headers=teacher,
    )

    subjects = await client.get("/api/v1/reports/subjects", headers=admin)
    assert subjects.status_code == 200, subjects.text
    target = next(item for item in subjects.json() if item["subject_name"] == "报表学科")
    assert target["course_count"] == 1
    assert target["average_score"] == 82.0
    assert target["pass_rate"] == 100.0

    classes = await client.get("/api/v1/reports/classes", headers=admin)
    assert classes.status_code == 200
    class_row = next(item for item in classes.json() if item["class_id"] == seed["class_id"])
    assert class_row["student_count"] == 1

    teacher_classes = await client.get("/api/v1/reports/classes", headers=teacher)
    assert teacher_classes.status_code == 200
    assert all(item["class_id"] == seed["class_id"] for item in teacher_classes.json())
