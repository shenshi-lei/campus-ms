"""审计日志路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.audit import AuditLogRead
from campus.schemas.common import Page
from campus.services.access import Permission
from campus.services.audit import AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogRead])
async def list_audit_logs(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.AUDIT_READ)),
    user_id: int | None = Query(default=None, ge=1),
    method: str | None = Query(default=None, max_length=10),
    path: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[AuditLogRead]:
    """操作审计日志（管理员）。"""
    return await AuditService(session).list_logs(
        access=access,
        user_id=user_id,
        method=method,
        path=path,
        page=page,
        page_size=page_size,
    )
