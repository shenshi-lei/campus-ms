"""座位表契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SeatItem(BaseModel):
    """一个座位格。"""

    seat_no: int
    seat_row: int
    seat_col: int
    student_id: int | None = None
    student_no: str | None = None
    student_name: str | None = None
    class_role: str = "none"


class SeatMap(BaseModel):
    """班级座位表。"""

    class_id: int
    class_name: str
    rows: int
    cols: int
    seats: list[SeatItem] = Field(default_factory=list)


class SeatAssignment(BaseModel):
    """调整单个座位。"""

    student_id: int
    seat_no: int = Field(ge=1, le=200)
    seat_row: int = Field(ge=1, le=20)
    seat_col: int = Field(ge=1, le=20)


class SeatUpdate(BaseModel):
    """批量调整座位。"""

    items: list[SeatAssignment] = Field(default_factory=list)
