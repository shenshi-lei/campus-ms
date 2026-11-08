"""站内消息服务。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import NotFoundError
from campus.core.pagination import PageParams
from campus.models.enums import NotificationKind
from campus.models.notification import Notification
from campus.repositories.notification import NotificationRepository
from campus.schemas.common import Page
from campus.schemas.notification import NotificationRead, NotificationSummary


class NotificationService:
    """消息写入与读取。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = NotificationRepository(session)

    def add(
        self,
        user_ids: set[int],
        *,
        kind: NotificationKind,
        title: str,
        body: str = "",
        link: str = "",
    ) -> None:
        """把消息加入当前事务；由调用方统一提交。"""
        for user_id in sorted(user_ids):
            self.session.add(
                Notification(
                    user_id=user_id,
                    kind=kind,
                    title=title,
                    body=body,
                    link=link,
                )
            )

    async def list_notifications(
        self, *, user_id: int, unread_only: bool, page: int, page_size: int
    ) -> Page[NotificationRead]:
        params = PageParams(page=page, page_size=page_size)
        statement = self.repository.filtered(user_id, unread_only=unread_only)
        rows, total = await self.repository.paginate(statement, params.page, params.page_size)
        return Page[NotificationRead](
            items=[self._to_read(item) for item in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def summary(self, user_id: int) -> NotificationSummary:
        unread = await self.repository.unread_count(user_id)
        total = await self.repository.count(self.repository.filtered(user_id))
        return NotificationSummary(unread=unread, total=total)

    async def mark_read(self, notification_id: int, user_id: int) -> NotificationRead:
        row = await self.repository.get(notification_id)
        if row is None or row.user_id != user_id:
            raise NotFoundError("消息不存在")
        row.is_read = True
        row.read_at = datetime.now(UTC)
        await self.session.commit()
        return self._to_read(row)

    async def mark_all_read(self, user_id: int) -> NotificationSummary:
        rows, _ = await self.repository.paginate(
            self.repository.filtered(user_id, unread_only=True), 1, 10000
        )
        now = datetime.now(UTC)
        for row in rows:
            row.is_read = True
            row.read_at = now
        await self.session.commit()
        return await self.summary(user_id)

    @staticmethod
    def _to_read(row: Notification) -> NotificationRead:
        created_at = (
            row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
        )
        read_at = (
            row.read_at.replace(tzinfo=UTC)
            if row.read_at is not None and row.read_at.tzinfo is None
            else row.read_at
        )
        return NotificationRead(
            id=row.id,
            kind=row.kind,
            title=row.title,
            body=row.body,
            link=row.link,
            is_read=row.is_read,
            read_at=read_at,
            created_at=created_at,
        )
