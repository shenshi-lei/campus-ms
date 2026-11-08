"""审计日志仓储。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select

from campus.models.audit import AuditLog
from campus.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    """审计日志查询。"""

    model = AuditLog

    def filtered(
        self,
        *,
        user_id: int | None = None,
        method: str | None = None,
        path: str | None = None,
    ) -> Select[Any]:
        statement = select(AuditLog)
        if user_id is not None:
            statement = statement.where(AuditLog.user_id == user_id)
        if method:
            statement = statement.where(AuditLog.method == method)
        if path:
            statement = statement.where(AuditLog.path.like(f"%{path}%"))
        return statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())

    async def paginated_rows(
        self,
        *,
        user_id: int | None,
        method: str | None,
        path: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditLog], int]:
        statement = self.filtered(user_id=user_id, method=method, path=path)
        count_statement = select(func.count()).select_from(statement.subquery())
        total = int(await self.session.scalar(count_statement) or 0)
        rows = await self.session.scalars(statement.offset((page - 1) * page_size).limit(page_size))
        return list(rows.all()), total
