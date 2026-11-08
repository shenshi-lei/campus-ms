"""可配置请假流程：流程、节点、流转事件与审批快照。

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08 00:10:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    """创建请假流程表并扩展申请/审批/考勤。"""
    if not _has_table("leave_flows"):
        op.create_table(
            "leave_flows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("applicant_type", sa.String(length=20), nullable=True),
            sa.Column("leave_type", sa.String(length=20), nullable=True),
            sa.Column("min_days", sa.Numeric(4, 1), nullable=False, server_default="0"),
            sa.Column("max_days", sa.Numeric(4, 1), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
            *_timestamps(),
            sa.UniqueConstraint("code", name="uq_leave_flows_code"),
        )
        op.create_index("ix_leave_flows_code", "leave_flows", ["code"])

    if not _has_table("leave_flow_steps"):
        op.create_table(
            "leave_flow_steps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "flow_id",
                sa.Integer(),
                sa.ForeignKey("leave_flows.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("step_no", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("approver_type", sa.String(length=20), nullable=False, server_default="role"),
            sa.Column("role_code", sa.String(length=50), nullable=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "group_id",
                sa.Integer(),
                sa.ForeignKey("user_groups.id", ondelete="SET NULL"),
                nullable=True,
            ),
            *_timestamps(),
            sa.UniqueConstraint("flow_id", "step_no", name="uq_leave_flow_steps_flow_step"),
        )

    if not _has_table("leave_events"):
        op.create_table(
            "leave_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "leave_request_id",
                sa.Integer(),
                sa.ForeignKey("leave_requests.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column(
                "actor_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("actor_name", sa.String(length=50), nullable=False, server_default=""),
            sa.Column("detail", sa.String(length=500), nullable=False, server_default=""),
            *_timestamps(),
        )

    request_columns = _columns("leave_requests")
    with op.batch_alter_table("leave_requests") as batch:
        if "flow_id" not in request_columns:
            batch.add_column(sa.Column("flow_id", sa.Integer(), nullable=True))
        if "flow_name" not in request_columns:
            batch.add_column(
                sa.Column("flow_name", sa.String(length=100), nullable=False, server_default="")
            )

    approval_columns = _columns("leave_approvals")
    with op.batch_alter_table("leave_approvals") as batch:
        if "step_name" not in approval_columns:
            batch.add_column(
                sa.Column("step_name", sa.String(length=50), nullable=False, server_default="")
            )
        if "approver_type" not in approval_columns:
            batch.add_column(
                sa.Column(
                    "approver_type", sa.String(length=20), nullable=False, server_default="role"
                )
            )
        if "approver_user_id" not in approval_columns:
            batch.add_column(sa.Column("approver_user_id", sa.Integer(), nullable=True))
        if "approver_group_id" not in approval_columns:
            batch.add_column(sa.Column("approver_group_id", sa.Integer(), nullable=True))
        if "assigned_at" not in approval_columns:
            batch.add_column(sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))

    attendance_columns = _columns("attendance")
    with op.batch_alter_table("attendance") as batch:
        if "leave_request_id" not in attendance_columns:
            batch.add_column(sa.Column("leave_request_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    """回滚请假流程扩展。"""
    attendance_columns = _columns("attendance")
    with op.batch_alter_table("attendance") as batch:
        if "leave_request_id" in attendance_columns:
            batch.drop_column("leave_request_id")

    approval_columns = _columns("leave_approvals")
    with op.batch_alter_table("leave_approvals") as batch:
        for column in (
            "assigned_at",
            "approver_group_id",
            "approver_user_id",
            "approver_type",
            "step_name",
        ):
            if column in approval_columns:
                batch.drop_column(column)

    request_columns = _columns("leave_requests")
    with op.batch_alter_table("leave_requests") as batch:
        for column in ("flow_name", "flow_id"):
            if column in request_columns:
                batch.drop_column(column)

    if _has_table("leave_events"):
        op.drop_table("leave_events")
    if _has_table("leave_flow_steps"):
        op.drop_table("leave_flow_steps")
    if _has_table("leave_flows"):
        op.drop_table("leave_flows")
