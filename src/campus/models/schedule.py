"""课表：课程在星期几、第几节、哪间教室上课。"""

from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import ScheduleStatus


class Schedule(TimestampMixin, Base):
    """同一课程的同一星期与起始节次只允许一条排课。"""

    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint("course_id", "weekday", "start_period", name="uq_schedules_course_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    semester_id: Mapped[int | None] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"), nullable=True
    )
    class_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )
    weekday: Mapped[int] = mapped_column(Integer)
    start_period: Mapped[int] = mapped_column(Integer)
    end_period: Mapped[int] = mapped_column(Integer)
    classroom: Mapped[str] = mapped_column(String(50), default="")
    weeks: Mapped[str] = mapped_column(String(30), default="1-16")
    status: Mapped[ScheduleStatus] = mapped_column(
        SAEnum(
            ScheduleStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ScheduleStatus.ACTIVE,
    )
