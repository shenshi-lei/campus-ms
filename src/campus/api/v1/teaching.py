"""教学运行路由：调课申请与审批。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.models.enums import RequestStatus
from campus.schemas.common import Page
from campus.schemas.teaching import (
    ScheduleChangeCreate,
    ScheduleChangeDecision,
    ScheduleChangeRead,
)
from campus.services.access import Permission
from campus.services.teaching import ScheduleChangeService

router = APIRouter(prefix="/schedule-changes", tags=["schedule-changes"])


@router.get("", response_model=Page[ScheduleChangeRead])
async def list_changes(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_READ)),
    status: RequestStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[ScheduleChangeRead]:
    """调课申请列表（按数据范围过滤）。"""
    return await ScheduleChangeService(session).list_changes(
        access=access, status=status, page=page, page_size=page_size
    )


@router.post("", response_model=ScheduleChangeRead, status_code=201)
async def create_change(
    payload: ScheduleChangeCreate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_CHANGE)),
) -> ScheduleChangeRead:
    """发起调课/停课/代课。"""
    return await ScheduleChangeService(session).create(payload, access)


@router.post("/{change_id}/approve", response_model=ScheduleChangeRead)
async def approve_change(
    change_id: int,
    payload: ScheduleChangeDecision,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_CHANGE)),
) -> ScheduleChangeRead:
    """通过调课申请（管理员）。"""
    return await ScheduleChangeService(session).decide(change_id, payload, access, approved=True)


@router.post("/{change_id}/reject", response_model=ScheduleChangeRead)
async def reject_change(
    change_id: int,
    payload: ScheduleChangeDecision,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_CHANGE)),
) -> ScheduleChangeRead:
    """驳回调课申请（管理员）。"""
    return await ScheduleChangeService(session).decide(change_id, payload, access, approved=False)
