"""课表路由：列表、周/日/月视图与课程详情。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Message, Page
from campus.schemas.schedule import (
    ScheduleCreate,
    ScheduleDayViewRead,
    ScheduleDetailRead,
    ScheduleGridRead,
    ScheduleMonthRead,
    ScheduleRead,
)
from campus.services.access import Permission
from campus.services.extras import ScheduleService
from campus.services.timetable import TimetableService

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=Page[ScheduleRead])
async def list_schedules(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_READ)),
    class_id: int | None = Query(default=None, ge=1),
    teacher_id: int | None = Query(default=None, ge=1),
    weekday: int | None = Query(default=None, ge=1, le=7),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> Page[ScheduleRead]:
    """按班级/教师/星期筛选课表（按数据范围过滤）。"""
    return await ScheduleService(session).list_schedules(
        access=access,
        class_id=class_id,
        teacher_id=teacher_id,
        weekday=weekday,
        page=page,
        page_size=page_size,
    )


@router.get("/grid", response_model=ScheduleGridRead)
async def read_grid(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_READ)),
    semester_id: int | None = Query(default=None, ge=1),
    week: int | None = Query(default=None, ge=1, le=30),
    class_id: int | None = Query(default=None, ge=1),
    teacher_id: int | None = Query(default=None, ge=1),
) -> ScheduleGridRead:
    """周课表网格。"""
    return await TimetableService(session).grid(
        access,
        semester_id=semester_id,
        week=week,
        class_id=class_id,
        teacher_id=teacher_id,
    )


@router.get("/month", response_model=ScheduleMonthRead)
async def read_month(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_READ)),
    month: str = Query(default="", max_length=7),
    class_id: int | None = Query(default=None, ge=1),
    teacher_id: int | None = Query(default=None, ge=1),
) -> ScheduleMonthRead:
    """月课表。"""
    target = month or date.today().strftime("%Y-%m")
    return await TimetableService(session).month(
        access, month=target, class_id=class_id, teacher_id=teacher_id
    )


@router.get("/day", response_model=ScheduleDayViewRead)
async def read_day(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_READ)),
    target: date | None = Query(default=None, alias="date"),
    class_id: int | None = Query(default=None, ge=1),
    teacher_id: int | None = Query(default=None, ge=1),
    semester_id: int | None = Query(default=None, ge=1),
) -> ScheduleDayViewRead:
    """日课表。"""
    return await TimetableService(session).day(
        access,
        target=target or date.today(),
        class_id=class_id,
        teacher_id=teacher_id,
        semester_id=semester_id,
    )


@router.get("/{schedule_id}/detail", response_model=ScheduleDetailRead)
async def read_schedule_detail(
    schedule_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_READ)),
) -> ScheduleDetailRead:
    """课程详情。"""
    return await TimetableService(session).detail(schedule_id, access)


@router.post("", response_model=ScheduleRead, status_code=201)
async def create_schedule(
    payload: ScheduleCreate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_MANAGE)),
) -> ScheduleRead:
    """新增排课（教师仅限本人课程）。"""
    return await ScheduleService(session).create_schedule(payload, access)


@router.delete("/{schedule_id}", response_model=Message)
async def delete_schedule(
    schedule_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCHEDULE_MANAGE)),
) -> Message:
    """删除排课。"""
    return await ScheduleService(session).delete_schedule(schedule_id, access)
