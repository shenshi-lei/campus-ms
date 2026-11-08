"""权限表：角色、权限点、角色授权、用户角色与用户级覆盖。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07 21:20:00

说明：基线 0001 使用元数据建表，新库会直接带上这 5 张表；本迁移面向已有库补齐，
因此先检查表是否存在，避免与基线重复创建。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    """补齐权限相关表。"""
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "roles" not in existing:
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("description", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamp_columns(),
            sa.UniqueConstraint("code", name="uq_roles_code"),
        )

    if "permissions" not in existing:
        op.create_table(
            "permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("resource", sa.String(length=40), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamp_columns(),
            sa.UniqueConstraint("code", name="uq_permissions_code"),
        )

    if "role_permissions" not in existing:
        op.create_table(
            "role_permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("roles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "permission_id",
                sa.Integer(),
                sa.ForeignKey("permissions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            *_timestamp_columns(),
            sa.UniqueConstraint(
                "role_id", "permission_id", name="uq_role_permissions_role_permission"
            ),
        )

    if "user_roles" not in existing:
        op.create_table(
            "user_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("roles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            *_timestamp_columns(),
            sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
        )

    if "user_permission_overrides" not in existing:
        op.create_table(
            "user_permission_overrides",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "permission_id",
                sa.Integer(),
                sa.ForeignKey("permissions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("effect", sa.String(length=10), nullable=False, server_default="allow"),
            *_timestamp_columns(),
            sa.UniqueConstraint(
                "user_id",
                "permission_id",
                name="uq_user_permission_overrides_user_permission",
            ),
        )


def downgrade() -> None:
    """删除权限相关表（仅删除确实存在的表）。"""
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in (
        "user_permission_overrides",
        "user_roles",
        "role_permissions",
        "permissions",
        "roles",
    ):
        if table in existing:
            op.drop_table(table)
