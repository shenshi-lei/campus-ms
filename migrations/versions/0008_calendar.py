"""日程：事件与参与人。

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-08 00:15:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    """创建日程表。"""
    if not _has_table("calendar_events"):
        op.create_table(
            "calendar_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("location", sa.String(length=100), nullable=False, server_default=""),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("all_day", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("kind", sa.String(length=20), nullable=False, server_default="other"),
            sa.Column(
                "visibility", sa.String(length=20), nullable=False, server_default="personal"
            ),
            sa.Column(
                "owner_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "department_id",
                sa.Integer(),
                sa.ForeignKey("departments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "class_id",
                sa.Integer(),
                sa.ForeignKey("school_classes.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("remind_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("color", sa.String(length=20), nullable=False, server_default=""),
            sa.Column("is_cancelled", sa.Boolean(), nullable=False, server_default="0"),
            *_timestamps(),
        )
        op.create_index("ix_calendar_events_start_at", "calendar_events", ["start_at"])

    if not _has_table("calendar_event_attendees"):
        op.create_table(
            "calendar_event_attendees",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "event_id",
                sa.Integer(),
                sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("response", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default="1"),
            *_timestamps(),
            sa.UniqueConstraint(
                "event_id", "user_id", name="uq_calendar_event_attendees_event_user"
            ),
        )


def downgrade() -> None:
    """删除日程表。"""
    if _has_table("calendar_event_attendees"):
        op.drop_table("calendar_event_attendees")
    if _has_table("calendar_events"):
        op.drop_table("calendar_events")
