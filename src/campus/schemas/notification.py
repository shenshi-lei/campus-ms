"""站内消息契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from campus.models.enums import NotificationKind


class NotificationRead(BaseModel):
    """消息输出。"""

    id: int
    kind: NotificationKind
    title: str
    body: str
    link: str
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationSummary(BaseModel):
    """未读数摘要。"""

    unread: int
    total: int
