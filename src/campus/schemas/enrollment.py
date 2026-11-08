"""选课契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from campus.models.enums import EnrollmentStatus


class EnrollmentCreate(BaseModel):
    """选课入参；学生自助选课时 student_id 留空即可。"""

    course_id: int = Field(ge=1)
    student_id: int | None = Field(default=None, ge=1)


class EnrollmentRead(BaseModel):
    """选课输出（已补齐学生与课程名称）。"""

    id: int
    student_id: int
    student_no: str
    student_name: str
    course_id: int
    course_code: str
    course_name: str
    status: EnrollmentStatus
    created_at: datetime
