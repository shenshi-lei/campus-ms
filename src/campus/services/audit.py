"""审计服务：查询与手工留痕。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.pagination import PageParams
from campus.models.audit import AuditLog
from campus.repositories.audit import AuditRepository
from campus.schemas.audit import AuditLogRead
from campus.schemas.common import Page
from campus.services.access import AccessContext, Permission


class AuditService:
    """操作审计。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AuditRepository(session)

    async def list_logs(
        self,
        *,
        access: AccessContext,
        user_id: int | None,
        method: str | None,
        path: str | None,
        page: int,
        page_size: int,
    ) -> Page[AuditLogRead]:
        access.ensure(Permission.AUDIT_READ)
        params = PageParams(page=page, page_size=page_size)
        rows, total = await self.repository.paginated_rows(
            user_id=user_id,
            method=method,
            path=path,
            page=params.page,
            page_size=params.page_size,
        )
        return Page[AuditLogRead](
            items=[AuditLogRead.model_validate(item) for item in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def record(
        self,
        access: AccessContext,
        *,
        method: str,
        path: str,
        status_code: int = 200,
        detail: str = "",
    ) -> None:
        """为导出等 GET 操作手工留痕。"""
        self.session.add(
            AuditLog(
                user_id=access.user.id,
                username=access.user.username,
                role=access.user.role.value,
                method=method,
                path=path,
                status_code=status_code,
                detail=detail,
            )
        )
        await self.session.commit()
