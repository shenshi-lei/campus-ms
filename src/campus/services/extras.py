"""扩展模块服务：考勤、课表、宿舍、缴费。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ReferenceExistsError,
)
from campus.core.pagination import PageParams
from campus.db.base import utc_now
from campus.models.attendance import Attendance
from campus.models.course import Course
from campus.models.dorm import Dorm, DormAssignment
from campus.models.enums import FeeStatus, Gender
from campus.models.fee import Fee
from campus.models.schedule import Schedule
from campus.models.student import Student
from campus.repositories.extras import (
    AttendanceRepository,
    DormAssignmentRepository,
    DormRepository,
    FeeRepository,
    ScheduleRepository,
)
from campus.schemas.attendance import AttendanceBulk, AttendanceRead
from campus.schemas.common import Message, Page
from campus.schemas.dorm import (
    DormAssignInput,
    DormAssignmentRead,
    DormCreate,
    DormRead,
)
from campus.schemas.fee import FeeCreate, FeeRead
from campus.schemas.schedule import ScheduleCreate, ScheduleRead
from campus.services.access import AccessContext, ScopeKind


class AttendanceService:
    """考勤登记与查询。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AttendanceRepository(session)

    async def list_attendance(
        self,
        *,
        access: AccessContext,
        course_id: int | None,
        student_id: int | None,
        day: date | None,
        page: int,
        page_size: int,
    ) -> Page[AttendanceRead]:
        params = PageParams(page=page, page_size=page_size)
        course_ids: frozenset[int] | None = None
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            pass
        elif scope.kind is ScopeKind.CLASSES:
            if course_id is not None and course_id not in scope.course_ids:
                raise PermissionDeniedError("只能查看本人所授课程的考勤")
            course_ids = scope.course_ids
        elif scope.kind is ScopeKind.SELF:
            student_id = access.student_id
        else:
            return Page[AttendanceRead](
                items=[], total=0, page=params.page, page_size=params.page_size
            )
        rows, total = await self.repository.paginated_rows(
            course_id=course_id,
            student_id=student_id,
            day=day,
            page=params.page,
            page_size=params.page_size,
            course_ids=course_ids,
        )
        return Page[AttendanceRead](
            items=[
                AttendanceRead(
                    id=record.id,
                    student_id=student.id,
                    student_no=student.student_no,
                    student_name=student.name,
                    course_id=course.id,
                    course_name=course.name,
                    date=record.date,
                    period_no=record.period_no,
                    status=record.status,
                    remark=record.remark,
                )
                for record, student, course in rows
            ],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def bulk_record(
        self, payload: AttendanceBulk, access: AccessContext
    ) -> list[AttendanceRead]:
        """同课程、同日期批量登记，重复登记按覆盖处理。"""
        saved: list[AttendanceRead] = []
        for item in payload.items:
            course = await self.session.get(Course, item.course_id)
            if course is None:
                raise NotFoundError("课程不存在")
            access.ensure_course_write(course)
            student = await self.session.get(Student, item.student_id)
            if student is None:
                raise NotFoundError("学生不存在")
            record = await self.repository.get_one(
                item.student_id, item.course_id, item.date, item.period_no
            )
            if record is None:
                record = Attendance(
                    student_id=item.student_id,
                    course_id=item.course_id,
                    date=item.date,
                    period_no=item.period_no,
                    schedule_id=item.schedule_id,
                )
                await self.repository.add(record)
            record.status = item.status
            record.remark = item.remark
            if item.schedule_id is not None:
                record.schedule_id = item.schedule_id
            saved.append(
                AttendanceRead(
                    id=record.id,
                    student_id=student.id,
                    student_no=student.student_no,
                    student_name=student.name,
                    course_id=course.id,
                    course_name=course.name,
                    date=record.date,
                    period_no=record.period_no,
                    status=record.status,
                    remark=record.remark,
                )
            )
        await self.session.commit()
        return saved


class ScheduleService:
    """排课。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ScheduleRepository(session)

    async def list_schedules(
        self,
        *,
        access: AccessContext,
        class_id: int | None,
        teacher_id: int | None,
        weekday: int | None,
        page: int,
        page_size: int,
    ) -> Page[ScheduleRead]:
        params = PageParams(page=page, page_size=page_size)
        course_ids: frozenset[int] | None = None
        student_id: int | None = None
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            pass
        elif scope.kind is ScopeKind.CLASSES:
            if class_id is not None and class_id not in scope.class_ids:
                raise PermissionDeniedError("只能查看权限范围内的班级课表")
            if teacher_id is not None and teacher_id != access.teacher_id:
                raise PermissionDeniedError("只能查看本人课表")
            course_ids = scope.course_ids
        elif scope.kind is ScopeKind.SELF:
            student_id = access.student_id
        else:
            return Page[ScheduleRead](
                items=[], total=0, page=params.page, page_size=params.page_size
            )
        rows, total = await self.repository.paginated_rows(
            class_id=class_id,
            teacher_id=teacher_id,
            weekday=weekday,
            page=params.page,
            page_size=params.page_size,
            course_ids=course_ids,
            student_id=student_id,
        )
        return Page[ScheduleRead](
            items=[self._to_read(schedule, course) for schedule, course in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create_schedule(self, payload: ScheduleCreate, access: AccessContext) -> ScheduleRead:
        from campus.services.timetable import TimetableService

        course = await self.session.get(Course, payload.course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        schedule = await TimetableService(self.session).create(payload, access)
        return self._to_read(schedule, course)

    async def delete_schedule(self, schedule_id: int, access: AccessContext) -> Message:
        schedule = await self.repository.get(schedule_id)
        if schedule is None:
            raise NotFoundError("排课不存在")
        course = await self.session.get(Course, schedule.course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        access.ensure_course_write(course)
        await self.repository.delete(schedule)
        await self.session.commit()
        return Message(message="排课已删除")

    @staticmethod
    def _to_read(schedule: Schedule, course: Course) -> ScheduleRead:
        return ScheduleRead(
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
        )


class DormService:
    """宿舍与床位。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DormRepository(session)
        self.assignment_repository = DormAssignmentRepository(session)

    async def list_dorms(
        self, *, access: AccessContext, building: str | None, page: int, page_size: int
    ) -> Page[DormRead]:
        params = PageParams(page=page, page_size=page_size)
        rows, total = await self.repository.paginated_with_occupied(
            page=params.page, page_size=params.page_size, building=building
        )
        return Page[DormRead](
            items=[
                DormRead(
                    id=dorm.id,
                    building=dorm.building,
                    room_no=dorm.room_no,
                    capacity=dorm.capacity,
                    gender=dorm.gender,
                    occupied=occupied,
                )
                for dorm, occupied in rows
            ],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create_dorm(self, payload: DormCreate) -> DormRead:
        existing = await self.session.scalar(
            select(Dorm).where(Dorm.building == payload.building, Dorm.room_no == payload.room_no)
        )
        if existing is not None:
            raise ConflictError("该房间已存在")
        dorm = Dorm(**payload.model_dump())
        await self.repository.add(dorm)
        await self.session.commit()
        await self.session.refresh(dorm)
        return DormRead(
            id=dorm.id,
            building=dorm.building,
            room_no=dorm.room_no,
            capacity=dorm.capacity,
            gender=dorm.gender,
            occupied=0,
        )

    async def my_assignment(self, access: AccessContext) -> DormAssignmentRead | None:
        """学生查看本人床位。"""
        if access.student_id is None:
            raise PermissionDeniedError("当前账号没有关联的学生档案")
        assignment = await self.assignment_repository.get_by_student(access.student_id)
        if assignment is None:
            return None
        student = await self.session.get(Student, assignment.student_id)
        dorm = await self.session.get(Dorm, assignment.dorm_id)
        if student is None or dorm is None:
            return None
        return DormAssignmentRead(
            id=assignment.id,
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.name,
            dorm_id=dorm.id,
            building=dorm.building,
            room_no=dorm.room_no,
            bed_no=assignment.bed_no,
        )

    async def assign(self, payload: DormAssignInput) -> DormAssignmentRead:
        student = await self.session.get(Student, payload.student_id)
        if student is None:
            raise NotFoundError("学生不存在")
        if not student.is_active:
            raise ConflictError("学生已停用，不能分配宿舍")
        dorm = await self.session.get(Dorm, payload.dorm_id)
        if dorm is None:
            raise NotFoundError("宿舍不存在")
        if await self.assignment_repository.get_by_student(student.id):
            raise ConflictError("该学生已有宿舍床位")
        occupied = await self.assignment_repository.count_for_dorm(dorm.id)
        if occupied >= dorm.capacity:
            raise ConflictError("宿舍已满")
        if (
            dorm.gender is not Gender.UNKNOWN
            and student.gender is not Gender.UNKNOWN
            and dorm.gender != student.gender
        ):
            raise ConflictError("学生性别与宿舍不匹配")
        bed_taken = await self.session.scalar(
            select(DormAssignment).where(
                DormAssignment.dorm_id == dorm.id,
                DormAssignment.bed_no == payload.bed_no,
            )
        )
        if bed_taken is not None:
            raise ConflictError("该床位已被占用")
        assignment = DormAssignment(student_id=student.id, dorm_id=dorm.id, bed_no=payload.bed_no)
        await self.assignment_repository.add(assignment)
        await self.session.commit()
        await self.session.refresh(assignment)
        return DormAssignmentRead(
            id=assignment.id,
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.name,
            dorm_id=dorm.id,
            building=dorm.building,
            room_no=dorm.room_no,
            bed_no=assignment.bed_no,
        )

    async def unassign(self, assignment_id: int) -> Message:
        assignment = await self.assignment_repository.get(assignment_id)
        if assignment is None:
            raise NotFoundError("床位分配记录不存在")
        await self.assignment_repository.delete(assignment)
        await self.session.commit()
        return Message(message="已退宿")

    async def list_assignments(
        self,
        *,
        access: AccessContext,
        dorm_id: int | None,
        page: int,
        page_size: int,
    ) -> Page[DormAssignmentRead]:
        params = PageParams(page=page, page_size=page_size)
        class_ids: frozenset[int] | None = None
        student_id: int | None = None
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            pass
        elif scope.kind is ScopeKind.CLASSES:
            class_ids = scope.class_ids
        elif scope.kind is ScopeKind.SELF:
            student_id = access.student_id
        else:
            return Page[DormAssignmentRead](
                items=[], total=0, page=params.page, page_size=params.page_size
            )
        rows, total = await self.assignment_repository.paginated_rows(
            dorm_id=dorm_id,
            page=params.page,
            page_size=params.page_size,
            class_ids=class_ids,
            student_id=student_id,
        )
        return Page[DormAssignmentRead](
            items=[
                DormAssignmentRead(
                    id=assignment.id,
                    student_id=student.id,
                    student_no=student.student_no,
                    student_name=student.name,
                    dorm_id=dorm.id,
                    building=dorm.building,
                    room_no=dorm.room_no,
                    bed_no=assignment.bed_no,
                )
                for assignment, student, dorm in rows
            ],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def delete_dorm(self, dorm_id: int) -> Message:
        dorm = await self.repository.get(dorm_id)
        if dorm is None:
            raise NotFoundError("宿舍不存在")
        if await self.assignment_repository.count_for_dorm(dorm_id) > 0:
            raise ReferenceExistsError("房间仍有学生入住，不能删除")
        await self.repository.delete(dorm)
        await self.session.commit()
        return Message(message="宿舍已删除")


class FeeService:
    """缴费管理。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = FeeRepository(session)

    async def list_fees(
        self,
        *,
        access: AccessContext,
        student_id: int | None,
        status: FeeStatus | None,
        page: int,
        page_size: int,
    ) -> Page[FeeRead]:
        params = PageParams(page=page, page_size=page_size)
        class_ids: frozenset[int] | None = None
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            pass
        elif scope.kind is ScopeKind.CLASSES:
            class_ids = scope.class_ids
        elif scope.kind is ScopeKind.SELF:
            student_id = access.student_id
        else:
            return Page[FeeRead](items=[], total=0, page=params.page, page_size=params.page_size)
        rows, total = await self.repository.paginated_rows(
            student_id=student_id,
            status=status,
            page=params.page,
            page_size=params.page_size,
            class_ids=class_ids,
        )
        return Page[FeeRead](
            items=[self._to_read(fee, student) for fee, student in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create_fee(self, payload: FeeCreate) -> FeeRead:
        student = await self.session.get(Student, payload.student_id)
        if student is None:
            raise NotFoundError("学生不存在")
        fee = Fee(**payload.model_dump())
        await self.repository.add(fee)
        await self.session.commit()
        await self.session.refresh(fee)
        return self._to_read(fee, student)

    async def pay(self, fee_id: int, access: AccessContext) -> FeeRead:
        fee = await self.repository.get(fee_id)
        if fee is None:
            raise NotFoundError("费用记录不存在")
        if access.scope.kind is ScopeKind.SELF:
            if fee.student_id != access.student_id:
                raise PermissionDeniedError("只能支付本人费用")
        elif access.scope.kind is not ScopeKind.ALL:
            raise PermissionDeniedError("没有权限支付该费用")
        if fee.status is FeeStatus.PAID:
            raise ConflictError("该费用已缴清")
        fee.status = FeeStatus.PAID
        fee.paid_at = utc_now()
        student = await self.session.get(Student, fee.student_id)
        if student is None:
            raise NotFoundError("学生不存在")
        await self.session.commit()
        return self._to_read(fee, student)

    @staticmethod
    def _to_read(fee: Fee, student: Student) -> FeeRead:
        return FeeRead(
            id=fee.id,
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.name,
            item=fee.item,
            amount=float(fee.amount),
            due_date=fee.due_date,
            status=fee.status,
            paid_at=fee.paid_at,
        )
