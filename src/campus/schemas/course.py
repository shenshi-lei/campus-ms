"""课程契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from campus.models.enums import AssessmentType, CourseType, EnrollmentStatus
from campus.schemas.common import ORMModel


class CourseCreate(BaseModel):
    """新增课程。"""

    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    credits: float = Field(default=3.0, ge=0, le=30)
    hours: int = Field(default=48, ge=1, le=400)
    semester: str = Field(default="2024-2025-1", max_length=20)
    semester_id: int | None = None
    subject_id: int | None = None
    department_id: int | None = None
    course_type: CourseType = CourseType.REQUIRED
    assessment_type: AssessmentType = AssessmentType.EXAM
    grade_scheme: dict[str, float] = Field(
        default_factory=lambda: {"usual": 0.4, "midterm": 0.0, "exam": 0.6}
    )
    textbook: str = Field(default="", max_length=100)
    grade_year: int | None = Field(default=None, ge=1900, le=2100)
    is_active: bool = True
    teacher_id: int | None = None
    capacity: int = Field(default=50, ge=1, le=500)
    description: str | None = Field(default=None, max_length=1000)


class CourseUpdate(BaseModel):
    """部分更新课程。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    credits: float | None = Field(default=None, ge=0, le=30)
    hours: int | None = Field(default=None, ge=1, le=400)
    semester: str | None = Field(default=None, max_length=20)
    semester_id: int | None = None
    subject_id: int | None = None
    department_id: int | None = None
    course_type: CourseType | None = None
    assessment_type: AssessmentType | None = None
    grade_scheme: dict[str, float] | None = None
    textbook: str | None = Field(default=None, max_length=100)
    grade_year: int | None = Field(default=None, ge=1900, le=2100)
    is_active: bool | None = None
    teacher_id: int | None = None
    capacity: int | None = Field(default=None, ge=1, le=500)
    description: str | None = Field(default=None, max_length=1000)


class CourseRead(ORMModel):
    """课程输出。"""

    id: int
    code: str
    name: str
    credits: float
    hours: int
    semester: str
    semester_id: int | None
    subject_id: int | None
    department_id: int | None
    course_type: CourseType
    assessment_type: AssessmentType
    grade_scheme: dict[str, float]
    textbook: str
    grade_year: int | None
    is_active: bool
    teacher_id: int | None
    capacity: int
    description: str | None


class RosterItem(BaseModel):
    """选课名单条目。"""

    enrollment_id: int
    student_id: int
    student_no: str
    student_name: str
    status: EnrollmentStatus
