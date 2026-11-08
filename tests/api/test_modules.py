from __future__ import annotations

from httpx import AsyncClient


async def test_schedule_lifecycle(client: AsyncClient, seed: dict[str, int], auth_headers) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    payload = {
        "course_id": seed["course_id"],
        "weekday": 2,
        "start_period": 3,
        "end_period": 4,
        "classroom": "B201",
    }
    created = await client.post("/api/v1/schedules", json=payload, headers=teacher)
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]

    listed = await client.get("/api/v1/schedules?weekday=2", headers=admin)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    forbidden = await client.post("/api/v1/schedules", json=payload, headers=student)
    assert forbidden.status_code == 403

    deleted = await client.delete(f"/api/v1/schedules/{schedule_id}", headers=admin)
    assert deleted.status_code == 200

    missing = await client.delete("/api/v1/schedules/9999", headers=admin)
    assert missing.status_code == 404


async def test_attendance_listing_and_scope(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    bulk = await client.post(
        "/api/v1/attendance/bulk",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "course_id": seed["course_id"],
                    "date": "2026-11-06",
                    "status": "late",
                    "remark": "迟到十分钟",
                }
            ]
        },
        headers=teacher,
    )
    assert bulk.status_code == 201

    by_day = await client.get("/api/v1/attendance?day=2026-11-06", headers=admin)
    assert by_day.json()["total"] == 1

    own = await client.get("/api/v1/attendance", headers=student)
    assert own.json()["total"] == 1
    assert own.json()["items"][0]["status"] == "late"

    foreign = await client.post(
        "/api/v1/courses", json={"code": "CS401", "name": "无主讲课程"}, headers=admin
    )
    forbidden = await client.post(
        "/api/v1/attendance/bulk",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "course_id": foreign.json()["id"],
                    "date": "2026-11-06",
                    "status": "present",
                }
            ]
        },
        headers=teacher,
    )
    assert forbidden.status_code == 403


async def test_dorm_assign_and_guards(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")

    denied = await client.post(
        "/api/v1/dorms",
        json={"building": "C", "room_no": "101", "capacity": 2},
        headers=teacher,
    )
    assert denied.status_code == 403

    created = await client.post(
        "/api/v1/dorms",
        json={"building": "C", "room_no": "101", "capacity": 2, "gender": "male"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    dorm_id = created.json()["id"]

    listed = await client.get("/api/v1/dorms?building=C", headers=admin)
    assert listed.json()["total"] == 1

    assigned = await client.post(
        "/api/v1/dorms/assignments",
        json={"student_id": seed["student_id"], "dorm_id": dorm_id, "bed_no": 1},
        headers=admin,
    )
    assert assigned.status_code == 201
    assignment_id = assigned.json()["id"]

    duplicate = await client.post(
        "/api/v1/dorms/assignments",
        json={"student_id": seed["student_id"], "dorm_id": dorm_id, "bed_no": 2},
        headers=admin,
    )
    assert duplicate.status_code == 409

    assignments = await client.get(f"/api/v1/dorms/assignments?dorm_id={dorm_id}", headers=admin)
    assert assignments.json()["total"] == 1

    blocked = await client.delete(f"/api/v1/dorms/{dorm_id}", headers=admin)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "REFERENCE_EXISTS"

    left = await client.delete(f"/api/v1/dorms/assignments/{assignment_id}", headers=admin)
    assert left.status_code == 200

    removed = await client.delete(f"/api/v1/dorms/{dorm_id}", headers=admin)
    assert removed.status_code == 200


async def test_fee_listing_and_payment(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    created = await client.post(
        "/api/v1/fees",
        json={
            "student_id": seed["student_id"],
            "item": "住宿费",
            "amount": 1200,
            "due_date": "2026-12-31",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    fee_id = created.json()["id"]

    unpaid = await client.get("/api/v1/fees?status=unpaid", headers=admin)
    assert unpaid.json()["total"] == 1

    own = await client.get("/api/v1/fees", headers=student)
    assert own.json()["total"] == 1

    teacher_denied = await client.post(f"/api/v1/fees/{fee_id}/pay", headers=teacher)
    assert teacher_denied.status_code == 403

    paid = await client.post(f"/api/v1/fees/{fee_id}/pay", headers=student)
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"

    again = await client.post(f"/api/v1/fees/{fee_id}/pay", headers=admin)
    assert again.status_code == 409

    missing = await client.post("/api/v1/fees/9999/pay", headers=admin)
    assert missing.status_code == 404


async def test_dashboard_summary(client: AsyncClient, seed: dict[str, int], auth_headers) -> None:
    student = await auth_headers("s001", "student123")
    response = await client.get("/api/v1/dashboard/summary", headers=student)
    assert response.status_code == 200
    body = response.json()
    assert body["students"] == 1
    assert body["teachers"] == 1
    assert body["courses"] == 1
    assert "attendance_rate" in body
