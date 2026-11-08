"""报表契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkloadItem(BaseModel):
    """教师工作量。"""

    teacher_id: int
    teacher_no: str
    teacher_name: str
    department: str
    subject_name: str | None
    position: str
    course_count: int
    weekly_periods: int
    hours: int
    student_count: int
    class_count: int


class SubjectReportItem(BaseModel):
    """学科成绩分析。"""

    subject_id: int | None
    subject_name: str
    course_count: int
    student_count: int
    average_score: float | None
    pass_rate: float


class ClassReportItem(BaseModel):
    """班级对比。"""

    class_id: int
    class_name: str
    student_count: int
    average_score: float | None
    attendance_rate: float
    collection_rate: float


class ReportList(BaseModel):
    """通用报表列表。"""

    items: list[WorkloadItem | SubjectReportItem | ClassReportItem] = Field(default_factory=list)
