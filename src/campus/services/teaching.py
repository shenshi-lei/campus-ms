"""教学运行服务：课程教师/面向班级配置与调课审批。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from campus.core.pagination import PageParams
from campus.db.base import utc_now
from campus.models.course import Course
from campus.models.enums import RequestStatus, ScheduleStatus
from campus.models.schedule import Schedule
from campus.models.teacher import Teacher
from campus.models.teaching import ScheduleChange
from campus.repositories.extras import ScheduleRepository
from campus.repositories.people import SchoolClassRepository
from campus.repositories.teaching import (
    CourseClassRepository,
    CourseTeacherRepository,
    ScheduleChangeRepository,
)
from campus.schemas.common import Page
from campus.schemas.teaching import (
    CourseClassRead,
    CourseClassUpdate,
    CourseTeacherRead,
    CourseTeacherUpdate,
    ScheduleChangeCreate,
    ScheduleChangeDecision,
    ScheduleChangeRead,
)
from campus.services.access import AccessContext, Permission, ScopeKind


class CourseRosterService:
    """课程教师与面向班级配置。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teachers = CourseTeacherRepository(session)
        self.classes = CourseClassRepository(session)

    async def list_teachers(self, course_id: int, access: AccessContext) -> list[CourseTeacherRead]:
        await self._ensure_course_read(course_id, access)
        return [
            CourseTeacherRead(
                teacher_id=teacher.id,
                teacher_no=teacher.teacher_no,
                teacher_name=teacher.name,
                role=link.role,
            )
            for link, teacher in await self.teachers.list_for(course_id)
        ]

    async def set_teachers(
        self, course_id: int, payload: CourseTeacherUpdate, access: AccessContext
    ) -> list[CourseTeacherRead]:
        self._ensure_admin(access)
        await self._require_course(course_id)
        items: list[tuple[int, str]] = []
        seen: set[int] = set()
        for item in payload.items:
            if item.teacher_id in seen:
                raise ConflictError("教师重复")
            teacher = await self.session.get(Teacher, item.teacher_id)
            if teacher is None:
                raise NotFoundError("教师不存在")
            seen.add(item.teacher_id)
            items.append((teacher.id, item.role or "primary"))
        await self.teachers.replace(course_id, items)
        await self.session.commit()
        return await self.list_teachers(course_id, access)

    async def list_classes(self, course_id: int, access: AccessContext) -> list[CourseClassRead]:
        await self._ensure_course_read(course_id, access)
        return [
            CourseClassRead(class_id=school_class.id, class_name=school_class.name)
            for _, school_class in await self.classes.list_for(course_id)
        ]

    async def set_classes(
        self, course_id: int, payload: CourseClassUpdate, access: AccessContext
    ) -> list[CourseClassRead]:
        self._ensure_admin(access)
        await self._require_course(course_id)
        class_ids: list[int] = []
        for item in payload.items:
            school_class = await SchoolClassRepository(self.session).get(item.class_id)
            if school_class is None:
                raise NotFoundError("班级不存在")
            if item.class_id not in class_ids:
                class_ids.append(item.class_id)
        await self.classes.replace(course_id, class_ids)
        await self.session.commit()
        return await self.list_classes(course_id, access)

    async def _ensure_course_read(self, course_id: int, access: AccessContext) -> None:
        await self._require_course(course_id)
        if access.scope.kind is ScopeKind.ALL:
            return
        if course_id in access.teaching_course_ids:
            return
        raise PermissionDeniedError("只能查看本人所授课程")

    async def _require_course(self, course_id: int) -> Course:
        course = await self.session.get(Course, course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        return course

    @staticmethod
    def _ensure_admin(access: AccessContext) -> None:
        if "admin" not in access.role_codes:
            raise PermissionDeniedError("仅管理员可配置课程教师与面向班级")


class ScheduleChangeService:
    """调课/停课/代课申请与审批。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ScheduleChangeRepository(session)
        self.schedules = ScheduleRepository(session)

    async def list_changes(
        self,
        *,
        access: AccessContext,
        status: RequestStatus | None,
        page: int,
        page_size: int,
    ) -> Page[ScheduleChangeRead]:
        access.ensure(Permission.SCHEDULE_READ)
        params = PageParams(page=page, page_size=page_size)
        course_ids: frozenset[int] | None = None
        if access.scope.kind is ScopeKind.CLASSES:
            course_ids = access.scope.course_ids
        elif access.scope.kind is not ScopeKind.ALL:
            return Page[ScheduleChangeRead](
                items=[], total=0, page=params.page, page_size=params.page_size
            )
        rows, total = await self.repository.paginated_rows(
            status=status.value if status is not None else None,
            course_ids=course_ids,
            page=params.page,
            page_size=params.page_size,
        )
        return Page[ScheduleChangeRead](
            items=[self._to_read(change, schedule, course) for change, schedule, course in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create(
        self, payload: ScheduleChangeCreate, access: AccessContext
    ) -> ScheduleChangeRead:
        access.ensure(Permission.SCHEDULE_CHANGE)
        schedule = await self.schedules.get(payload.schedule_id)
        if schedule is None:
            raise NotFoundError("排课不存在")
        course = await self.session.get(Course, schedule.course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        access.ensure_course_write(course)
        change = ScheduleChange(
            schedule_id=schedule.id,
            change_date=payload.change_date,
            kind=payload.kind,
            new_weekday=payload.new_weekday,
            new_start_period=payload.new_start_period,
            new_end_period=payload.new_end_period,
            new_classroom=payload.new_classroom,
            new_teacher_id=payload.new_teacher_id,
            reason=payload.reason,
            status=RequestStatus.PENDING,
            requested_by=access.user.id,
        )
        await self.repository.add(change)
        await self.session.commit()
        return self._to_read(change, schedule, course)

    async def decide(
        self,
        change_id: int,
        payload: ScheduleChangeDecision,
        access: AccessContext,
        *,
        approved: bool,
    ) -> ScheduleChangeRead:
        access.ensure(Permission.SCHEDULE_CHANGE)
        if "admin" not in access.role_codes:
            raise PermissionDeniedError("仅管理员可审批调课")
        change = await self.repository.get(change_id)
        if change is None:
            raise NotFoundError("调课申请不存在")
        if change.status is not RequestStatus.PENDING:
            raise ConflictError("该申请已处理")
        change.status = RequestStatus.APPROVED if approved else RequestStatus.REJECTED
        change.approved_by = access.user.id
        change.decided_at = utc_now()
        if approved:
            await self._apply(change)
        await self.session.commit()
        schedule = await self.schedules.get(change.schedule_id)
        if schedule is None:
            raise NotFoundError("排课不存在")
        course = await self.session.get(Course, schedule.course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        return self._to_read(change, schedule, course)

    async def _apply(self, change: ScheduleChange) -> None:
        schedule = await self.schedules.get(change.schedule_id)
        if schedule is None:
            return
        if change.kind.value == "cancel":
            schedule.status = ScheduleStatus.CANCELLED
            return
        if change.new_weekday is not None:
            schedule.weekday = change.new_weekday
        if change.new_start_period is not None:
            schedule.start_period = change.new_start_period
        if change.new_end_period is not None:
            schedule.end_period = change.new_end_period
        if change.new_classroom:
            schedule.classroom = change.new_classroom

    @staticmethod
    def _to_read(change: ScheduleChange, schedule: Schedule, course: Course) -> ScheduleChangeRead:
        return ScheduleChangeRead(
            id=change.id,
            schedule_id=schedule.id,
            course_id=course.id,
            course_name=course.name,
            change_date=change.change_date,
            kind=change.kind,
            new_weekday=change.new_weekday,
            new_start_period=change.new_start_period,
            new_end_period=change.new_end_period,
            new_classroom=change.new_classroom,
            new_teacher_id=change.new_teacher_id,
            reason=change.reason,
            status=change.status,
            requested_by=change.requested_by,
            approved_by=change.approved_by,
            decided_at=change.decided_at,
        )
