"""教学运行契约：课程教师、面向班级与调课。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from campus.models.enums import RequestStatus, ScheduleChangeKind


class CourseTeacherItem(BaseModel):
    """课程教师项。"""

    teacher_id: int
    role: str = "primary"


class CourseTeacherUpdate(BaseModel):
    """整体替换课程教师。"""

    items: list[CourseTeacherItem] = Field(default_factory=list)


class CourseTeacherRead(BaseModel):
    """课程教师输出。"""

    teacher_id: int
    teacher_no: str
    teacher_name: str
    role: str


class CourseClassItem(BaseModel):
    """面向班级项。"""

    class_id: int


class CourseClassUpdate(BaseModel):
    """整体替换面向班级。"""

    items: list[CourseClassItem] = Field(default_factory=list)


class CourseClassRead(BaseModel):
    """面向班级输出。"""

    class_id: int
    class_name: str


class ScheduleChangeCreate(BaseModel):
    """发起调课/停课/代课。"""

    schedule_id: int
    change_date: date
    kind: ScheduleChangeKind
    new_weekday: int | None = Field(default=None, ge=1, le=7)
    new_start_period: int | None = Field(default=None, ge=1, le=12)
    new_end_period: int | None = Field(default=None, ge=1, le=12)
    new_classroom: str = Field(default="", max_length=50)
    new_teacher_id: int | None = None
    reason: str = Field(default="", max_length=200)


class ScheduleChangeDecision(BaseModel):
    """审批调课申请。"""

    remark: str = Field(default="", max_length=200)


class ScheduleChangeRead(BaseModel):
    """调课申请输出。"""

    id: int
    schedule_id: int
    course_id: int
    course_name: str
    change_date: date
    kind: ScheduleChangeKind
    new_weekday: int | None
    new_start_period: int | None
    new_end_period: int | None
    new_classroom: str
    new_teacher_id: int | None
    reason: str
    status: RequestStatus
    requested_by: int | None
    approved_by: int | None
    decided_at: datetime | None
