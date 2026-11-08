"""成绩：平时分、期中、考试分与总评。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin, utc_now


class Score(TimestampMixin, Base):
    """一条选课对应一条成绩；总评按课程成绩构成计算。"""

    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), unique=True
    )
    usual_score: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)
    midterm_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2, asdecimal=False), nullable=True
    )
    exam_score: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)
    final_score: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)
    published: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
