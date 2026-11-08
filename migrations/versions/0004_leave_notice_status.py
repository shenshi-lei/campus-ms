"""请假审批、通知与学籍异动。

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07 22:05:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """创建请假、通知与学籍异动表。"""
    if not _has_table("leave_requests"):
        op.create_table(
            "leave_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "applicant_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("applicant_type", sa.String(length=20), nullable=False),
            sa.Column(
                "student_id",
                sa.Integer(),
                sa.ForeignKey("students.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "teacher_id",
                sa.Integer(),
                sa.ForeignKey("teachers.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("leave_type", sa.String(length=20), nullable=False),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("days", sa.Numeric(4, 1), nullable=False, server_default="1"),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("required_steps", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "final_approver_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamp_columns(),
            sa.CheckConstraint(
                "(student_id IS NOT NULL) <> (teacher_id IS NOT NULL)",
                name="ck_leave_requests_applicant",
            ),
        )

    if not _has_table("leave_approvals"):
        op.create_table(
            "leave_approvals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "leave_request_id",
                sa.Integer(),
                sa.ForeignKey("leave_requests.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("step_no", sa.Integer(), nullable=False),
            sa.Column("approver_role_code", sa.String(length=50), nullable=False),
            sa.Column(
                "approver_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("remark", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamp_columns(),
            sa.UniqueConstraint(
                "leave_request_id", "step_no", name="uq_leave_approvals_request_step"
            ),
        )

    if not _has_table("leave_policies"):
        op.create_table(
            "leave_policies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("applicant_type", sa.String(length=20), nullable=False),
            sa.Column("step_no", sa.Integer(), nullable=False),
            sa.Column("approver_role_code", sa.String(length=50), nullable=False),
            sa.Column("min_days", sa.Numeric(4, 1), nullable=False, server_default="0"),
            *_timestamp_columns(),
            sa.UniqueConstraint("applicant_type", "step_no", name="uq_leave_policies_type_step"),
        )

    if not _has_table("notices"):
        op.create_table(
            "notices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=100), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("audience", sa.String(length=20), nullable=False, server_default="all"),
            sa.Column(
                "class_id",
                sa.Integer(),
                sa.ForeignKey("school_classes.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "publisher_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamp_columns(),
        )

    if not _has_table("student_status_history"):
        op.create_table(
            "student_status_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "student_id",
                sa.Integer(),
                sa.ForeignKey("students.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("from_status", sa.String(length=20), nullable=True),
            sa.Column("to_status", sa.String(length=20), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.String(length=200), nullable=False, server_default=""),
            sa.Column(
                "operator_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            *_timestamp_columns(),
        )


def downgrade() -> None:
    """删除请假、通知与学籍异动表。"""
    for table in (
        "student_status_history",
        "notices",
        "leave_policies",
        "leave_approvals",
        "leave_requests",
    ):
        if _has_table(table):
            op.drop_table(table)
