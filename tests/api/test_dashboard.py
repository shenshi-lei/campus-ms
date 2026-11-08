from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from campus.db.base import utc_now
from campus.models.attendance import Attendance
from campus.models.enrollment import Enrollment
from campus.models.enums import AttendanceStatus, FeeStatus
from campus.models.fee import Fee
from campus.models.schedule import Schedule
from campus.models.score import Score


@pytest.fixture
async def dashboard_seed(app: object, seed: dict[str, int]) -> dict[str, int]:
    """在基础种子上补齐考勤、成绩、费用与排课。"""
    factory = app.state.session_factory
    today = date.today()
    async with factory() as session:
        enrollment = Enrollment(student_id=seed["student_id"], course_id=seed["course_id"])
        session.add(enrollment)
        await session.flush()
        session.add_all(
            [
                Attendance(
                    student_id=seed["student_id"],
                    course_id=seed["course_id"],
                    date=today,
                    status=AttendanceStatus.LATE,
                ),
                Attendance(
                    student_id=seed["student_id"],
                    course_id=seed["course_id"],
                    date=today - timedelta(days=1),
                    status=AttendanceStatus.ABSENT,
                ),
                Score(
                    enrollment_id=enrollment.id,
                    usual_score=70.0,
                    exam_score=50.0,
                    final_score=58.0,
                    recorded_at=utc_now(),
                ),
                Fee(
                    student_id=seed["student_id"],
                    item="学费",
                    amount=1000.0,
                    due_date=today - timedelta(days=3),
                    status=FeeStatus.UNPAID,
                ),
                Schedule(
                    course_id=seed["course_id"],
                    weekday=today.isoweekday(),
                    start_period=1,
                    end_period=2,
                    classroom="A101",
                    weeks="1-16",
                ),
            ]
        )
        await session.commit()
    return seed


async def test_dashboard_overview_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard/overview")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_admin_overview_contains_all_sections(
    client: AsyncClient, dashboard_seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("admin", "admin123")

    response = await client.get("/api/v1/dashboard/overview?days=30", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "admin"
    assert body["days"] == 30
    assert body["semester"] == "2024-2025-1"
    assert len(body["kpis"]) == 5
    assert body["attendance_trend"]["rate"] == 50.0
    assert len(body["attendance_trend"]["labels"]) == 30
    assert body["attendance_trend"]["series"][0]["name"] == "出勤"
    assert body["score_distribution"]["sample"] == 1
    assert body["score_distribution"]["buckets"][0] == {"label": "<60", "count": 1}
    assert body["fee_breakdown"]["overdue_count"] == 1
    assert body["fee_breakdown"]["unpaid_amount"] == 1000.0
    assert body["course_load"][0]["enrolled"] == 1
    assert body["course_load"][0]["rate"] == 50.0
    assert body["class_comparison"][0]["students"] == 1
    assert body["alerts"]
    assert body["recent"]


async def test_teacher_overview_scopes_to_own_courses(
    client: AsyncClient, dashboard_seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("t001", "teacher123")

    response = await client.get("/api/v1/dashboard/overview", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "teacher"
    assert body["student"] is None
    assert body["teacher"]["courses"][0]["students"] == 1
    assert body["teacher"]["courses"][0]["pending"] == 0
    assert body["course_load"][0]["course_id"] == dashboard_seed["course_id"]
    assert body["attendance_trend"]["rate"] == 50.0


async def test_student_overview_returns_personal_panel(
    client: AsyncClient, dashboard_seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("s001", "student123")

    response = await client.get("/api/v1/dashboard/overview", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "student"
    assert body["teacher"] is None
    assert body["student"]["failed_courses"] == 1
    assert body["student"]["gpa"] == 0.0
    assert body["student"]["credits"] == 0.0
    assert body["student"]["today"][0]["classroom"] == "A101"
    assert body["fee_breakdown"]["unpaid_count"] == 1
    assert body["fee_breakdown"]["overdue_count"] == 1


async def test_overview_rejects_invalid_days(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    headers = await auth_headers("admin", "admin123")

    response = await client.get("/api/v1/dashboard/overview?days=3", headers=headers)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
