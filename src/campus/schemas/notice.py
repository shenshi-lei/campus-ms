"""通知公告契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from campus.models.enums import NoticeAudience
from campus.schemas.common import ORMModel


class NoticeCreate(BaseModel):
    """发布通知。"""

    title: str = Field(min_length=1, max_length=100)
    content: str = Field(default="", max_length=5000)
    audience: NoticeAudience = NoticeAudience.ALL
    class_id: int | None = None
    group_id: int | None = None
    is_pinned: bool = False
    expires_at: datetime | None = None


class NoticeUpdate(BaseModel):
    """更新通知。"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, max_length=5000)
    audience: NoticeAudience | None = None
    class_id: int | None = None
    group_id: int | None = None
    is_pinned: bool | None = None
    expires_at: datetime | None = None


class NoticeRead(ORMModel):
    """通知输出。"""

    id: int
    title: str
    content: str
    audience: NoticeAudience
    class_id: int | None
    group_id: int | None
    publisher_id: int | None
    published_at: datetime
    is_pinned: bool
    expires_at: datetime | None
