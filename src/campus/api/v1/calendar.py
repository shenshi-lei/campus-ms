"""日程路由。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.models.enums import ParticipantResponse
from campus.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventRead,
    CalendarEventUpdate,
    CalendarRsvp,
)
from campus.services.access import Permission
from campus.services.calendar import CalendarService

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events", response_model=list[CalendarEventRead])
async def list_events(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.CALENDAR_READ)),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
) -> list[CalendarEventRead]:
    """按时间范围查看日程。"""
    start_at = start or datetime.combine(date.today(), time.min)
    end_at = end or start_at + timedelta(days=30)
    return await CalendarService(session).list_events(access, start=start_at, end=end_at)


@router.get("/today", response_model=list[CalendarEventRead])
async def today_events(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.CALENDAR_READ)),
) -> list[CalendarEventRead]:
    """今日日程。"""
    return await CalendarService(session).today(access)


@router.post("/events", response_model=CalendarEventRead, status_code=201)
async def create_event(
    payload: CalendarEventCreate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.CALENDAR_MANAGE)),
) -> CalendarEventRead:
    """新建日程。"""
    return await CalendarService(session).create(payload, access)


@router.get("/events/{event_id}", response_model=CalendarEventRead)
async def read_event(
    event_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.CALENDAR_READ)),
) -> CalendarEventRead:
    """日程详情。"""
    return await CalendarService(session).get(event_id, access)


@router.patch("/events/{event_id}", response_model=CalendarEventRead)
async def update_event(
    event_id: int,
    payload: CalendarEventUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.CALENDAR_MANAGE)),
) -> CalendarEventRead:
    """更新日程。"""
    return await CalendarService(session).update(event_id, payload, access)


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.CALENDAR_MANAGE)),
) -> dict[str, str]:
    """删除日程。"""
    await CalendarService(session).delete(event_id, access)
    return {"message": "已删除"}


@router.post("/events/{event_id}/rsvp", response_model=CalendarEventRead)
async def rsvp_event(
    event_id: int,
    payload: CalendarRsvp,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.CALENDAR_READ)),
) -> CalendarEventRead:
    """参与人回复。"""
    return await CalendarService(session).rsvp(
        event_id, ParticipantResponse(payload.response), access
    )
