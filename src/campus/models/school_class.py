"""行政班级。"""

from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import ClassStatus


class SchoolClass(TimestampMixin, Base):
    """班级：名称、年级、专业、班主任与固定教室。"""

    __tablename__ = "school_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    grade: Mapped[str] = mapped_column(String(10), default="2024")
    grade_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    major: Mapped[str] = mapped_column(String(50), default="")
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    classroom: Mapped[str] = mapped_column(String(50), default="")
    capacity: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[ClassStatus] = mapped_column(
        SAEnum(
            ClassStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ClassStatus.ACTIVE,
    )
    head_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
