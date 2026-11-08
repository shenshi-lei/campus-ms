"""班级契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from campus.models.enums import ClassStatus
from campus.schemas.common import ORMModel


class SchoolClassCreate(BaseModel):
    """新增班级。"""

    name: str = Field(min_length=1, max_length=50)
    grade: str = Field(default="2024", max_length=10)
    grade_year: int | None = Field(default=None, ge=1900, le=2100)
    major: str = Field(default="", max_length=50)
    department_id: int | None = None
    classroom: str = Field(default="", max_length=50)
    capacity: int = Field(default=50, ge=1, le=200)
    status: ClassStatus = ClassStatus.ACTIVE
    head_teacher_id: int | None = None


class SchoolClassUpdate(BaseModel):
    """部分更新班级。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    grade: str | None = Field(default=None, max_length=10)
    grade_year: int | None = Field(default=None, ge=1900, le=2100)
    major: str | None = Field(default=None, max_length=50)
    department_id: int | None = None
    classroom: str | None = Field(default=None, max_length=50)
    capacity: int | None = Field(default=None, ge=1, le=200)
    status: ClassStatus | None = None
    head_teacher_id: int | None = None


class SchoolClassRead(ORMModel):
    """班级输出。"""

    id: int
    name: str
    grade: str
    grade_year: int | None
    major: str
    department_id: int | None
    classroom: str
    capacity: int
    status: ClassStatus
    head_teacher_id: int | None
