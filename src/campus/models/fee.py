"""缴费记录。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import FeeStatus


class Fee(TimestampMixin, Base):
    """学生费用项：金额、截止日期与缴费状态。"""

    __tablename__ = "fees"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    item: Mapped[str] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[FeeStatus] = mapped_column(
        SAEnum(
            FeeStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=FeeStatus.UNPAID,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
