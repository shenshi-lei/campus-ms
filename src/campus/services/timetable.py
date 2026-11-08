"""课表服务：周次解析、周/日/月视图与冲突校验。"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from campus.models.course import Course
from campus.models.enrollment import Enrollment
from campus.models.enums import (
    EnrollmentStatus,
    RequestStatus,
    ScheduleChangeKind,
    ScheduleStatus,
)
from campus.models.org import Semester
from campus.models.schedule import Schedule
from campus.models.school_class import SchoolClass
from campus.models.teacher import Teacher
from campus.models.teaching import ScheduleChange
from campus.repositories.org import SemesterRepository
from campus.schemas.schedule import (
    PeriodSlotRead,
    ScheduleCreate,
    ScheduleDayRead,
    ScheduleDayViewRead,
    ScheduleDetailRead,
    ScheduleEntryRead,
    ScheduleGridRead,
    ScheduleMonthDayRead,
    ScheduleMonthRead,
)
from campus.services.access import AccessContext, ScopeKind
from campus.services.setting import SystemSettingService

_WEEK_TOKEN = re.compile(r"^(?P<start>\d{1,2})(?:\s*-\s*(?P<end>\d{1,2}))?\s*(?P<mode>单|双)?周?$")


def parse_weeks(text: str) -> set[int]:
    """解析周次字符串：1-16、1,3,5、1-8,10-16、1-16单/双。"""
    weeks: set[int] = set()
    for raw in re.split(r"[,，;；\s]+", (text or "").strip()):
        if not raw:
            continue
        token = raw.replace("（", "(").replace("）", ")").replace("(", "").replace(")", "")
        match = _WEEK_TOKEN.match(token)
        if match is None:
            continue
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        if end < start:
            start, end = end, start
        mode = match.group("mode") or ""
        for week in range(start, end + 1):
            if mode == "单" and week % 2 == 0:
                continue
            if mode == "双" and week % 2 == 1:
                continue
            weeks.add(week)
    return weeks


def week_number(start: date, target: date) -> int:
    """计算目标日期属于学期第几周。"""
    return max(1, (target - start).days // 7 + 1)


class TimetableService:
    """课表网格与课程详情。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.semesters = SemesterRepository(session)
        self.settings = SystemSettingService(session)

    async def grid(
        self,
        access: AccessContext,
        *,
        semester_id: int | None,
        week: int | None,
        class_id: int | None,
        teacher_id: int | None,
    ) -> ScheduleGridRead:
        semester = await self._semester(semester_id)
        today = date.today()
        current = week or week_number(semester.start_date, today)
        current = max(1, min(current, semester.weeks))
        start = semester.start_date + timedelta(days=(current - 1) * 7)
        days = [
            ScheduleDayRead(
                date=start + timedelta(days=index),
                weekday=index + 1,
                label=["周一", "周二", "周三", "周四", "周五", "周六", "周日"][index],
            )
            for index in range(7)
        ]
        rows = await self._schedule_rows(access, class_id=class_id, teacher_id=teacher_id)
        entries = [
            await self._entry(schedule, course)
            for schedule, course in rows
            if current in parse_weeks(schedule.weeks)
        ]
        periods = [
            PeriodSlotRead(no=item["no"], start=item["start"], end=item["end"])
            for item in await self.settings.period_times()
        ]
        return ScheduleGridRead(
            semester_id=semester.id,
            semester_name=semester.name,
            week=current,
            week_start=start,
            week_end=start + timedelta(days=6),
            days=days,
            periods=periods,
            entries=entries,
        )

    async def month(
        self,
        access: AccessContext,
        *,
        month: str,
        class_id: int | None,
        teacher_id: int | None,
    ) -> ScheduleMonthRead:
        try:
            year, month_no = (int(part) for part in month.split("-", 1))
            first = date(year, month_no, 1)
        except (TypeError, ValueError) as exc:
            raise ConflictError("月份格式应为 YYYY-MM") from exc
        next_first = date(year + 1, 1, 1) if month_no == 12 else date(year, month_no + 1, 1)
        semester = await self._semester(None)
        rows = await self._schedule_rows(access, class_id=class_id, teacher_id=teacher_id)
        entries_by_day: dict[date, list[ScheduleEntryRead]] = {}
        day = first
        while day < next_first:
            number = week_number(semester.start_date, day)
            for schedule, course in rows:
                if number not in parse_weeks(schedule.weeks):
                    continue
                if schedule.weekday != day.isoweekday():
                    continue
                entry = await self._entry(schedule, course, target=day)
                if entry.status.value == "cancelled":
                    continue
                entries_by_day.setdefault(day, []).append(entry)
            day += timedelta(days=1)
        return ScheduleMonthRead(
            month=first.strftime("%Y-%m"),
            days=[
                ScheduleMonthDayRead(
                    date=day,
                    count=len(entries_by_day.get(day, [])),
                    entries=entries_by_day.get(day, []),
                )
                for day in sorted(entries_by_day)
            ],
        )

    async def day(
        self,
        access: AccessContext,
        *,
        target: date,
        class_id: int | None,
        teacher_id: int | None,
        semester_id: int | None = None,
    ) -> ScheduleDayViewRead:
        semester = await self._semester(semester_id)
        number = week_number(semester.start_date, target)
        rows = await self._schedule_rows(access, class_id=class_id, teacher_id=teacher_id)
        entries: list[ScheduleEntryRead] = []
        for schedule, course in rows:
            if schedule.weekday != target.isoweekday():
                continue
            if number not in parse_weeks(schedule.weeks):
                continue
            entry = await self._entry(schedule, course, target=target)
            if entry.status.value == "cancelled":
                continue
            entries.append(entry)
        entries.sort(key=lambda item: (item.start_period, item.end_period))
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return ScheduleDayViewRead(
            date=target,
            weekday=target.isoweekday(),
            label=weekdays[target.isoweekday() - 1],
            entries=entries,
        )

    async def detail(self, schedule_id: int, access: AccessContext) -> ScheduleDetailRead:
        schedule = await self.session.get(Schedule, schedule_id)
        if schedule is None:
            raise NotFoundError("排课不存在")
        course = await self.session.get(Course, schedule.course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        await self._ensure_visible(access, schedule, course)
        teacher = (
            await self.session.get(Teacher, course.teacher_id)
            if course.teacher_id is not None
            else None
        )
        school_class = (
            await self.session.get(SchoolClass, schedule.class_id)
            if schedule.class_id is not None
            else None
        )
        count = int(
            await self.session.scalar(
                select(Enrollment.id).where(
                    Enrollment.course_id == course.id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
            )
            or 0
        )
        changes = await self.session.scalars(
            select(ScheduleChange).where(ScheduleChange.schedule_id == schedule.id)
        )
        return ScheduleDetailRead(
            id=schedule.id,
            course_id=course.id,
            course_code=course.code,
            course_name=course.name,
            semester_id=schedule.semester_id,
            class_id=schedule.class_id,
            weekday=schedule.weekday,
            start_period=schedule.start_period,
            end_period=schedule.end_period,
            classroom=schedule.classroom,
            weeks=schedule.weeks,
            status=schedule.status,
            teacher_name=teacher.name if teacher else "",
            class_name=school_class.name if school_class else "",
            enrolled=count,
            capacity=course.capacity,
            changes=[f"{item.change_date} {item.kind.value} {item.reason}" for item in changes],
        )

    async def create(self, payload: ScheduleCreate, access: AccessContext) -> Schedule:
        """创建排课并做冲突校验。"""
        course = await self.session.get(Course, payload.course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        access.ensure_course_write(course)
        existing = await self.session.scalars(
            select(Schedule).where(
                Schedule.weekday == payload.weekday,
                Schedule.start_period <= payload.end_period,
                Schedule.end_period >= payload.start_period,
            )
        )
        for item in existing.all():
            other = await self.session.get(Course, item.course_id)
            if other is None:
                continue
            same_class = payload.class_id is not None and item.class_id == payload.class_id
            same_room = payload.classroom and item.classroom and payload.classroom == item.classroom
            same_teacher = course.teacher_id is not None and other.teacher_id == course.teacher_id
            if (same_class or same_room or same_teacher) and parse_weeks(item.weeks) & parse_weeks(
                payload.weeks
            ):
                raise ConflictError("该时段与现有排课冲突")
        schedule = Schedule(
            course_id=payload.course_id,
            semester_id=payload.semester_id,
            class_id=payload.class_id,
            weekday=payload.weekday,
            start_period=payload.start_period,
            end_period=payload.end_period,
            classroom=payload.classroom,
            weeks=payload.weeks,
        )
        self.session.add(schedule)
        await self.session.commit()
        await self.session.refresh(schedule)
        return schedule

    async def _schedule_rows(
        self,
        access: AccessContext,
        *,
        class_id: int | None,
        teacher_id: int | None,
    ) -> list[tuple[Schedule, Course]]:
        statement = select(Schedule, Course).join(Course, Schedule.course_id == Course.id)
        if access.scope.kind is ScopeKind.SELF and access.student_id is not None:
            statement = (
                statement.join(Enrollment, Enrollment.course_id == Schedule.course_id)
                .where(
                    Enrollment.student_id == access.student_id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
                .distinct()
            )
        elif access.scope.kind is ScopeKind.CLASSES:
            if class_id is not None and class_id not in access.scope.class_ids:
                raise PermissionDeniedError("只能查看权限范围内的班级课表")
            if teacher_id is not None and teacher_id != access.teacher_id:
                raise PermissionDeniedError("只能查看本人课表")
            statement = statement.where(Schedule.course_id.in_(access.scope.course_ids))
        elif access.scope.kind is not ScopeKind.ALL:
            return []
        if class_id is not None:
            statement = statement.where(Schedule.class_id == class_id)
        if teacher_id is not None:
            statement = statement.where(Course.teacher_id == teacher_id)
        result = await self.session.execute(
            statement.order_by(Schedule.weekday, Schedule.start_period)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def _entry(
        self,
        schedule: Schedule,
        course: Course,
        *,
        target: date | None = None,
    ) -> ScheduleEntryRead:
        teacher = (
            await self.session.get(Teacher, course.teacher_id)
            if course.teacher_id is not None
            else None
        )
        school_class = (
            await self.session.get(SchoolClass, schedule.class_id)
            if schedule.class_id is not None
            else None
        )
        status = schedule.status
        note = ""
        if target is not None:
            change = await self.session.scalar(
                select(ScheduleChange).where(
                    ScheduleChange.schedule_id == schedule.id,
                    ScheduleChange.change_date == target,
                    ScheduleChange.status == RequestStatus.APPROVED,
                )
            )
            if change is not None:
                if change.kind is ScheduleChangeKind.CANCEL:
                    status = ScheduleStatus.CANCELLED
                note = change.reason
        return ScheduleEntryRead(
            id=schedule.id,
            course_id=course.id,
            course_code=course.code,
            course_name=course.name,
            teacher_name=teacher.name if teacher else "",
            class_name=school_class.name if school_class else "",
            classroom=schedule.classroom,
            weekday=schedule.weekday,
            start_period=schedule.start_period,
            end_period=schedule.end_period,
            weeks=schedule.weeks,
            status=status,
            note=note,
        )

    async def _ensure_visible(
        self, access: AccessContext, schedule: Schedule, course: Course
    ) -> None:
        if access.scope.kind is ScopeKind.ALL:
            return
        if access.scope.kind is ScopeKind.SELF:
            if access.student_id is None:
                raise PermissionDeniedError("无权查看该课表")
            enrolled = await self.session.scalar(
                select(Enrollment.id).where(
                    Enrollment.student_id == access.student_id,
                    Enrollment.course_id == course.id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
            )
            if enrolled is None:
                raise PermissionDeniedError("只能查看本人选课")
            return
        if course.id not in access.scope.course_ids and course.teacher_id != access.teacher_id:
            raise PermissionDeniedError("只能查看本人课程")

    async def _semester(self, semester_id: int | None) -> Semester:
        semester = (
            await self.semesters.get(semester_id)
            if semester_id is not None
            else await self.semesters.get_current()
        )
        if semester is None:
            semester = await self.semesters.get_current()
        if semester is None:
            raise NotFoundError("尚未设置当前学期")
        return semester


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """返回某天的起止时间。"""
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)
