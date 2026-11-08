"""学生契约。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from campus.models.enums import ClassRole, Gender, ResidenceType, StudentStatus
from campus.schemas.common import ORMModel


class StudentCreate(BaseModel):
    """新增学生。"""

    student_no: str = Field(min_length=4, max_length=20)
    name: str = Field(min_length=1, max_length=50)
    gender: Gender = Gender.UNKNOWN
    birth_date: date | None = None
    enroll_date: date | None = None
    status: StudentStatus = StudentStatus.ACTIVE
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    id_card_masked: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=200)
    guardian_name: str | None = Field(default=None, max_length=50)
    guardian_phone: str | None = Field(default=None, max_length=20)
    class_id: int | None = None
    class_role: ClassRole = ClassRole.NONE
    residence_type: ResidenceType = ResidenceType.BOARDING
    seat_no: int | None = Field(default=None, ge=1, le=200)
    seat_row: int | None = Field(default=None, ge=1, le=20)
    seat_col: int | None = Field(default=None, ge=1, le=20)
    user_id: int | None = None


class StudentUpdate(BaseModel):
    """部分更新，仅提交的字段生效。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    gender: Gender | None = None
    birth_date: date | None = None
    enroll_date: date | None = None
    status: StudentStatus | None = None
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    id_card_masked: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=200)
    guardian_name: str | None = Field(default=None, max_length=50)
    guardian_phone: str | None = Field(default=None, max_length=20)
    class_id: int | None = None
    class_role: ClassRole | None = None
    residence_type: ResidenceType | None = None
    seat_no: int | None = Field(default=None, ge=1, le=200)
    seat_row: int | None = Field(default=None, ge=1, le=20)
    seat_col: int | None = Field(default=None, ge=1, le=20)
    is_active: bool | None = None


class StudentRead(ORMModel):
    """学生输出。"""

    id: int
    student_no: str
    name: str
    gender: Gender
    birth_date: date | None
    enroll_date: date | None
    status: StudentStatus
    phone: str | None
    email: str | None
    id_card_masked: str | None
    address: str | None
    guardian_name: str | None
    guardian_phone: str | None
    class_id: int | None
    class_role: ClassRole
    residence_type: ResidenceType
    seat_no: int | None
    seat_row: int | None
    seat_col: int | None
    user_id: int | None
    is_active: bool


class TranscriptItem(BaseModel):
    """成绩单条目。"""

    course_code: str
    course_name: str
    credits: float
    semester: str
    final_score: float | None
