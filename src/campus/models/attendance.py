"""考勤记录：按课程、日期与节次登记。"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import AttendanceStatus


class Attendance(TimestampMixin, Base):
    """同一学生、课程、日期、节次只保留一条考勤。"""

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "course_id",
            "date",
            "period_no",
            name="uq_attendance_student_course_date_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True
    )
    leave_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[dt.date] = mapped_column(Date)
    period_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(
            AttendanceStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=AttendanceStatus.PRESENT,
    )
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)
