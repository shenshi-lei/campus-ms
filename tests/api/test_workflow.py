from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient


async def _create_flow(client: AsyncClient, admin: dict[str, str]) -> int:
    response = await client.post(
        "/api/v1/leaves/flows",
        json={
            "code": "student_two_step",
            "name": "学生两级审批",
            "applicant_type": "student",
            "min_days": 3,
            "is_active": True,
            "priority": 100,
            "steps": [
                {
                    "step_no": 1,
                    "name": "班主任审批",
                    "approver_type": "head_teacher",
                    "role_code": "head_teacher",
                },
                {
                    "step_no": 2,
                    "name": "管理员审批",
                    "approver_type": "role",
                    "role_code": "admin",
                },
            ],
        },
        headers=admin,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def test_leave_flow_config_and_two_step_approval(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")
    flow_id = await _create_flow(client, admin)

    flows = await client.get("/api/v1/leaves/flows", headers=admin)
    assert flows.status_code == 200
    assert any(item["id"] == flow_id for item in flows.json())

    teacher_denied = await client.get("/api/v1/leaves/flows", headers=teacher)
    assert teacher_denied.status_code == 403

    preview = await client.get(
        "/api/v1/leaves/flows/preview?applicant_type=student&leave_type=personal&days=5",
        headers=admin,
    )
    assert preview.status_code == 200
    assert preview.json()["matched"] is True
    assert preview.json()["flow"]["id"] == flow_id

    tomorrow = date.today() + timedelta(days=1)
    applied = await client.post(
        "/api/v1/leaves",
        json={
            "leave_type": "sick",
            "start_at": f"{tomorrow.isoformat()}T08:00:00",
            "end_at": f"{(tomorrow + timedelta(days=4)).isoformat()}T18:00:00",
            "reason": "住院治疗",
        },
        headers=student,
    )
    assert applied.status_code == 201, applied.text
    body = applied.json()
    assert body["flow_id"] == flow_id
    assert body["required_steps"] == 2
    assert [item["step_name"] for item in body["approvals"]] == ["班主任审批", "管理员审批"]
    request_id = body["id"]

    pending = await client.get("/api/v1/leaves/pending", headers=teacher)
    assert pending.status_code == 200
    assert any(item["id"] == request_id for item in pending.json())

    approved = await client.post(
        f"/api/v1/leaves/{request_id}/approve",
        json={"remark": "同意"},
        headers=teacher,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["current_step"] == 2
    assert approved.json()["status"] == "pending"

    admin_pending = await client.get("/api/v1/leaves/pending", headers=admin)
    assert any(item["id"] == request_id for item in admin_pending.json())
    final = await client.post(
        f"/api/v1/leaves/{request_id}/approve",
        json={"remark": "同意"},
        headers=admin,
    )
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "approved"
    assert len(final.json()["events"]) >= 4

    notifications = await client.get("/api/v1/notifications/summary", headers=admin)
    assert notifications.status_code == 200
    assert notifications.json()["unread"] >= 1


async def test_leave_flow_reject_and_cancel(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    teacher = await auth_headers("t001", "teacher123")
    student = await auth_headers("s001", "student123")
    await _create_flow(client, admin)

    tomorrow = date.today() + timedelta(days=1)
    applied = await client.post(
        "/api/v1/leaves",
        json={
            "leave_type": "personal",
            "start_at": f"{tomorrow.isoformat()}T08:00:00",
            "end_at": f"{(tomorrow + timedelta(days=4)).isoformat()}T18:00:00",
            "reason": "家中有事",
        },
        headers=student,
    )
    request_id = applied.json()["id"]

    rejected = await client.post(
        f"/api/v1/leaves/{request_id}/reject",
        json={"remark": "材料不足"},
        headers=teacher,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["actions"]["can_cancel"] is False

    second = await client.post(
        "/api/v1/leaves",
        json={
            "leave_type": "personal",
            "start_at": f"{tomorrow.isoformat()}T08:00:00",
            "end_at": f"{tomorrow.isoformat()}T18:00:00",
            "reason": "临时事项",
        },
        headers=student,
    )
    second_id = second.json()["id"]
    cancelled = await client.post(f"/api/v1/leaves/{second_id}/cancel", headers=student)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_leave_flow_validation_rejects_empty_steps(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")
    response = await client.post(
        "/api/v1/leaves/flows",
        json={
            "code": "empty_flow",
            "name": "空流程",
            "applicant_type": "student",
            "is_active": True,
            "steps": [],
        },
        headers=admin,
    )
    assert response.status_code == 409
    assert response.json()["code"] in {"CONFLICT", "REFERENCE_EXISTS"}
