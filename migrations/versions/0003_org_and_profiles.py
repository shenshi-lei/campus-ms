"""组织与档案细化：院系、学科、学期 + 教师/学生/班级扩展字段。

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07 21:50:00

说明：基线 0001 使用元数据建表，新库已带这些表与字段；本迁移面向已有库补齐，
所有建表/加列都先检查存在性，SQLite 下使用 batch 模式重建表。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _add_missing(table: str, columns: list[sa.Column[Any]]) -> None:
    existing = _columns(table)
    missing = [column for column in columns if column.name not in existing]
    if not missing:
        return
    with op.batch_alter_table(table) as batch:
        for column in missing:
            batch.add_column(column)


def upgrade() -> None:
    """创建组织表并补齐档案字段。"""
    if not _has_table("departments"):
        op.create_table(
            "departments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False, server_default="college"),
            sa.Column(
                "parent_id",
                sa.Integer(),
                sa.ForeignKey("departments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamp_columns(),
            sa.UniqueConstraint("code", name="uq_departments_code"),
            sa.UniqueConstraint("name", name="uq_departments_name"),
        )

    if not _has_table("subjects"):
        op.create_table(
            "subjects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column(
                "department_id",
                sa.Integer(),
                sa.ForeignKey("departments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamp_columns(),
            sa.UniqueConstraint("code", name="uq_subjects_code"),
            sa.UniqueConstraint("name", name="uq_subjects_name"),
        )

    if not _has_table("semesters"):
        op.create_table(
            "semesters",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=20), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("weeks", sa.Integer(), nullable=False, server_default="20"),
            *_timestamp_columns(),
            sa.UniqueConstraint("name", name="uq_semesters_name"),
        )

    _add_missing(
        "teachers",
        [
            sa.Column(
                "subject_id",
                sa.Integer(),
                sa.ForeignKey("subjects.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("position", sa.String(length=30), nullable=False, server_default=""),
            sa.Column("hire_date", sa.Date(), nullable=True),
            sa.Column(
                "employment_status",
                sa.String(length=20),
                nullable=False,
                server_default="active",
            ),
            sa.Column(
                "staff_type", sa.String(length=20), nullable=False, server_default="permanent"
            ),
            sa.Column("education", sa.String(length=20), nullable=False, server_default="other"),
            sa.Column("office", sa.String(length=30), nullable=False, server_default=""),
            sa.Column("workload_limit", sa.Integer(), nullable=False, server_default="16"),
        ],
    )

    _add_missing(
        "students",
        [
            sa.Column("enroll_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("id_card_masked", sa.String(length=32), nullable=True),
            sa.Column("address", sa.String(length=200), nullable=True),
            sa.Column("guardian_name", sa.String(length=50), nullable=True),
            sa.Column("guardian_phone", sa.String(length=20), nullable=True),
            sa.Column("class_role", sa.String(length=20), nullable=False, server_default="none"),
            sa.Column(
                "residence_type", sa.String(length=20), nullable=False, server_default="boarding"
            ),
            sa.Column("seat_no", sa.Integer(), nullable=True),
            sa.Column("seat_row", sa.Integer(), nullable=True),
            sa.Column("seat_col", sa.Integer(), nullable=True),
        ],
    )

    _add_missing(
        "school_classes",
        [
            sa.Column("grade_year", sa.Integer(), nullable=True),
            sa.Column(
                "department_id",
                sa.Integer(),
                sa.ForeignKey("departments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("classroom", sa.String(length=50), nullable=False, server_default=""),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        ],
    )


def downgrade() -> None:
    """删除扩展字段与组织表。"""
    for table, columns in (
        (
            "school_classes",
            ["status", "capacity", "classroom", "department_id", "grade_year"],
        ),
        (
            "students",
            [
                "seat_col",
                "seat_row",
                "seat_no",
                "residence_type",
                "class_role",
                "guardian_phone",
                "guardian_name",
                "address",
                "id_card_masked",
                "status",
                "enroll_date",
            ],
        ),
        (
            "teachers",
            [
                "workload_limit",
                "office",
                "education",
                "staff_type",
                "employment_status",
                "hire_date",
                "position",
                "subject_id",
            ],
        ),
    ):
        existing = _columns(table)
        present = [name for name in columns if name in existing]
        if present:
            with op.batch_alter_table(table) as batch:
                for name in present:
                    batch.drop_column(name)

    for table in ("semesters", "subjects", "departments"):
        if _has_table(table):
            op.drop_table(table)
