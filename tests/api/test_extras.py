from __future__ import annotations

from httpx import AsyncClient


async def test_attendance_bulk_and_fee_payment(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    teacher = await auth_headers("t001", "teacher123")
    attendance = await client.post(
        "/api/v1/attendance/bulk",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "course_id": seed["course_id"],
                    "date": "2026-11-07",
                    "status": "present",
                }
            ]
        },
        headers=teacher,
    )
    assert attendance.status_code == 201, attendance.text
    assert attendance.json()[0]["status"] == "present"

    admin = await auth_headers("admin", "admin123")
    fee = await client.post(
        "/api/v1/fees",
        json={
            "student_id": seed["student_id"],
            "item": "学费",
            "amount": 5000,
            "due_date": "2026-12-31",
        },
        headers=admin,
    )
    assert fee.status_code == 201, fee.text

    student = await auth_headers("s001", "student123")
    paid = await client.post(f"/api/v1/fees/{fee.json()['id']}/pay", headers=student)
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"


async def test_dorm_capacity_and_gender_rules(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    dorm = await client.post(
        "/api/v1/dorms",
        json={"building": "A", "room_no": "101", "capacity": 1, "gender": "male"},
        headers=admin,
    )
    assert dorm.status_code == 201, dorm.text
    dorm_id = dorm.json()["id"]

    assigned = await client.post(
        "/api/v1/dorms/assignments",
        json={"student_id": seed["student_id"], "dorm_id": dorm_id, "bed_no": 1},
        headers=admin,
    )
    assert assigned.status_code == 201, assigned.text

    second = await client.post(
        "/api/v1/students",
        json={"student_no": "S005", "name": "学生五", "class_id": seed["class_id"]},
        headers=admin,
    )
    overflow = await client.post(
        "/api/v1/dorms/assignments",
        json={"student_id": second.json()["id"], "dorm_id": dorm_id, "bed_no": 2},
        headers=admin,
    )
    assert overflow.status_code == 409


async def test_schedule_slot_conflict(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    payload = {
        "course_id": seed["course_id"],
        "weekday": 1,
        "start_period": 1,
        "end_period": 2,
        "classroom": "A101",
    }
    first = await client.post("/api/v1/schedules", json=payload, headers=admin)
    assert first.status_code == 201, first.text

    duplicate = await client.post("/api/v1/schedules", json=payload, headers=admin)
    assert duplicate.status_code == 409
