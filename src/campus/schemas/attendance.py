"""考勤契约。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from campus.models.enums import AttendanceStatus


class AttendanceInput(BaseModel):
    """单条考勤。"""

    student_id: int = Field(ge=1)
    course_id: int = Field(ge=1)
    date: dt.date
    period_no: int = Field(default=1, ge=1, le=12)
    schedule_id: int | None = None
    status: AttendanceStatus = AttendanceStatus.PRESENT
    remark: str | None = Field(default=None, max_length=200)


class AttendanceBulk(BaseModel):
    """批量考勤登记（同一天、同一课程）。"""

    items: list[AttendanceInput] = Field(min_length=1, max_length=500)


class AttendanceRead(BaseModel):
    """考勤输出（已补齐学生与课程信息）。"""

    id: int
    student_id: int
    student_no: str
    student_name: str
    course_id: int
    course_name: str
    date: dt.date
    period_no: int
    status: AttendanceStatus
    remark: str | None
