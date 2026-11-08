"""课表契约。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from campus.models.enums import ScheduleStatus


class ScheduleCreate(BaseModel):
    """排课入参。"""

    course_id: int = Field(ge=1)
    semester_id: int | None = None
    class_id: int | None = None
    weekday: int = Field(ge=1, le=7)
    start_period: int = Field(ge=1, le=12)
    end_period: int = Field(ge=1, le=12)
    classroom: str = Field(default="", max_length=50)
    weeks: str = Field(default="1-16", max_length=30)

    @model_validator(mode="after")
    def _check_periods(self) -> ScheduleCreate:
        if self.end_period < self.start_period:
            raise ValueError("end_period 不能小于 start_period")
        return self


class ScheduleRead(BaseModel):
    """课表输出。"""

    id: int
    course_id: int
    course_code: str
    course_name: str
    semester_id: int | None
    class_id: int | None
    weekday: int
    start_period: int
    end_period: int
    classroom: str
    weeks: str
    status: ScheduleStatus


class ScheduleEntryRead(BaseModel):
    """课表网格中的一个课程块。"""

    id: int
    course_id: int
    course_code: str
    course_name: str
    teacher_name: str = ""
    class_name: str = ""
    classroom: str = ""
    weekday: int
    start_period: int
    end_period: int
    weeks: str
    status: ScheduleStatus
    note: str = ""


class ScheduleDayRead(BaseModel):
    """一周中的某一天。"""

    date: date
    weekday: int
    label: str


class PeriodSlotRead(BaseModel):
    """节次时间。"""

    no: int
    start: str
    end: str


class ScheduleGridRead(BaseModel):
    """周课表。"""

    semester_id: int | None
    semester_name: str
    week: int
    week_start: date
    week_end: date
    days: list[ScheduleDayRead]
    periods: list[PeriodSlotRead]
    entries: list[ScheduleEntryRead]


class ScheduleMonthDayRead(BaseModel):
    """月视图中的一天。"""

    date: date
    count: int
    entries: list[ScheduleEntryRead]


class ScheduleMonthRead(BaseModel):
    """月课表。"""

    month: str
    days: list[ScheduleMonthDayRead]


class ScheduleDayViewRead(BaseModel):
    """日课表。"""

    date: date
    weekday: int
    label: str
    entries: list[ScheduleEntryRead]


class ScheduleDetailRead(ScheduleRead):
    """课程详情。"""

    teacher_name: str = ""
    class_name: str = ""
    enrolled: int = 0
    capacity: int = 0
    changes: list[str] = Field(default_factory=list)
