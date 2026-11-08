"""系统参数契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SettingRead(BaseModel):
    """系统参数输出。"""

    key: str
    value: str
    description: str = ""


class SettingUpdate(BaseModel):
    """更新系统参数。"""

    value: str = Field(default="", max_length=10000)
    description: str | None = Field(default=None, max_length=255)


class PeriodSlot(BaseModel):
    """节次时间。"""

    no: int = Field(ge=1, le=20)
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
