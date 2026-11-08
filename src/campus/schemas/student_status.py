"""学籍异动契约。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from campus.models.enums import StudentStatus


class StudentStatusChange(BaseModel):
    """变更学籍状态。"""

    status: StudentStatus
    effective_date: date
    reason: str = Field(default="", max_length=200)


class StudentStatusHistoryRead(BaseModel):
    """学籍异动记录。"""

    id: int
    from_status: StudentStatus | None
    to_status: StudentStatus
    effective_date: date
    reason: str
