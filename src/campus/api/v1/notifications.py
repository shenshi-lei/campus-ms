"""站内消息路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Page
from campus.schemas.notification import NotificationRead, NotificationSummary
from campus.services.access import Permission
from campus.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationRead])
async def list_notifications(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.NOTIFICATION_READ)),
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[NotificationRead]:
    """我的消息。"""
    return await NotificationService(session).list_notifications(
        user_id=access.user.id,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=NotificationSummary)
async def notification_summary(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.NOTIFICATION_READ)),
) -> NotificationSummary:
    """未读/总数摘要。"""
    return await NotificationService(session).summary(access.user.id)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.NOTIFICATION_READ)),
) -> NotificationRead:
    """标记单条已读。"""
    return await NotificationService(session).mark_read(notification_id, access.user.id)


@router.post("/read-all", response_model=NotificationSummary)
async def mark_all_read(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.NOTIFICATION_READ)),
) -> NotificationSummary:
    """全部标记已读。"""
    return await NotificationService(session).mark_all_read(access.user.id)
