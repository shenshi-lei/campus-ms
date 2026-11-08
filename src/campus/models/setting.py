"""系统参数：节次时间、提醒策略等键值配置。"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin


class SystemSetting(TimestampMixin, Base):
    """键值配置；value 存 JSON 字符串。"""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(String(255), default="")
