"""教师契约。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from campus.models.enums import Education, EmploymentStatus, StaffType
from campus.schemas.common import ORMModel


class TeacherCreate(BaseModel):
    """新增教师。"""

    teacher_no: str = Field(min_length=3, max_length=20)
    name: str = Field(min_length=1, max_length=50)
    title: str = Field(default="讲师", max_length=30)
    department: str = Field(default="", max_length=50)
    subject_id: int | None = None
    position: str = Field(default="", max_length=30)
    hire_date: date | None = None
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE
    staff_type: StaffType = StaffType.PERMANENT
    education: Education = Education.OTHER
    office: str = Field(default="", max_length=30)
    workload_limit: int = Field(default=16, ge=0, le=60)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    user_id: int | None = None


class TeacherUpdate(BaseModel):
    """部分更新教师。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, max_length=30)
    department: str | None = Field(default=None, max_length=50)
    subject_id: int | None = None
    position: str | None = Field(default=None, max_length=30)
    hire_date: date | None = None
    employment_status: EmploymentStatus | None = None
    staff_type: StaffType | None = None
    education: Education | None = None
    office: str | None = Field(default=None, max_length=30)
    workload_limit: int | None = Field(default=None, ge=0, le=60)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class TeacherRead(ORMModel):
    """教师输出。"""

    id: int
    teacher_no: str
    name: str
    title: str
    department: str
    subject_id: int | None
    position: str
    hire_date: date | None
    employment_status: EmploymentStatus
    staff_type: StaffType
    education: Education
    office: str
    workload_limit: int
    phone: str | None
    email: str | None
    user_id: int | None
    is_active: bool
