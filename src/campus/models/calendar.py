"""日程：会议、活动、考试与个人事项。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import (
    CalendarEventKind,
    CalendarVisibility,
    ParticipantResponse,
)


def _enum(enum_cls: type, length: int = 20) -> SAEnum:
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [item.value for item in cls],
    )


class CalendarEvent(TimestampMixin, Base):
    """日程事件；可见范围决定谁能看到。"""

    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(100), default="")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[CalendarEventKind] = mapped_column(
        _enum(CalendarEventKind), default=CalendarEventKind.OTHER
    )
    visibility: Mapped[CalendarVisibility] = mapped_column(
        _enum(CalendarVisibility), default=CalendarVisibility.PERSONAL
    )
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    class_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    remind_minutes: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(20), default="")
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)


class CalendarEventAttendee(TimestampMixin, Base):
    """日程参与人及回复状态。"""

    __tablename__ = "calendar_event_attendees"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_calendar_event_attendees_event_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("calendar_events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    response: Mapped[ParticipantResponse] = mapped_column(
        _enum(ParticipantResponse), default=ParticipantResponse.PENDING
    )
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
