"""日程契约。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from campus.models.enums import CalendarEventKind, CalendarVisibility, ParticipantResponse


class CalendarEventCreate(BaseModel):
    """新增日程。"""

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=100)
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    kind: CalendarEventKind = CalendarEventKind.OTHER
    visibility: CalendarVisibility = CalendarVisibility.PERSONAL
    department_id: int | None = None
    class_id: int | None = None
    remind_minutes: int = Field(default=0, ge=0, le=10080)
    color: str = Field(default="", max_length=20)
    participant_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_range(self) -> CalendarEventCreate:
        if self.end_at <= self.start_at:
            raise ValueError("end_at 必须晚于 start_at")
        return self


class CalendarEventUpdate(BaseModel):
    """更新日程。"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=100)
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    kind: CalendarEventKind | None = None
    visibility: CalendarVisibility | None = None
    department_id: int | None = None
    class_id: int | None = None
    remind_minutes: int | None = Field(default=None, ge=0, le=10080)
    color: str | None = Field(default=None, max_length=20)
    participant_ids: list[int] | None = None


class CalendarParticipantRead(BaseModel):
    """参与人输出。"""

    user_id: int
    display_name: str
    response: ParticipantResponse
    is_required: bool


class CalendarEventRead(BaseModel):
    """日程输出。"""

    id: int
    title: str
    description: str
    location: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    kind: CalendarEventKind
    visibility: CalendarVisibility
    owner_id: int | None
    owner_name: str | None = None
    department_id: int | None
    class_id: int | None
    remind_minutes: int
    color: str
    is_cancelled: bool
    participants: list[CalendarParticipantRead] = Field(default_factory=list)
    can_edit: bool = False
    created_at: datetime


class CalendarDayRead(BaseModel):
    """某一天的日程摘要。"""

    date: date
    events: list[CalendarEventRead] = Field(default_factory=list)


class CalendarRsvp(BaseModel):
    """参与人回复。"""

    response: ParticipantResponse
