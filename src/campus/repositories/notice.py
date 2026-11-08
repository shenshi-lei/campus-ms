"""通知公告仓储。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select

from campus.models.enums import NoticeAudience
from campus.models.notice import Notice
from campus.repositories.base import BaseRepository


class NoticeRepository(BaseRepository[Notice]):
    """通知查询。"""

    model = Notice

    def visible(
        self,
        *,
        role_codes: frozenset[str],
        class_ids: frozenset[int],
        group_ids: frozenset[int],
        now: datetime,
    ) -> Select[Any]:
        audience_conditions = [Notice.audience == NoticeAudience.ALL]
        if "teacher" in role_codes:
            audience_conditions.append(Notice.audience == NoticeAudience.TEACHER)
        if "student" in role_codes:
            audience_conditions.append(Notice.audience == NoticeAudience.STUDENT)
        if class_ids:
            audience_conditions.append(
                (Notice.audience == NoticeAudience.CLASS) & (Notice.class_id.in_(class_ids))
            )
        if group_ids:
            audience_conditions.append(
                (Notice.audience == NoticeAudience.GROUP) & (Notice.group_id.in_(group_ids))
            )
        conditions = [
            or_(*audience_conditions),
            or_(Notice.expires_at.is_(None), Notice.expires_at > now),
        ]
        return (
            select(Notice)
            .where(*conditions)
            .order_by(Notice.is_pinned.desc(), Notice.published_at.desc(), Notice.id.desc())
        )

    async def paginated_visible(
        self,
        *,
        role_codes: frozenset[str],
        class_ids: frozenset[int],
        group_ids: frozenset[int],
        now: datetime,
        page: int,
        page_size: int,
    ) -> tuple[list[Notice], int]:
        statement = self.visible(
            role_codes=role_codes,
            class_ids=class_ids,
            group_ids=group_ids,
            now=now,
        )
        count_statement = select(func.count()).select_from(statement.subquery())
        total = int(await self.session.scalar(count_statement) or 0)
        rows = await self.session.scalars(statement.offset((page - 1) * page_size).limit(page_size))
        return list(rows.all()), total
