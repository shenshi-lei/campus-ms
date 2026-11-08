"""日程仓储。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, select

from campus.models.calendar import CalendarEvent, CalendarEventAttendee
from campus.repositories.base import BaseRepository


class CalendarEventRepository(BaseRepository[CalendarEvent]):
    """日程查询。"""

    model = CalendarEvent

    def between(self, start: datetime, end: datetime) -> Select[CalendarEvent]:
        return (
            select(CalendarEvent)
            .where(
                CalendarEvent.is_cancelled.is_(False),
                CalendarEvent.start_at < end,
                CalendarEvent.end_at > start,
            )
            .order_by(CalendarEvent.start_at, CalendarEvent.id)
        )

    async def attendees(self, event_id: int) -> list[CalendarEventAttendee]:
        rows = await self.session.scalars(
            select(CalendarEventAttendee).where(CalendarEventAttendee.event_id == event_id)
        )
        return list(rows.all())

    async def attendees_for(self, event_ids: list[int]) -> dict[int, list[CalendarEventAttendee]]:
        if not event_ids:
            return {}
        rows = await self.session.scalars(
            select(CalendarEventAttendee).where(CalendarEventAttendee.event_id.in_(event_ids))
        )
        result: dict[int, list[CalendarEventAttendee]] = {}
        for item in rows.all():
            result.setdefault(item.event_id, []).append(item)
        return result
