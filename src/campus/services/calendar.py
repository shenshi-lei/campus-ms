"""日程服务：可见范围、参与人与回复。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import NotFoundError, PermissionDeniedError
from campus.models.calendar import CalendarEvent, CalendarEventAttendee
from campus.models.enums import (
    CalendarVisibility,
    NotificationKind,
    ParticipantResponse,
)
from campus.models.school_class import SchoolClass
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.user import User
from campus.repositories.calendar import CalendarEventRepository
from campus.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventRead,
    CalendarEventUpdate,
    CalendarParticipantRead,
)
from campus.services.access import AccessContext, Permission, ScopeKind
from campus.services.notification import NotificationService


def _local_naive(value: datetime) -> datetime:
    """把带时区时间转换为本地 naive，统一与 SQLite 存储比较。"""
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


class CalendarService:
    """日程 CRUD 与今日视图。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CalendarEventRepository(session)
        self.notifications = NotificationService(session)

    async def list_events(
        self, access: AccessContext, *, start: datetime, end: datetime
    ) -> list[CalendarEventRead]:
        access.ensure(Permission.CALENDAR_READ)
        start_at = _local_naive(start)
        end_at = _local_naive(end)
        rows = list((await self.session.scalars(self.repository.between(start_at, end_at))).all())
        visible = [row for row in rows if await self._visible(access, row)]
        return await self._read_many(visible, access)

    async def today(self, access: AccessContext) -> list[CalendarEventRead]:
        day = date.today()
        start = datetime.combine(day, time.min)
        end = start + timedelta(days=1)
        access.ensure(Permission.CALENDAR_READ)
        rows = list((await self.session.scalars(self.repository.between(start, end))).all())
        visible = [row for row in rows if await self._visible(access, row)]
        return await self._read_many(visible, access)

    async def get(self, event_id: int, access: AccessContext) -> CalendarEventRead:
        event = await self._require(event_id)
        if not await self._visible(access, event):
            raise PermissionDeniedError("无权查看该日程")
        return (await self._read_many([event], access))[0]

    async def create(
        self, payload: CalendarEventCreate, access: AccessContext
    ) -> CalendarEventRead:
        access.ensure(Permission.CALENDAR_MANAGE)
        if payload.visibility is CalendarVisibility.SCHOOL and not access.can(
            Permission.CALENDAR_MANAGE_ALL
        ):
            raise PermissionDeniedError("只有管理员可以创建全校日程")
        if payload.visibility is CalendarVisibility.CLASS and access.scope.kind is ScopeKind.SELF:
            raise PermissionDeniedError("学生不能创建班级日程")
        event = CalendarEvent(
            title=payload.title,
            description=payload.description,
            location=payload.location,
            start_at=_local_naive(payload.start_at),
            end_at=_local_naive(payload.end_at),
            all_day=payload.all_day,
            kind=payload.kind,
            visibility=payload.visibility,
            owner_id=access.user.id,
            department_id=payload.department_id,
            class_id=payload.class_id,
            created_by=access.user.id,
            remind_minutes=payload.remind_minutes,
            color=payload.color,
        )
        self.session.add(event)
        await self.session.flush()
        await self._replace_participants(event, payload.participant_ids)
        self.notifications.add(
            {user_id for user_id in payload.participant_ids if user_id != access.user.id},
            kind=NotificationKind.CALENDAR,
            title=f"日程邀请：{event.title}",
            body=f"{event.start_at:%Y-%m-%d %H:%M} · {event.location or '地点待定'}",
            link=f"/calendar?event={event.id}",
        )
        await self.session.commit()
        return await self.get(event.id, access)

    async def update(
        self, event_id: int, payload: CalendarEventUpdate, access: AccessContext
    ) -> CalendarEventRead:
        event = await self._require(event_id)
        if not self._can_edit(access, event):
            raise PermissionDeniedError("无权修改该日程")
        data = payload.model_dump(exclude_unset=True, exclude={"participant_ids"})
        for key, value in data.items():
            if key in {"start_at", "end_at"} and isinstance(value, datetime):
                value = _local_naive(value)
            setattr(event, key, value)
        if event.end_at <= event.start_at:
            raise PermissionDeniedError("结束时间必须晚于开始时间")
        if payload.participant_ids is not None:
            await self._replace_participants(event, payload.participant_ids)
        await self.session.commit()
        return await self.get(event_id, access)

    async def delete(self, event_id: int, access: AccessContext) -> None:
        event = await self._require(event_id)
        if not self._can_edit(access, event):
            raise PermissionDeniedError("无权删除该日程")
        await self.session.delete(event)
        await self.session.commit()

    async def rsvp(
        self, event_id: int, response: ParticipantResponse, access: AccessContext
    ) -> CalendarEventRead:
        event = await self._require(event_id)
        attendee = await self.session.scalar(
            select(CalendarEventAttendee).where(
                CalendarEventAttendee.event_id == event_id,
                CalendarEventAttendee.user_id == access.user.id,
            )
        )
        if attendee is None:
            if event.owner_id == access.user.id:
                attendee = CalendarEventAttendee(
                    event_id=event_id,
                    user_id=access.user.id,
                    response=response,
                )
                self.session.add(attendee)
            else:
                raise PermissionDeniedError("你不在该日程的参与人中")
        else:
            attendee.response = response
        await self.session.commit()
        return await self.get(event_id, access)

    async def _replace_participants(self, event: CalendarEvent, user_ids: list[int]) -> None:
        existing = await self.repository.attendees(event.id)
        for item in existing:
            await self.session.delete(item)
        await self.session.flush()
        for user_id in sorted(set(user_ids)):
            user = await self.session.get(User, user_id)
            if user is None:
                continue
            self.session.add(CalendarEventAttendee(event_id=event.id, user_id=user_id))
        await self.session.flush()

    async def _read_many(
        self, rows: list[CalendarEvent], access: AccessContext
    ) -> list[CalendarEventRead]:
        attendees = await self.repository.attendees_for([item.id for item in rows])
        names = await self._user_names(
            {item.user_id for items in attendees.values() for item in items}
            | {item.owner_id for item in rows if item.owner_id is not None}
        )
        return [
            CalendarEventRead(
                id=item.id,
                title=item.title,
                description=item.description,
                location=item.location,
                start_at=item.start_at,
                end_at=item.end_at,
                all_day=item.all_day,
                kind=item.kind,
                visibility=item.visibility,
                owner_id=item.owner_id,
                owner_name=names.get(item.owner_id) if item.owner_id else None,
                department_id=item.department_id,
                class_id=item.class_id,
                remind_minutes=item.remind_minutes,
                color=item.color,
                is_cancelled=item.is_cancelled,
                participants=[
                    CalendarParticipantRead(
                        user_id=attendee.user_id,
                        display_name=names.get(attendee.user_id, f"用户{attendee.user_id}"),
                        response=attendee.response,
                        is_required=attendee.is_required,
                    )
                    for attendee in attendees.get(item.id, [])
                ],
                can_edit=self._can_edit(access, item),
                created_at=item.created_at,
            )
            for item in rows
        ]

    async def _visible(self, access: AccessContext, event: CalendarEvent) -> bool:
        if access.can(Permission.CALENDAR_MANAGE_ALL):
            return True
        if event.owner_id == access.user.id:
            return True
        attendee_ids = {item.user_id for item in await self.repository.attendees(event.id)}
        if access.user.id in attendee_ids:
            return True
        if event.visibility is CalendarVisibility.SCHOOL:
            return True
        if event.visibility is CalendarVisibility.PERSONAL:
            return False
        if event.visibility is CalendarVisibility.CLASS:
            return event.class_id in await self._class_ids(access)
        if event.visibility is CalendarVisibility.DEPARTMENT:
            return event.department_id == await self._department_id(access)
        return False

    def _can_edit(self, access: AccessContext, event: CalendarEvent) -> bool:
        return access.can(Permission.CALENDAR_MANAGE_ALL) or event.owner_id == access.user.id

    async def _class_ids(self, access: AccessContext) -> set[int]:
        if access.scope.kind is ScopeKind.ALL:
            rows = await self.session.scalars(select(SchoolClass.id))
            return {int(item) for item in rows.all()}
        if access.scope.kind is ScopeKind.SELF and access.student_id is not None:
            student = await self.session.get(Student, access.student_id)
            return {student.class_id} if student and student.class_id else set()
        return set(access.scope.class_ids)

    async def _department_id(self, access: AccessContext) -> int | None:
        if access.teacher_id is not None:
            teacher = await self.session.get(Teacher, access.teacher_id)
            return teacher.department_id if teacher else None
        if access.student_id is not None:
            student = await self.session.get(Student, access.student_id)
            if student and student.class_id:
                school_class = await self.session.get(SchoolClass, student.class_id)
                return school_class.department_id if school_class else None
        return access.scope.department_id

    async def _user_names(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        names: dict[int, str] = {}
        users = await self.session.scalars(select(User).where(User.id.in_(user_ids)))
        for user in users.all():
            names[user.id] = user.username
        students = await self.session.execute(
            select(Student.user_id, Student.name).where(Student.user_id.in_(user_ids))
        )
        for user_id, name in students.all():
            if user_id is not None:
                names[int(user_id)] = str(name)
        teachers = await self.session.execute(
            select(Teacher.user_id, Teacher.name).where(Teacher.user_id.in_(user_ids))
        )
        for user_id, name in teachers.all():
            if user_id is not None:
                names[int(user_id)] = str(name)
        return names

    async def _require(self, event_id: int) -> CalendarEvent:
        event = await self.repository.get(event_id)
        if event is None:
            raise NotFoundError("日程不存在")
        return event
