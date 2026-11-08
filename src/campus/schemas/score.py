"""成绩契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScoreInput(BaseModel):
    """单条成绩录入：按学生 + 课程定位选课记录。"""

    student_id: int = Field(ge=1)
    course_id: int = Field(ge=1)
    usual_score: float | None = Field(default=None, ge=0, le=100)
    midterm_score: float | None = Field(default=None, ge=0, le=100)
    exam_score: float | None = Field(default=None, ge=0, le=100)


class ScoreBatch(BaseModel):
    """批量录入。"""

    items: list[ScoreInput] = Field(min_length=1, max_length=200)


class ScoreUpdate(BaseModel):
    """修改单条成绩，未提交的字段保持不变。"""

    usual_score: float | None = Field(default=None, ge=0, le=100)
    midterm_score: float | None = Field(default=None, ge=0, le=100)
    exam_score: float | None = Field(default=None, ge=0, le=100)


class ScoreRead(BaseModel):
    """成绩输出（已补齐学生与课程信息）。"""

    id: int
    enrollment_id: int
    student_id: int
    student_no: str
    student_name: str
    course_id: int
    course_code: str
    course_name: str
    usual_score: float | None
    midterm_score: float | None
    exam_score: float | None
    final_score: float | None
    published: bool
    recorded_at: datetime
