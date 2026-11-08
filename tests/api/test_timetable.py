from __future__ import annotations

from httpx import AsyncClient


async def test_timetable_grid_day_month_and_detail(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")

    semester = await client.post(
        "/api/v1/org/semesters",
        json={
            "name": "2099-2100-1",
            "start_date": "2026-11-02",
            "end_date": "2027-01-31",
            "weeks": 20,
            "is_current": True,
        },
        headers=admin,
    )
    assert semester.status_code == 201, semester.text
    semester_id = semester.json()["id"]

    created = await client.post(
        "/api/v1/schedules",
        json={
            "course_id": seed["course_id"],
            "semester_id": semester_id,
            "class_id": seed["class_id"],
            "weekday": 1,
            "start_period": 1,
            "end_period": 2,
            "classroom": "A101",
            "weeks": "1-20",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]

    grid = await client.get(
        f"/api/v1/schedules/grid?semester_id={semester_id}&week=1&class_id={seed['class_id']}",
        headers=admin,
    )
    assert grid.status_code == 200, grid.text
    assert grid.json()["week"] == 1
    assert any(item["id"] == schedule_id for item in grid.json()["entries"])
    assert len(grid.json()["periods"]) >= 8

    day = await client.get(
        f"/api/v1/schedules/day?date=2026-11-02&semester_id={semester_id}&class_id={seed['class_id']}",
        headers=admin,
    )
    assert day.status_code == 200, day.text
    assert any(item["id"] == schedule_id for item in day.json()["entries"])

    month = await client.get(
        f"/api/v1/schedules/month?month=2026-11&class_id={seed['class_id']}",
        headers=admin,
    )
    assert month.status_code == 200, month.text
    assert any(
        any(item["id"] == schedule_id for item in day_item["entries"])
        for day_item in month.json()["days"]
    )

    detail = await client.get(f"/api/v1/schedules/{schedule_id}/detail", headers=admin)
    assert detail.status_code == 200, detail.text
    assert detail.json()["course_name"] == "程序设计"
    assert detail.json()["class_name"] == "计算机2301"

    conflict = await client.post(
        "/api/v1/schedules",
        json={
            "course_id": seed["course_id"],
            "semester_id": semester_id,
            "class_id": seed["class_id"],
            "weekday": 1,
            "start_period": 2,
            "end_period": 3,
            "classroom": "A101",
            "weeks": "1-20",
        },
        headers=admin,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "CONFLICT"


async def test_student_timetable_scope(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    student = await auth_headers("s001", "student123")
    semester = await client.post(
        "/api/v1/org/semesters",
        json={
            "name": "2099-2100-2",
            "start_date": "2026-11-02",
            "end_date": "2027-01-31",
            "weeks": 20,
            "is_current": True,
        },
        headers=admin,
    )
    semester_id = semester.json()["id"]
    enrolled = await client.post(
        "/api/v1/enrollments",
        json={"student_id": seed["student_id"], "course_id": seed["course_id"]},
        headers=admin,
    )
    assert enrolled.status_code in {201, 409}
    await client.post(
        "/api/v1/schedules",
        json={
            "course_id": seed["course_id"],
            "semester_id": semester_id,
            "class_id": seed["class_id"],
            "weekday": 1,
            "start_period": 1,
            "end_period": 2,
            "classroom": "A101",
            "weeks": "1-20",
        },
        headers=admin,
    )
    grid = await client.get(
        f"/api/v1/schedules/grid?semester_id={semester_id}&week=1", headers=student
    )
    assert grid.status_code == 200
    assert len(grid.json()["entries"]) >= 1
