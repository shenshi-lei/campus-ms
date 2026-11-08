"""学生档案。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import ClassRole, Gender, ResidenceType, StudentStatus


class Student(TimestampMixin, Base):
    """学生基本信息；删除采用 is_active 停用而非物理删除。"""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    gender: Mapped[Gender] = mapped_column(
        SAEnum(
            Gender,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=Gender.UNKNOWN,
    )
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    enroll_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[StudentStatus] = mapped_column(
        SAEnum(
            StudentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=StudentStatus.ACTIVE,
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    id_card_masked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    class_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )
    class_role: Mapped[ClassRole] = mapped_column(
        SAEnum(
            ClassRole,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ClassRole.NONE,
    )
    residence_type: Mapped[ResidenceType] = mapped_column(
        SAEnum(
            ResidenceType,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ResidenceType.BOARDING,
    )
    seat_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seat_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seat_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
