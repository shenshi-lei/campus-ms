"""教师档案。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import Education, EmploymentStatus, StaffType


class Teacher(TimestampMixin, Base):
    """教师基本信息；删除采用 is_active 停用而非物理删除。"""

    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(30), default="讲师")
    department: Mapped[str] = mapped_column(String(50), default="")
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[str] = mapped_column(String(30), default="")
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        SAEnum(
            EmploymentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=EmploymentStatus.ACTIVE,
    )
    staff_type: Mapped[StaffType] = mapped_column(
        SAEnum(
            StaffType,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=StaffType.PERMANENT,
    )
    education: Mapped[Education] = mapped_column(
        SAEnum(
            Education,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=Education.OTHER,
    )
    office: Mapped[str] = mapped_column(String(30), default="")
    workload_limit: Mapped[int] = mapped_column(Integer, default=16)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
