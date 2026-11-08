"""课程。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import AssessmentType, CourseType


class Course(TimestampMixin, Base):
    """课程：代码唯一，容量用于选课校验。"""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    credits: Mapped[float] = mapped_column(Numeric(3, 1, asdecimal=False), default=3.0)
    hours: Mapped[int] = mapped_column(Integer, default=48)
    semester: Mapped[str] = mapped_column(String(20), index=True, default="2024-2025-1")
    semester_id: Mapped[int | None] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"), nullable=True
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    course_type: Mapped[CourseType] = mapped_column(
        SAEnum(
            CourseType,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=CourseType.REQUIRED,
    )
    assessment_type: Mapped[AssessmentType] = mapped_column(
        SAEnum(
            AssessmentType,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=AssessmentType.EXAM,
    )
    grade_scheme: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=lambda: {"usual": 0.4, "midterm": 0.0, "exam": 0.6}
    )
    textbook: Mapped[str] = mapped_column(String(100), default="")
    grade_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    capacity: Mapped[int] = mapped_column(Integer, default=50)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
