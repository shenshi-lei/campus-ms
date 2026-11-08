"""组织模型：院系、学科与学期。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import DepartmentKind, SemesterStatus


def _enum(enum_cls: type, length: int = 20) -> SAEnum:
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [item.value for item in cls],
    )


class Department(TimestampMixin, Base):
    """院系或处室；单层结构，parent_id 预留。"""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    kind: Mapped[DepartmentKind] = mapped_column(
        _enum(DepartmentKind), default=DepartmentKind.COLLEGE
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subject(TimestampMixin, Base):
    """学科：语文/数学/计算机等，教师与课程都挂学科。"""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Semester(TimestampMixin, Base):
    """学期：同一时间只允许一个 is_current。"""

    __tablename__ = "semesters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[SemesterStatus] = mapped_column(
        _enum(SemesterStatus), default=SemesterStatus.PLANNED
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    weeks: Mapped[int] = mapped_column(Integer, default=20)
