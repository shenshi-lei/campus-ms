"""缴费契约。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from campus.models.enums import FeeStatus


class FeeCreate(BaseModel):
    """新增费用项。"""

    student_id: int = Field(ge=1)
    item: str = Field(min_length=1, max_length=50)
    amount: float = Field(gt=0, le=100000)
    due_date: date


class FeeRead(BaseModel):
    """费用输出。"""

    id: int
    student_id: int
    student_no: str
    student_name: str
    item: str
    amount: float
    due_date: date
    status: FeeStatus
    paid_at: datetime | None
