"""站内消息仓储。"""

from __future__ import annotations

from sqlalchemy import Select, func, select

from campus.models.notification import Notification
from campus.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    """消息查询。"""

    model = Notification

    def filtered(self, user_id: int, *, unread_only: bool = False) -> Select[Notification]:
        statement = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            statement = statement.where(Notification.is_read.is_(False))
        return statement.order_by(Notification.created_at.desc(), Notification.id.desc())

    async def unread_count(self, user_id: int) -> int:
        total = await self.session.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.is_read.is_(False)
            )
        )
        return int(total or 0)
