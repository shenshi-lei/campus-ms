from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient


async def _enroll(client: AsyncClient, seed: dict[str, int], admin: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/enrollments",
        json={"student_id": seed["student_id"], "course_id": seed["course_id"]},
        headers=admin,
    )
    assert response.status_code in {201, 409}


async def test_one_level_leave_and_attendance_link(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")
    await _enroll(client, seed, admin)

    tomorrow = date.today() + timedelta(days=1)
    applied = await client.post(
        "/api/v1/leaves",
        json={
            "leave_type": "personal",
            "start_at": f"{tomorrow.isoformat()}T08:00:00",
            "end_at": f"{tomorrow.isoformat()}T18:00:00",
            "reason": "家中有事",
        },
        headers=student,
    )
    assert applied.status_code == 201, applied.text
    body = applied.json()
    assert body["required_steps"] == 1
    assert body["status"] == "pending"

    pending = await client.get("/api/v1/leaves/pending", headers=teacher)
    assert pending.status_code == 200
    assert any(item["id"] == body["id"] for item in pending.json())

    approved = await client.post(
        f"/api/v1/leaves/{body['id']}/approve",
        json={"remark": "同意"},
        headers=teacher,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approvals"][0]["status"] == "approved"

    attendance = await client.get(
        f"/api/v1/attendance?student_id={seed['student_id']}", headers=admin
    )
    assert attendance.status_code == 200
    assert any(item["status"] == "leave" for item in attendance.json()["items"])


async def test_two_level_leave_flow(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    start = date.today() + timedelta(days=1)
    end = start + timedelta(days=5)
    applied = await client.post(
        "/api/v1/leaves",
        json={
            "leave_type": "sick",
            "start_at": f"{start.isoformat()}T08:00:00",
            "end_at": f"{end.isoformat()}T18:00:00",
            "reason": "住院治疗",
        },
        headers=student,
    )
    assert applied.status_code == 201, applied.text
    request_id = applied.json()["id"]
    assert applied.json()["required_steps"] == 2

    first = await client.post(
        f"/api/v1/leaves/{request_id}/approve",
        json={"remark": "情况属实"},
        headers=teacher,
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "pending"
    assert first.json()["current_step"] == 2

    again = await client.post(f"/api/v1/leaves/{request_id}/approve", json={}, headers=teacher)
    assert again.status_code == 403

    final = await client.post(
        f"/api/v1/leaves/{request_id}/approve",
        json={"remark": "同意"},
        headers=admin,
    )
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "approved"


async def test_leave_reject_and_cancel(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")
    tomorrow = date.today() + timedelta(days=1)

    def payload(reason: str) -> dict[str, str]:
        return {
            "leave_type": "personal",
            "start_at": f"{tomorrow.isoformat()}T08:00:00",
            "end_at": f"{tomorrow.isoformat()}T18:00:00",
            "reason": reason,
        }

    rejected = await client.post("/api/v1/leaves", json=payload("外出"), headers=student)
    response = await client.post(
        f"/api/v1/leaves/{rejected.json()['id']}/reject",
        json={"remark": "不同意"},
        headers=teacher,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    cancelled = await client.post("/api/v1/leaves", json=payload("临时"), headers=student)
    response = await client.post(f"/api/v1/leaves/{cancelled.json()['id']}/cancel", headers=student)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    approve_after = await client.post(
        f"/api/v1/leaves/{cancelled.json()['id']}/approve",
        json={},
        headers=teacher,
    )
    assert approve_after.status_code == 409


async def test_student_cannot_approve_leave(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    student = await auth_headers("s001", "student123")
    response = await client.get("/api/v1/leaves/pending", headers=student)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_notice_audience_and_publish_scope(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    created = await client.post(
        "/api/v1/notices",
        json={"title": "期末安排", "content": "请查看考试安排", "audience": "all"},
        headers=admin,
    )
    assert created.status_code == 201, created.text

    visible = await client.get("/api/v1/notices", headers=student)
    assert visible.status_code == 200
    assert any(item["title"] == "期末安排" for item in visible.json()["items"])

    denied = await client.post(
        "/api/v1/notices",
        json={"title": "越权通知", "audience": "all"},
        headers=teacher,
    )
    assert denied.status_code == 403

    own_class = await client.post(
        "/api/v1/notices",
        json={
            "title": "本班通知",
            "audience": "class",
            "class_id": seed["class_id"],
        },
        headers=teacher,
    )
    assert own_class.status_code == 201, own_class.text

    class_visible = await client.get("/api/v1/notices", headers=student)
    assert any(item["title"] == "本班通知" for item in class_visible.json()["items"])


async def test_seat_map_view_and_update(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    updated = await client.put(
        f"/api/v1/classes/{seed['class_id']}/seats",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "seat_no": 3,
                    "seat_row": 1,
                    "seat_col": 3,
                }
            ]
        },
        headers=teacher,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["seats"][0]["student_id"] == seed["student_id"]

    viewed = await client.get(f"/api/v1/classes/{seed['class_id']}/seats", headers=student)
    assert viewed.status_code == 200
    assert viewed.json()["seats"][0]["seat_no"] == 3

    duplicate = await client.put(
        f"/api/v1/classes/{seed['class_id']}/seats",
        json={
            "items": [
                {
                    "student_id": seed["student_id"],
                    "seat_no": 4,
                    "seat_row": 1,
                    "seat_col": 3,
                },
                {
                    "student_id": seed["student_id"],
                    "seat_no": 5,
                    "seat_row": 1,
                    "seat_col": 3,
                },
            ]
        },
        headers=admin,
    )
    assert duplicate.status_code == 409

    forbidden = await client.put(
        f"/api/v1/classes/{seed['class_id']}/seats",
        json={"items": []},
        headers=student,
    )
    assert forbidden.status_code == 403


async def test_student_status_history(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    changed = await client.post(
        f"/api/v1/students/{seed['student_id']}/status",
        json={
            "status": "suspended",
            "effective_date": date.today().isoformat(),
            "reason": "病休一学期",
        },
        headers=admin,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "suspended"

    history = await client.get(
        f"/api/v1/students/{seed['student_id']}/status-history", headers=teacher
    )
    assert history.status_code == 200
    assert history.json()[0]["to_status"] == "suspended"

    own = await client.get(f"/api/v1/students/{seed['student_id']}/status-history", headers=student)
    assert own.status_code == 200

    forbidden = await client.post(
        f"/api/v1/students/{seed['student_id']}/status",
        json={"status": "active", "effective_date": date.today().isoformat()},
        headers=teacher,
    )
    assert forbidden.status_code == 403
