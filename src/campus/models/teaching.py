"""教学运行：课程教师、面向班级与调课申请。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import RequestStatus, ScheduleChangeKind


def _enum(enum_cls: type, length: int = 20) -> SAEnum:
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [item.value for item in cls],
    )


class CourseTeacher(TimestampMixin, Base):
    """课程与教师的多对多关系，区分主讲与辅导。"""

    __tablename__ = "course_teachers"
    __table_args__ = (
        UniqueConstraint("course_id", "teacher_id", name="uq_course_teachers_course_teacher"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), default="primary")


class CourseClass(TimestampMixin, Base):
    """课程面向的行政班。"""

    __tablename__ = "course_classes"
    __table_args__ = (
        UniqueConstraint("course_id", "class_id", name="uq_course_classes_course_class"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"))


class ScheduleChange(TimestampMixin, Base):
    """调课/停课/代课申请。"""

    __tablename__ = "schedule_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"))
    change_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[ScheduleChangeKind] = mapped_column(_enum(ScheduleChangeKind))
    new_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_start_period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_end_period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_classroom: Mapped[str] = mapped_column(String(50), default="")
    new_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus), default=RequestStatus.PENDING
    )
    requested_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
