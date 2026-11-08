"""操作审计日志。

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-07 22:50:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建审计日志表（新库已由基线创建则跳过）。"""
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "audit_logs" in existing:
        return
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("username", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("ip", sa.String(length=45), nullable=False, server_default=""),
        sa.Column("detail", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    """删除审计日志表。"""
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "audit_logs" in existing:
        op.drop_table("audit_logs")
