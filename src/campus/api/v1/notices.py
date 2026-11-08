"""通知路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Message, Page
from campus.schemas.notice import NoticeCreate, NoticeRead, NoticeUpdate
from campus.services.access import Permission
from campus.services.notice import NoticeService

router = APIRouter(prefix="/notices", tags=["notices"])


@router.get("", response_model=Page[NoticeRead])
async def list_notices(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.NOTICE_READ)),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[NoticeRead]:
    """按角色/班级过滤的通知列表。"""
    return await NoticeService(session).list_notices(access=access, page=page, page_size=page_size)


@router.post("", response_model=NoticeRead, status_code=201)
async def create_notice(
    payload: NoticeCreate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.NOTICE_MANAGE)),
) -> NoticeRead:
    """发布通知。"""
    return await NoticeService(session).create_notice(payload, access)


@router.patch("/{notice_id}", response_model=NoticeRead)
async def update_notice(
    notice_id: int,
    payload: NoticeUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.NOTICE_MANAGE)),
) -> NoticeRead:
    """更新通知。"""
    return await NoticeService(session).update_notice(notice_id, payload, access)


@router.delete("/{notice_id}", response_model=Message)
async def delete_notice(
    notice_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.NOTICE_MANAGE)),
) -> Message:
    """删除通知。"""
    return await NoticeService(session).delete_notice(notice_id, access)
