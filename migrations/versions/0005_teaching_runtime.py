"""教学运行：课程多教师/面向班级、调课、成绩构成与考勤节次。

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07 22:30:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
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
    """创建教学运行表并扩展课程/课表/成绩/考勤。"""
    if not _has_table("course_teachers"):
        op.create_table(
            "course_teachers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "course_id",
                sa.Integer(),
                sa.ForeignKey("courses.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "teacher_id",
                sa.Integer(),
                sa.ForeignKey("teachers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="primary"),
            *_timestamp_columns(),
            sa.UniqueConstraint(
                "course_id", "teacher_id", name="uq_course_teachers_course_teacher"
            ),
        )

    if not _has_table("course_classes"):
        op.create_table(
            "course_classes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "course_id",
                sa.Integer(),
                sa.ForeignKey("courses.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "class_id",
                sa.Integer(),
                sa.ForeignKey("school_classes.id", ondelete="CASCADE"),
                nullable=False,
            ),
            *_timestamp_columns(),
            sa.UniqueConstraint("course_id", "class_id", name="uq_course_classes_course_class"),
        )

    if not _has_table("schedule_changes"):
        op.create_table(
            "schedule_changes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "schedule_id",
                sa.Integer(),
                sa.ForeignKey("schedules.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("change_date", sa.Date(), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("new_weekday", sa.Integer(), nullable=True),
            sa.Column("new_start_period", sa.Integer(), nullable=True),
            sa.Column("new_end_period", sa.Integer(), nullable=True),
            sa.Column("new_classroom", sa.String(length=50), nullable=False, server_default=""),
            sa.Column(
                "new_teacher_id",
                sa.Integer(),
                sa.ForeignKey("teachers.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("reason", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column(
                "requested_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "approved_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamp_columns(),
        )

    _add_missing(
        "courses",
        [
            sa.Column("semester_id", sa.Integer(), nullable=True),
            sa.Column("subject_id", sa.Integer(), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True),
            sa.Column(
                "course_type", sa.String(length=20), nullable=False, server_default="required"
            ),
            sa.Column(
                "assessment_type", sa.String(length=20), nullable=False, server_default="exam"
            ),
            sa.Column("grade_scheme", sa.JSON(), nullable=True),
            sa.Column("textbook", sa.String(length=100), nullable=False, server_default=""),
            sa.Column("grade_year", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        ],
    )

    _add_missing(
        "schedules",
        [
            sa.Column("semester_id", sa.Integer(), nullable=True),
            sa.Column("class_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        ],
    )

    _add_missing(
        "scores",
        [
            sa.Column("midterm_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        ],
    )

    _add_missing(
        "attendance",
        [
            sa.Column("period_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("schedule_id", sa.Integer(), nullable=True),
        ],
    )

    inspector = sa.inspect(op.get_bind())
    unique_names = {item["name"] for item in inspector.get_unique_constraints("attendance")}
    if "uq_attendance_student_course_date_period" not in unique_names:
        with op.batch_alter_table("attendance") as batch:
            if "uq_attendance_student_course_date" in unique_names:
                batch.drop_constraint("uq_attendance_student_course_date", type_="unique")
            batch.create_unique_constraint(
                "uq_attendance_student_course_date_period",
                ["student_id", "course_id", "date", "period_no"],
            )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE courses SET semester_id = ("
            "SELECT id FROM semesters WHERE semesters.name = courses.semester"
            ") WHERE semester_id IS NULL"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE schedules SET semester_id = ("
            "SELECT semester_id FROM courses WHERE courses.id = schedules.course_id"
            ") WHERE semester_id IS NULL"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO course_teachers (course_id, teacher_id, role, created_at, updated_at) "
            "SELECT c.id, c.teacher_id, 'primary', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
            "FROM courses c WHERE c.teacher_id IS NOT NULL AND NOT EXISTS ("
            "SELECT 1 FROM course_teachers ct "
            "WHERE ct.course_id = c.id AND ct.teacher_id = c.teacher_id)"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO course_classes (course_id, class_id, created_at, updated_at) "
            "SELECT DISTINCT e.course_id, s.class_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
            "FROM enrollments e JOIN students s ON s.id = e.student_id "
            "WHERE s.class_id IS NOT NULL AND NOT EXISTS ("
            "SELECT 1 FROM course_classes cc "
            "WHERE cc.course_id = e.course_id AND cc.class_id = s.class_id)"
        )
    )


def downgrade() -> None:
    """回滚教学运行扩展。"""
    inspector = sa.inspect(op.get_bind())
    unique_names = {item["name"] for item in inspector.get_unique_constraints("attendance")}
    if "uq_attendance_student_course_date_period" in unique_names:
        with op.batch_alter_table("attendance") as batch:
            batch.drop_constraint("uq_attendance_student_course_date_period", type_="unique")
            batch.create_unique_constraint(
                "uq_attendance_student_course_date",
                ["student_id", "course_id", "date"],
            )

    for table, columns in (
        ("attendance", ["schedule_id", "period_no"]),
        ("scores", ["published_at", "published", "midterm_score"]),
        ("schedules", ["status", "class_id", "semester_id"]),
        (
            "courses",
            [
                "is_active",
                "grade_year",
                "textbook",
                "grade_scheme",
                "assessment_type",
                "course_type",
                "department_id",
                "subject_id",
                "semester_id",
            ],
        ),
    ):
        existing = _columns(table)
        present = [name for name in columns if name in existing]
        if present:
            with op.batch_alter_table(table) as batch:
                for name in present:
                    batch.drop_column(name)

    for table in ("schedule_changes", "course_classes", "course_teachers"):
        if _has_table(table):
            op.drop_table(table)
