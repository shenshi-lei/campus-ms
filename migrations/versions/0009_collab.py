"""群组、站内消息与系统参数；补教师院系外键与通知群组受众。

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-08 00:20:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
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
    """创建群组/消息/参数表并扩展教师与通知。"""
    if not _has_table("user_groups"):
        op.create_table(
            "user_groups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("kind", sa.String(length=30), nullable=False, server_default="custom"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column(
                "created_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            *_timestamps(),
            sa.UniqueConstraint("code", name="uq_user_groups_code"),
            sa.UniqueConstraint("name", name="uq_user_groups_name"),
        )
        op.create_index("ix_user_groups_code", "user_groups", ["code"])

    if not _has_table("user_group_members"):
        op.create_table(
            "user_group_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "group_id",
                sa.Integer(),
                sa.ForeignKey("user_groups.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("member_type", sa.String(length=20), nullable=False),
            sa.Column("member_id", sa.Integer(), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("display_name", sa.String(length=100), nullable=False, server_default=""),
            *_timestamps(),
            sa.UniqueConstraint(
                "group_id",
                "member_type",
                "member_id",
                name="uq_user_group_members_target",
            ),
        )

    if not _has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("kind", sa.String(length=20), nullable=False, server_default="system"),
            sa.Column("title", sa.String(length=100), nullable=False),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("link", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamps(),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
        op.create_index("ix_notifications_is_read", "notifications", ["is_read"])

    if not _has_table("system_settings"):
        op.create_table(
            "system_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(length=100), nullable=False),
            sa.Column("value", sa.Text(), nullable=False, server_default=""),
            sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
            *_timestamps(),
            sa.UniqueConstraint("key", name="uq_system_settings_key"),
        )
        op.create_index("ix_system_settings_key", "system_settings", ["key"])

    notice_columns = _columns("notices")
    with op.batch_alter_table("notices") as batch:
        if "group_id" not in notice_columns:
            batch.add_column(sa.Column("group_id", sa.Integer(), nullable=True))

    teacher_columns = _columns("teachers")
    with op.batch_alter_table("teachers") as batch:
        if "department_id" not in teacher_columns:
            batch.add_column(sa.Column("department_id", sa.Integer(), nullable=True))

    if _has_table("departments"):
        op.execute(
            sa.text(
                "UPDATE teachers SET department_id = ("
                "SELECT departments.id FROM departments "
                "WHERE departments.name = teachers.department"
                ") WHERE department_id IS NULL AND department <> ''"
            )
        )


def downgrade() -> None:
    """回滚群组/消息/参数扩展。"""
    teacher_columns = _columns("teachers")
    with op.batch_alter_table("teachers") as batch:
        if "department_id" in teacher_columns:
            batch.drop_column("department_id")

    notice_columns = _columns("notices")
    with op.batch_alter_table("notices") as batch:
        if "group_id" in notice_columns:
            batch.drop_column("group_id")

    if _has_table("system_settings"):
        op.drop_table("system_settings")
    if _has_table("notifications"):
        op.drop_table("notifications")
    if _has_table("user_group_members"):
        op.drop_table("user_group_members")
    if _has_table("user_groups"):
        op.drop_table("user_groups")
