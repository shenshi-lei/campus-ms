from __future__ import annotations

from datetime import datetime, time

from httpx import AsyncClient


def _today_at(hour: int) -> str:
    return datetime.combine(datetime.now().date(), time(hour=hour)).isoformat()


async def test_calendar_event_crud_and_today(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    student = await auth_headers("s001", "student123")
    teacher = await auth_headers("t001", "teacher123")

    created = await client.post(
        "/api/v1/calendar/events",
        json={
            "title": "全校安全会议",
            "description": "安全工作部署",
            "location": "行政楼 302",
            "start_at": _today_at(9),
            "end_at": _today_at(10),
            "kind": "meeting",
            "visibility": "school",
            "participant_ids": [seed["student_user_id"]],
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    assert created.json()["owner_id"] is not None
    assert created.json()["participants"][0]["user_id"] == seed["student_user_id"]

    today = await client.get("/api/v1/calendar/today", headers=student)
    assert today.status_code == 200
    assert any(item["id"] == event_id for item in today.json())

    teacher_view = await client.get("/api/v1/calendar/today", headers=teacher)
    assert any(item["id"] == event_id for item in teacher_view.json())

    rsvp = await client.post(
        f"/api/v1/calendar/events/{event_id}/rsvp",
        json={"response": "accepted"},
        headers=student,
    )
    assert rsvp.status_code == 200
    assert any(
        item["user_id"] == seed["student_user_id"] and item["response"] == "accepted"
        for item in rsvp.json()["participants"]
    )

    updated = await client.patch(
        f"/api/v1/calendar/events/{event_id}",
        json={"location": "行政楼 401"},
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["location"] == "行政楼 401"

    deleted = await client.delete(f"/api/v1/calendar/events/{event_id}", headers=admin)
    assert deleted.status_code == 200


async def test_personal_calendar_visibility(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")

    created = await client.post(
        "/api/v1/calendar/events",
        json={
            "title": "学生个人事项",
            "start_at": _today_at(10),
            "end_at": _today_at(11),
            "kind": "personal",
            "visibility": "personal",
        },
        headers=student,
    )
    assert created.status_code == 201
    event_id = created.json()["id"]

    own = await client.get("/api/v1/calendar/today", headers=student)
    assert any(item["id"] == event_id for item in own.json())

    other = await client.get("/api/v1/calendar/today", headers=teacher)
    assert all(item["id"] != event_id for item in other.json())

    denied = await client.delete(f"/api/v1/calendar/events/{event_id}", headers=teacher)
    assert denied.status_code == 403


async def test_dashboard_includes_today_events(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    created = await client.post(
        "/api/v1/calendar/events",
        json={
            "title": "首页日程",
            "start_at": _today_at(8),
            "end_at": _today_at(9),
            "visibility": "school",
        },
        headers=admin,
    )
    assert created.status_code == 201
    overview = await client.get("/api/v1/dashboard/overview?days=7", headers=admin)
    assert overview.status_code == 200
    assert any(item["title"] == "首页日程" for item in overview.json()["today_events"])
