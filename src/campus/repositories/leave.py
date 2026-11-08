"""请假、流程与学籍异动仓储。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from campus.models.enums import ApplicantType, LeaveStatus, LeaveType
from campus.models.leave import (
    LeaveApproval,
    LeaveEvent,
    LeaveFlow,
    LeaveFlowStep,
    LeavePolicy,
    LeaveRequest,
    StudentStatusHistory,
)
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.repositories.base import BaseRepository

LeaveRow = tuple[LeaveRequest, Student | None, Teacher | None]


class LeaveRepository(BaseRepository[LeaveRequest]):
    """请假申请查询。"""

    model = LeaveRequest

    def filtered(
        self,
        *,
        status: LeaveStatus | None = None,
        applicant_type: ApplicantType | None = None,
        leave_type: LeaveType | None = None,
        student_id: int | None = None,
        teacher_id: int | None = None,
        class_ids: frozenset[int] | None = None,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Select[LeaveRequest, Student, Teacher]:
        statement = (
            select(LeaveRequest, Student, Teacher)
            .outerjoin(Student, LeaveRequest.student_id == Student.id)
            .outerjoin(Teacher, LeaveRequest.teacher_id == Teacher.id)
        )
        if status is not None:
            statement = statement.where(LeaveRequest.status == status)
        if applicant_type is not None:
            statement = statement.where(LeaveRequest.applicant_type == applicant_type)
        if leave_type is not None:
            statement = statement.where(LeaveRequest.leave_type == leave_type)
        if student_id is not None:
            statement = statement.where(LeaveRequest.student_id == student_id)
        if teacher_id is not None:
            statement = statement.where(LeaveRequest.teacher_id == teacher_id)
        if class_ids is not None:
            statement = statement.where(Student.class_id.in_(class_ids))
        if keyword:
            like = f"%{keyword}%"
            statement = statement.where(
                or_(
                    Student.name.like(like),
                    Student.student_no.like(like),
                    Teacher.name.like(like),
                    Teacher.teacher_no.like(like),
                    LeaveRequest.reason.like(like),
                )
            )
        if date_from is not None:
            statement = statement.where(LeaveRequest.start_at >= date_from)
        if date_to is not None:
            statement = statement.where(LeaveRequest.end_at <= date_to)
        return statement.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc())

    async def paginated_rows(
        self,
        *,
        page: int,
        page_size: int,
        status: LeaveStatus | None = None,
        applicant_type: ApplicantType | None = None,
        leave_type: LeaveType | None = None,
        student_id: int | None = None,
        teacher_id: int | None = None,
        class_ids: frozenset[int] | None = None,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[Sequence[LeaveRow], int]:
        statement = self.filtered(
            status=status,
            applicant_type=applicant_type,
            leave_type=leave_type,
            student_id=student_id,
            teacher_id=teacher_id,
            class_ids=class_ids,
            keyword=keyword,
            date_from=date_from,
            date_to=date_to,
        )
        total = int(
            await self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )
        result = await self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        rows = [(row[0], row[1], row[2]) for row in result.all()]
        return rows, total

    async def approvals(self, request_id: int) -> list[LeaveApproval]:
        rows = await self.session.scalars(
            select(LeaveApproval)
            .where(LeaveApproval.leave_request_id == request_id)
            .order_by(LeaveApproval.step_no)
        )
        return list(rows.all())

    async def approvals_for_requests(
        self, request_ids: list[int]
    ) -> dict[int, list[LeaveApproval]]:
        if not request_ids:
            return {}
        rows = await self.session.scalars(
            select(LeaveApproval)
            .where(LeaveApproval.leave_request_id.in_(request_ids))
            .order_by(LeaveApproval.step_no)
        )
        result: dict[int, list[LeaveApproval]] = {}
        for item in rows.all():
            result.setdefault(item.leave_request_id, []).append(item)
        return result

    async def events(self, request_id: int) -> list[LeaveEvent]:
        rows = await self.session.scalars(
            select(LeaveEvent)
            .where(LeaveEvent.leave_request_id == request_id)
            .order_by(LeaveEvent.created_at, LeaveEvent.id)
        )
        return list(rows.all())

    async def events_for_requests(self, request_ids: list[int]) -> dict[int, list[LeaveEvent]]:
        if not request_ids:
            return {}
        rows = await self.session.scalars(
            select(LeaveEvent)
            .where(LeaveEvent.leave_request_id.in_(request_ids))
            .order_by(LeaveEvent.created_at, LeaveEvent.id)
        )
        result: dict[int, list[LeaveEvent]] = {}
        for item in rows.all():
            result.setdefault(item.leave_request_id, []).append(item)
        return result

    def pending_for(
        self,
        *,
        role_codes: frozenset[str],
        head_class_ids: frozenset[int],
        user_id: int | None = None,
        group_ids: frozenset[int] = frozenset(),
        include_all: bool = False,
    ) -> Select[LeaveRequest, Student, Teacher]:
        """当前步骤等待指定角色、班主任、指定用户或群组处理的申请。"""
        statement = (
            select(LeaveRequest, Student, Teacher)
            .join(
                LeaveApproval,
                and_(
                    LeaveApproval.leave_request_id == LeaveRequest.id,
                    LeaveApproval.step_no == LeaveRequest.current_step,
                    LeaveApproval.status == LeaveStatus.PENDING,
                ),
            )
            .outerjoin(Student, LeaveRequest.student_id == Student.id)
            .outerjoin(Teacher, LeaveRequest.teacher_id == Teacher.id)
            .where(LeaveRequest.status == LeaveStatus.PENDING)
        )
        if not include_all:
            matches: list[ColumnElement[bool]] = [
                LeaveApproval.approver_role_code.in_(role_codes),
            ]
            if user_id is not None:
                matches.append(LeaveApproval.approver_user_id == user_id)
            if head_class_ids:
                matches.append(
                    and_(
                        LeaveApproval.approver_role_code == "head_teacher",
                        Student.class_id.in_(head_class_ids),
                    )
                )
            if group_ids:
                matches.append(LeaveApproval.approver_group_id.in_(group_ids))
            statement = statement.where(or_(*matches))
        return statement.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc())

    async def count_by_status(self) -> dict[LeaveStatus, int]:
        rows = await self.session.execute(
            select(LeaveRequest.status, func.count(LeaveRequest.id)).group_by(LeaveRequest.status)
        )
        return {status: int(count) for status, count in rows.all()}


class LeaveFlowRepository(BaseRepository[LeaveFlow]):
    """请假流程查询。"""

    model = LeaveFlow

    async def list_all(self, *, active_only: bool = False) -> list[LeaveFlow]:
        statement = select(LeaveFlow).order_by(LeaveFlow.priority.desc(), LeaveFlow.id)
        if active_only:
            statement = statement.where(LeaveFlow.is_active.is_(True))
        rows = await self.session.scalars(statement)
        return list(rows.all())

    async def get_by_code(self, code: str) -> LeaveFlow | None:
        return await self.session.scalar(select(LeaveFlow).where(LeaveFlow.code == code))

    async def steps(self, flow_id: int) -> list[LeaveFlowStep]:
        rows = await self.session.scalars(
            select(LeaveFlowStep)
            .where(LeaveFlowStep.flow_id == flow_id)
            .order_by(LeaveFlowStep.step_no)
        )
        return list(rows.all())

    async def steps_for_flows(self, flow_ids: list[int]) -> dict[int, list[LeaveFlowStep]]:
        if not flow_ids:
            return {}
        rows = await self.session.scalars(
            select(LeaveFlowStep)
            .where(LeaveFlowStep.flow_id.in_(flow_ids))
            .order_by(LeaveFlowStep.step_no)
        )
        result: dict[int, list[LeaveFlowStep]] = {}
        for item in rows.all():
            result.setdefault(item.flow_id, []).append(item)
        return result


class LeavePolicyRepository(BaseRepository[LeavePolicy]):
    """审批策略查询（兼容旧数据）。"""

    model = LeavePolicy

    async def list_for(self, applicant_type: ApplicantType) -> list[LeavePolicy]:
        rows = await self.session.scalars(
            select(LeavePolicy)
            .where(LeavePolicy.applicant_type == applicant_type)
            .order_by(LeavePolicy.step_no)
        )
        return list(rows.all())


class StudentStatusRepository(BaseRepository[StudentStatusHistory]):
    """学籍异动记录。"""

    model = StudentStatusHistory

    async def history(self, student_id: int) -> list[StudentStatusHistory]:
        rows = await self.session.scalars(
            select(StudentStatusHistory)
            .where(StudentStatusHistory.student_id == student_id)
            .order_by(StudentStatusHistory.effective_date.desc(), StudentStatusHistory.id.desc())
        )
        return list(rows.all())
