"""基线迁移：按 ORM 元数据创建全部表。

Revision ID: 0001
Revises:
Create Date: 2026-11-07 18:00:00

说明：首个版本以 ``Base.metadata.create_all`` 建立基线，避免手写 12 张表的 DDL 与
模型漂移；后续结构变更一律使用显式 DDL 的新迁移（见 AGENTS.md 第 7 节）。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建全部业务表。"""
    import campus.models  # noqa: F401
    from campus.db.base import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """删除全部业务表。"""
    import campus.models  # noqa: F401
    from campus.db.base import Base

    Base.metadata.drop_all(bind=op.get_bind())
