"""请假服务：可配置审批流、流转时间线与考勤联动。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from campus.core.pagination import PageParams
from campus.db.base import utc_now
from campus.models.attendance import Attendance
from campus.models.authz import AuthRole, UserRole
from campus.models.enrollment import Enrollment
from campus.models.enums import (
    ApplicantType,
    ApproverType,
    AttendanceStatus,
    GroupMemberType,
    LeaveEventAction,
    LeaveStatus,
    LeaveType,
    NotificationKind,
)
from campus.models.group import UserGroup, UserGroupMember
from campus.models.leave import (
    LeaveApproval,
    LeaveEvent,
    LeaveFlow,
    LeaveFlowStep,
    LeavePolicy,
    LeaveRequest,
)
from campus.models.school_class import SchoolClass
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.user import User
from campus.repositories.leave import (
    LeaveFlowRepository,
    LeavePolicyRepository,
    LeaveRepository,
)
from campus.schemas.common import Page
from campus.schemas.leave import (
    LeaveActions,
    LeaveApply,
    LeaveApprovalRead,
    LeaveDecision,
    LeaveEventRead,
    LeaveFlowCreate,
    LeaveFlowPreview,
    LeaveFlowRead,
    LeaveFlowStepInput,
    LeaveFlowStepRead,
    LeaveFlowUpdate,
    LeaveRead,
)
from campus.services.access import AccessContext, Permission, ScopeKind
from campus.services.group import GroupService
from campus.services.notification import NotificationService

DEFAULT_FLOWS: tuple[dict[str, object], ...] = (
    {
        "code": "student_short",
        "name": "学生请假（3 天内）",
        "applicant_type": ApplicantType.STUDENT,
        "leave_type": None,
        "min_days": 0.0,
        "max_days": 2.9,
        "priority": 10,
        "steps": [("班主任审批", ApproverType.HEAD_TEACHER, "head_teacher")],
    },
    {
        "code": "student_long",
        "name": "学生请假（3 天及以上）",
        "applicant_type": ApplicantType.STUDENT,
        "leave_type": None,
        "min_days": 3.0,
        "max_days": None,
        "priority": 20,
        "steps": [
            ("班主任审批", ApproverType.HEAD_TEACHER, "head_teacher"),
            ("学工处审批", ApproverType.ROLE, "student_affairs"),
        ],
    },
    {
        "code": "teacher_short",
        "name": "教师请假（3 天内）",
        "applicant_type": ApplicantType.TEACHER,
        "leave_type": None,
        "min_days": 0.0,
        "max_days": 2.9,
        "priority": 10,
        "steps": [("教务主任审批", ApproverType.ROLE, "academic_director")],
    },
    {
        "code": "teacher_long",
        "name": "教师请假（3 天及以上）",
        "applicant_type": ApplicantType.TEACHER,
        "leave_type": None,
        "min_days": 3.0,
        "max_days": None,
        "priority": 20,
        "steps": [
            ("教务主任审批", ApproverType.ROLE, "academic_director"),
            ("管理员审批", ApproverType.ROLE, "admin"),
        ],
    },
)

ROLE_LABELS = {
    "admin": "管理员",
    "teacher": "教师",
    "student": "学生",
    "student_affairs": "学工处",
    "academic_director": "教务主任",
    "head_teacher": "班主任",
}


def _as_utc(value: datetime | None) -> datetime | None:
    """把 SQLite 读出的 naive UTC 标记为 UTC，便于前端转本地时区。"""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class LeaveService:
    """请假申请、审批与流程配置。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = LeaveRepository(session)
        self.flows = LeaveFlowRepository(session)
        self.policies = LeavePolicyRepository(session)
        self.notifications = NotificationService(session)

    async def ensure_default_policies(self) -> None:
        """幂等写入旧版默认两级审批策略（兼容历史数据）。"""
        rows = await self.session.scalars(select(LeavePolicy))
        existing = {(item.applicant_type, item.step_no) for item in rows.all()}
        defaults: dict[ApplicantType, list[tuple[int, str, float]]] = {
            ApplicantType.STUDENT: [(1, "head_teacher", 0.0), (2, "student_affairs", 3.0)],
            ApplicantType.TEACHER: [(1, "academic_director", 0.0), (2, "admin", 3.0)],
        }
        for applicant_type, rules in defaults.items():
            for step, role, min_days in rules:
                if (applicant_type, step) not in existing:
                    self.session.add(
                        LeavePolicy(
                            applicant_type=applicant_type,
                            step_no=step,
                            approver_role_code=role,
                            min_days=min_days,
                        )
                    )
        await self.session.commit()

    async def ensure_default_flows(self) -> None:
        """首次启动写入默认流程；已有流程时不覆盖。"""
        existing = await self.flows.list_all()
        if existing:
            return
        for item in DEFAULT_FLOWS:
            steps = cast(list[tuple[str, ApproverType, str]], item["steps"])
            flow = LeaveFlow(
                code=str(item["code"]),
                name=str(item["name"]),
                applicant_type=cast(ApplicantType | None, item["applicant_type"]),
                leave_type=cast(LeaveType | None, item["leave_type"]),
                min_days=float(cast(float, item["min_days"])),
                max_days=cast(float | None, item["max_days"]),
                priority=int(cast(int, item["priority"])),
                is_active=True,
                description="系统默认流程，可在系统设置中调整",
            )
            self.session.add(flow)
            await self.session.flush()
            for index, (name, approver_type, role_code) in enumerate(steps, start=1):
                self.session.add(
                    LeaveFlowStep(
                        flow_id=flow.id,
                        step_no=index,
                        name=name,
                        approver_type=approver_type,
                        role_code=role_code,
                    )
                )
        await self.session.commit()

    async def apply(self, payload: LeaveApply, access: AccessContext) -> LeaveRead:
        """提交请假；按条件匹配流程并快照审批节点。"""
        access.ensure(Permission.LEAVE_APPLY)
        applicant_type, student_id, teacher_id = self._applicant(access)
        if payload.end_at <= payload.start_at:
            raise ConflictError("结束时间必须晚于开始时间")
        days = self._days(payload.start_at, payload.end_at)
        flow = await self._match_flow(applicant_type, payload.leave_type, days)
        if flow is not None:
            steps = await self.flows.steps(flow.id)
            required_steps = len(steps)
        else:
            policies = await self._legacy_rules(applicant_type)
            applicable = [item for item in policies if days >= item[2]]
            required_steps = max((item[0] for item in applicable), default=1)
            steps = []
        request = LeaveRequest(
            applicant_user_id=access.user.id,
            applicant_type=applicant_type,
            student_id=student_id,
            teacher_id=teacher_id,
            leave_type=payload.leave_type or LeaveType.PERSONAL,
            start_at=payload.start_at,
            end_at=payload.end_at,
            days=days,
            reason=payload.reason,
            status=LeaveStatus.PENDING,
            current_step=1,
            required_steps=max(1, required_steps),
            flow_id=flow.id if flow is not None else None,
            flow_name=flow.name if flow is not None else "默认审批流程",
        )
        await self.repository.add(request)
        now = utc_now()
        if steps:
            for flow_step in steps:
                self.session.add(
                    LeaveApproval(
                        leave_request_id=request.id,
                        step_no=flow_step.step_no,
                        step_name=flow_step.name,
                        approver_type=flow_step.approver_type,
                        approver_role_code=flow_step.role_code or self._role_for_type(flow_step),
                        approver_user_id=flow_step.user_id,
                        approver_group_id=flow_step.group_id,
                        assigned_at=now,
                    )
                )
        else:
            policies = await self._legacy_rules(applicant_type)
            for step_no, role_code, min_days in policies:
                if days < min_days:
                    continue
                self.session.add(
                    LeaveApproval(
                        leave_request_id=request.id,
                        step_no=step_no,
                        step_name=ROLE_LABELS.get(role_code, role_code),
                        approver_type=ApproverType.HEAD_TEACHER
                        if role_code == "head_teacher"
                        else ApproverType.ROLE,
                        approver_role_code=role_code,
                        assigned_at=now,
                    )
                )
        self.session.add(
            LeaveEvent(
                leave_request_id=request.id,
                action=LeaveEventAction.SUBMIT,
                actor_id=access.user.id,
                actor_name=access.display_name,
                detail=f"提交{self._type_label(payload.leave_type)}申请，共 {days} 天",
            )
        )
        self._notify_applicant(request, "请假申请已提交", "等待审批")
        for step in await self.repository.approvals(request.id):
            if step.step_no == 1:
                await self._notify_approvers(request, step, access.display_name)
        await self.session.commit()
        return await self._read(request, access)

    async def list_leaves(
        self,
        *,
        access: AccessContext,
        status: LeaveStatus | None,
        applicant_type: ApplicantType | None,
        leave_type: LeaveType | None,
        mine: bool,
        keyword: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> Page[LeaveRead]:
        """按数据范围列出请假。"""
        access.ensure(Permission.LEAVE_READ)
        params = PageParams(page=page, page_size=page_size)
        student_id: int | None = None
        teacher_id: int | None = None
        class_ids: frozenset[int] | None = None
        scope = access.scope
        if mine or scope.kind is ScopeKind.SELF:
            if access.student_id is not None:
                student_id = access.student_id
            elif access.teacher_id is not None:
                teacher_id = access.teacher_id
            else:
                return Page[LeaveRead](
                    items=[], total=0, page=params.page, page_size=params.page_size
                )
        elif scope.kind is ScopeKind.CLASSES:
            class_ids = access.head_class_ids | access.teaching_class_ids
        elif scope.kind is not ScopeKind.ALL:
            return Page[LeaveRead](items=[], total=0, page=params.page, page_size=params.page_size)
        rows, total = await self.repository.paginated_rows(
            page=params.page,
            page_size=params.page_size,
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
        items = await self._read_many(rows, access)
        return Page[LeaveRead](
            items=items, total=total, page=params.page, page_size=params.page_size
        )

    async def pending(self, access: AccessContext, *, page: int, page_size: int) -> Page[LeaveRead]:
        """当前用户可审批的申请（分页）。"""
        access.ensure(Permission.LEAVE_APPROVE)
        group_ids = await self._user_group_ids(access)
        statement = self.repository.pending_for(
            role_codes=access.role_codes,
            head_class_ids=access.head_class_ids,
            user_id=access.user.id,
            group_ids=group_ids,
            include_all="admin" in access.role_codes,
        )
        result = await self.session.execute(statement)
        rows = [(row[0], row[1], row[2]) for row in result.all()]
        filtered = [row for row in rows if await self._row_approvable(access, row[0])]
        params = PageParams(page=page, page_size=page_size)
        start = params.offset
        items = await self._read_many(filtered[start : start + params.page_size], access)
        return Page[LeaveRead](
            items=items, total=len(filtered), page=params.page, page_size=params.page_size
        )

    async def get(self, request_id: int, access: AccessContext) -> LeaveRead:
        """查看单条请假详情。"""
        request = await self._require(request_id)
        student = await self._student(request.student_id)
        if not self._visible(access, request, student):
            raise PermissionDeniedError("只能查看权限范围内的请假")
        return await self._read(request, access)

    async def approve(
        self, request_id: int, payload: LeaveDecision, access: AccessContext
    ) -> LeaveRead:
        """通过当前审批级。"""
        return await self._decide(request_id, payload, access, approved=True)

    async def reject(
        self, request_id: int, payload: LeaveDecision, access: AccessContext
    ) -> LeaveRead:
        """驳回当前审批级。"""
        return await self._decide(request_id, payload, access, approved=False)

    async def cancel(self, request_id: int, access: AccessContext) -> LeaveRead:
        """申请人撤销未开始审批的申请。"""
        request = await self._require(request_id)
        if not self._is_owner(access, request):
            raise PermissionDeniedError("只能撤销本人的请假")
        if request.status is not LeaveStatus.PENDING or request.current_step != 1:
            raise ConflictError("当前状态不能撤销")
        approvals = await self.repository.approvals(request.id)
        if not approvals or approvals[0].status is not LeaveStatus.PENDING:
            raise ConflictError("当前状态不能撤销")
        request.status = LeaveStatus.CANCELLED
        for item in approvals:
            if item.status is LeaveStatus.PENDING:
                item.status = LeaveStatus.CANCELLED
        self._event(request, LeaveEventAction.CANCEL, access, "申请人撤销")
        await self.session.commit()
        return await self._read(request, access)

    async def revoke(
        self, request_id: int, payload: LeaveDecision, access: AccessContext
    ) -> LeaveRead:
        """管理员撤回已通过的申请并回滚考勤。"""
        access.ensure(Permission.LEAVE_APPROVE)
        if "admin" not in access.role_codes:
            raise PermissionDeniedError("仅管理员可以撤回已通过的请假")
        request = await self._require(request_id)
        if request.status is not LeaveStatus.APPROVED:
            raise ConflictError("只有已通过的申请可以撤回")
        request.status = LeaveStatus.CANCELLED
        request.decided_at = utc_now()
        for item in await self.repository.approvals(request.id):
            if item.status is LeaveStatus.PENDING:
                item.status = LeaveStatus.CANCELLED
        await self._rollback_attendance(request)
        self._event(request, LeaveEventAction.REVOKE, access, payload.remark or "管理员撤回")
        await self.session.commit()
        return await self._read(request, access)

    async def list_flows(self) -> list[LeaveFlowRead]:
        """流程列表。"""
        flows = await self.flows.list_all()
        steps = await self.flows.steps_for_flows([item.id for item in flows])
        return [await self._to_flow_read(flow, steps.get(flow.id, [])) for flow in flows]

    async def preview_flow(
        self, applicant_type: ApplicantType, leave_type: LeaveType, days: float
    ) -> LeaveFlowPreview:
        """按条件预览命中的流程。"""
        flow = await self._match_flow(applicant_type, leave_type, days)
        if flow is None:
            return LeaveFlowPreview(matched=False, reason="未匹配到流程，将使用默认审批")
        steps = await self.flows.steps(flow.id)
        return LeaveFlowPreview(matched=True, flow=await self._to_flow_read(flow, steps))

    async def create_flow(self, payload: LeaveFlowCreate) -> LeaveFlowRead:
        """新增流程。"""
        if await self.flows.get_by_code(payload.code):
            raise ConflictError("流程编码已存在")
        self._validate_flow(payload, payload.steps)
        flow = LeaveFlow(
            code=payload.code,
            name=payload.name,
            applicant_type=payload.applicant_type,
            leave_type=payload.leave_type,
            min_days=payload.min_days,
            max_days=payload.max_days,
            priority=payload.priority,
            is_active=payload.is_active,
            description=payload.description,
        )
        self.session.add(flow)
        await self.session.flush()
        await self._replace_steps(flow.id, payload.steps)
        await self.session.commit()
        return await self._flow_read(flow.id)

    async def update_flow(self, flow_id: int, payload: LeaveFlowUpdate) -> LeaveFlowRead:
        """更新流程。"""
        flow = await self._require_flow(flow_id)
        data = payload.model_dump(exclude_unset=True, exclude={"steps"})
        for key, value in data.items():
            setattr(flow, key, value)
        if payload.steps is not None:
            self._validate_flow(flow, payload.steps)
            await self._replace_steps(flow.id, payload.steps)
        elif flow.is_active:
            steps = await self.flows.steps(flow.id)
            if not steps:
                raise ConflictError("启用流程至少需要一个审批节点")
        await self.session.commit()
        return await self._flow_read(flow.id)

    async def delete_flow(self, flow_id: int) -> None:
        """删除未被使用的流程。"""
        flow = await self._require_flow(flow_id)
        used = await self.session.scalar(
            select(LeaveRequest.id).where(LeaveRequest.flow_id == flow_id).limit(1)
        )
        if used is not None:
            raise ConflictError("流程已被请假单使用，请改为停用")
        await self.repository.session.delete(flow)
        await self.session.commit()

    async def _decide(
        self,
        request_id: int,
        payload: LeaveDecision,
        access: AccessContext,
        *,
        approved: bool,
    ) -> LeaveRead:
        access.ensure(Permission.LEAVE_APPROVE)
        request = await self._require(request_id)
        if request.status is not LeaveStatus.PENDING:
            raise ConflictError("该申请已处理")
        approvals = await self.repository.approvals(request.id)
        current = next((item for item in approvals if item.step_no == request.current_step), None)
        if current is None or current.status is not LeaveStatus.PENDING:
            raise ConflictError("当前审批级状态异常")
        student = await self._student(request.student_id)
        teacher = await self._teacher(request.teacher_id)
        if not await self._can_approve(access, request, student, current):
            raise PermissionDeniedError("无权审批该申请")
        applicant_name = (
            student.name
            if student is not None
            else teacher.name
            if teacher is not None
            else "申请人"
        )

        now = utc_now()
        current.status = LeaveStatus.APPROVED if approved else LeaveStatus.REJECTED
        current.approver_id = access.user.id
        current.remark = payload.remark
        current.decided_at = now
        if approved:
            self._event(
                request,
                LeaveEventAction.APPROVE,
                access,
                payload.remark or "同意",
            )
        else:
            self._event(
                request,
                LeaveEventAction.REJECT,
                access,
                payload.remark or "驳回",
            )
        if not approved:
            request.status = LeaveStatus.REJECTED
            request.final_approver_id = access.user.id
            request.decided_at = now
            for item in approvals:
                if item.step_no > current.step_no and item.status is LeaveStatus.PENDING:
                    item.status = LeaveStatus.CANCELLED
            self._notify_applicant(request, "请假申请被驳回", payload.remark or "请查看审批意见")
        elif request.current_step < request.required_steps:
            request.current_step += 1
            next_step = next(
                (item for item in approvals if item.step_no == request.current_step), None
            )
            if next_step is not None:
                next_step.assigned_at = now
                await self._notify_approvers(request, next_step, applicant_name)
        else:
            request.status = LeaveStatus.APPROVED
            request.final_approver_id = access.user.id
            request.decided_at = now
            await self._apply_attendance(request)
            self._event(
                request,
                LeaveEventAction.ATTENDANCE_SYNC,
                access,
                "已同步请假期间考勤",
            )
            self._notify_applicant(request, "请假申请已通过", "审批已完成")
        await self.session.commit()
        return await self._read(request, access)

    async def _read_many(
        self,
        rows: Sequence[tuple[LeaveRequest, Student | None, Teacher | None]],
        access: AccessContext,
    ) -> list[LeaveRead]:
        requests = [row[0] for row in rows]
        approvals_map = await self.repository.approvals_for_requests([item.id for item in requests])
        events_map = await self.repository.events_for_requests([item.id for item in requests])
        approver_ids = {
            item.approver_id
            for approvals in approvals_map.values()
            for item in approvals
            if item.approver_id is not None
        } | {
            item.approver_user_id
            for approvals in approvals_map.values()
            for item in approvals
            if item.approver_user_id is not None
        }
        names = await self._user_names(approver_ids)
        group_ids = await self._user_group_ids(access)
        return [
            self._to_read(
                request,
                student,
                teacher,
                approvals_map.get(request.id, []),
                events_map.get(request.id, []),
                names,
                access,
                group_ids,
            )
            for request, student, teacher in rows
        ]

    async def _read(self, request: LeaveRequest, access: AccessContext) -> LeaveRead:
        approvals = await self.repository.approvals(request.id)
        events = await self.repository.events(request.id)
        names = await self._user_names(
            {item.approver_id for item in approvals if item.approver_id is not None}
            | {item.approver_user_id for item in approvals if item.approver_user_id is not None}
        )
        student = await self._student(request.student_id)
        teacher = await self._teacher(request.teacher_id)
        group_ids = await self._user_group_ids(access)
        return self._to_read(request, student, teacher, approvals, events, names, access, group_ids)

    def _to_read(
        self,
        request: LeaveRequest,
        student: Student | None,
        teacher: Teacher | None,
        approvals: list[LeaveApproval],
        events: list[LeaveEvent],
        names: dict[int, str],
        access: AccessContext,
        group_ids: frozenset[int] = frozenset(),
    ) -> LeaveRead:
        current = next((item for item in approvals if item.step_no == request.current_step), None)
        can_approve = (
            request.status is LeaveStatus.PENDING
            and current is not None
            and current.status is LeaveStatus.PENDING
            and (
                "admin" in access.role_codes
                or current.approver_user_id == access.user.id
                or (
                    current.approver_group_id is not None and current.approver_group_id in group_ids
                )
                or current.approver_role_code in access.role_codes
                or (
                    current.approver_role_code == "head_teacher"
                    and student is not None
                    and student.class_id in access.head_class_ids
                )
            )
        )
        return LeaveRead(
            id=request.id,
            applicant_type=request.applicant_type,
            student_id=request.student_id,
            student_name=student.name if student else None,
            student_no=student.student_no if student else None,
            teacher_id=request.teacher_id,
            teacher_name=teacher.name if teacher else None,
            leave_type=request.leave_type,
            start_at=request.start_at,
            end_at=request.end_at,
            days=float(request.days),
            reason=request.reason,
            status=request.status,
            current_step=request.current_step,
            required_steps=request.required_steps,
            flow_id=request.flow_id,
            flow_name=request.flow_name,
            approvals=[
                LeaveApprovalRead(
                    step_no=item.step_no,
                    step_name=item.step_name,
                    approver_type=item.approver_type,
                    approver_role_code=item.approver_role_code,
                    status=item.status,
                    approver_name=(
                        names.get(item.approver_id) if item.approver_id is not None else None
                    ),
                    remark=item.remark,
                    assigned_at=_as_utc(item.assigned_at),
                    decided_at=_as_utc(item.decided_at),
                )
                for item in approvals
            ],
            events=[
                LeaveEventRead(
                    id=item.id,
                    action=item.action,
                    actor_name=item.actor_name,
                    detail=item.detail,
                    created_at=_as_utc(item.created_at) or item.created_at,
                )
                for item in events
            ],
            actions=LeaveActions(
                can_approve=can_approve,
                can_reject=can_approve,
                can_cancel=(
                    request.status is LeaveStatus.PENDING
                    and request.current_step == 1
                    and self._is_owner(access, request)
                ),
                can_revoke=(
                    request.status is LeaveStatus.APPROVED and "admin" in access.role_codes
                ),
            ),
            created_at=_as_utc(request.created_at) or request.created_at,
        )

    async def _to_flow_read(self, flow: LeaveFlow, steps: list[LeaveFlowStep]) -> LeaveFlowRead:
        user_ids = {item.user_id for item in steps if item.user_id is not None}
        group_ids = {item.group_id for item in steps if item.group_id is not None}
        user_names = await self._user_names(user_ids)
        group_names = await self._group_names(group_ids)
        return LeaveFlowRead(
            id=flow.id,
            code=flow.code,
            name=flow.name,
            applicant_type=flow.applicant_type,
            leave_type=flow.leave_type,
            min_days=float(flow.min_days),
            max_days=float(flow.max_days) if flow.max_days is not None else None,
            priority=flow.priority,
            is_active=flow.is_active,
            description=flow.description,
            steps=[
                LeaveFlowStepRead(
                    id=item.id,
                    step_no=item.step_no,
                    name=item.name,
                    approver_type=item.approver_type,
                    role_code=item.role_code,
                    user_id=item.user_id,
                    user_name=user_names.get(item.user_id) if item.user_id else None,
                    group_id=item.group_id,
                    group_name=group_names.get(item.group_id) if item.group_id else None,
                )
                for item in steps
            ],
        )

    async def _flow_read(self, flow_id: int) -> LeaveFlowRead:
        flow = await self._require_flow(flow_id)
        return await self._to_flow_read(flow, await self.flows.steps(flow_id))

    async def _replace_steps(self, flow_id: int, steps: list[LeaveFlowStepInput]) -> None:
        existing = await self.flows.steps(flow_id)
        for item in existing:
            await self.session.delete(item)
        await self.session.flush()
        for step in sorted(steps, key=lambda item: item.step_no):
            self.session.add(
                LeaveFlowStep(
                    flow_id=flow_id,
                    step_no=step.step_no,
                    name=step.name,
                    approver_type=step.approver_type,
                    role_code=step.role_code,
                    user_id=step.user_id,
                    group_id=step.group_id,
                )
            )
        await self.session.flush()

    def _validate_flow(
        self, flow: LeaveFlow | LeaveFlowCreate, steps: list[LeaveFlowStepInput]
    ) -> None:
        if flow.is_active and not steps:
            raise ConflictError("启用流程至少需要一个审批节点")
        seen: set[int] = set()
        for step in steps:
            if step.step_no in seen:
                raise ConflictError("审批节点序号不能重复")
            seen.add(step.step_no)
            if step.approver_type is ApproverType.ROLE and not step.role_code:
                raise ConflictError("角色审批必须选择角色")
            if step.approver_type is ApproverType.USER and step.user_id is None:
                raise ConflictError("指定人员审批必须选择人员")
            if step.approver_type is ApproverType.GROUP and step.group_id is None:
                raise ConflictError("群组审批必须选择群组")

    async def _match_flow(
        self, applicant_type: ApplicantType, leave_type: LeaveType, days: float
    ) -> LeaveFlow | None:
        flows = await self.flows.list_all(active_only=True)
        matched: list[LeaveFlow] = []
        for flow in flows:
            if flow.applicant_type is not None and flow.applicant_type is not applicant_type:
                continue
            if flow.leave_type is not None and flow.leave_type is not leave_type:
                continue
            if days < float(flow.min_days):
                continue
            if flow.max_days is not None and days > float(flow.max_days):
                continue
            matched.append(flow)
        matched.sort(key=lambda item: (item.priority, item.id), reverse=True)
        return matched[0] if matched else None

    async def _legacy_rules(self, applicant_type: ApplicantType) -> list[tuple[int, str, float]]:
        policies = await self.policies.list_for(applicant_type)
        if policies:
            return [
                (item.step_no, item.approver_role_code, float(item.min_days)) for item in policies
            ]
        return (
            [(1, "head_teacher", 0.0), (2, "student_affairs", 3.0)]
            if applicant_type is ApplicantType.STUDENT
            else [(1, "academic_director", 0.0), (2, "admin", 3.0)]
        )

    async def _can_approve(
        self,
        access: AccessContext,
        request: LeaveRequest,
        student: Student | None,
        approval: LeaveApproval,
    ) -> bool:
        if "admin" in access.role_codes:
            return True
        if approval.approver_user_id is not None:
            return approval.approver_user_id == access.user.id
        if approval.approver_group_id is not None:
            group_ids = await self._user_group_ids(access)
            return approval.approver_group_id in group_ids
        if approval.approver_role_code == "head_teacher":
            return (
                student is not None
                and student.class_id is not None
                and student.class_id in access.head_class_ids
            )
        return approval.approver_role_code in access.role_codes

    async def _row_approvable(self, access: AccessContext, request: LeaveRequest) -> bool:
        approvals = await self.repository.approvals(request.id)
        current = next((item for item in approvals if item.step_no == request.current_step), None)
        if current is None:
            return False
        student = await self._student(request.student_id)
        return await self._can_approve(access, request, student, current)

    async def _notify_approvers(
        self, request: LeaveRequest, approval: LeaveApproval, actor_name: str
    ) -> None:
        user_ids = await self._approval_user_ids(request, approval)
        if not user_ids:
            return
        self.notifications.add(
            user_ids,
            kind=NotificationKind.APPROVAL,
            title=f"待审批：{request.flow_name or '请假申请'}",
            body=f"{actor_name} 提交的请假申请等待{approval.step_name or '审批'}",
            link=f"/leaves?request={request.id}",
        )

    async def _approval_user_ids(self, request: LeaveRequest, approval: LeaveApproval) -> set[int]:
        if approval.approver_user_id is not None:
            return {approval.approver_user_id}
        if approval.approver_group_id is not None:
            return await GroupService(self.session).user_ids_for_group(approval.approver_group_id)
        if approval.approver_role_code == "head_teacher":
            student = await self._student(request.student_id)
            if student is None or student.class_id is None:
                return set()
            head_teacher_id = await self.session.scalar(
                select(SchoolClass.head_teacher_id).where(SchoolClass.id == student.class_id)
            )
            if head_teacher_id is None:
                return set()
            user_id = await self.session.scalar(
                select(Teacher.user_id).where(Teacher.id == head_teacher_id)
            )
            return {int(user_id)} if user_id is not None else set()
        return await self._users_with_role(approval.approver_role_code)

    async def _users_with_role(self, role_code: str) -> set[int]:
        user_ids = {
            int(item)
            for item in (
                await self.session.scalars(
                    select(User.id).where(User.role == role_code, User.is_active.is_(True))
                )
            ).all()
        }
        rows = await self.session.scalars(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(AuthRole, AuthRole.id == UserRole.role_id)
            .where(AuthRole.code == role_code, User.is_active.is_(True))
        )
        user_ids.update(int(item) for item in rows.all())
        return user_ids

    async def _user_group_ids(self, access: AccessContext) -> frozenset[int]:
        rows = await self.session.scalars(
            select(UserGroupMember.group_id)
            .join(UserGroup, UserGroup.id == UserGroupMember.group_id)
            .where(
                UserGroup.is_active.is_(True),
                (
                    (UserGroupMember.user_id == access.user.id)
                    | (
                        (UserGroupMember.member_type == GroupMemberType.USER)
                        & (UserGroupMember.member_id == access.user.id)
                    )
                ),
            )
            .distinct()
        )
        return frozenset(int(item) for item in rows.all())

    async def _group_names(self, group_ids: set[int]) -> dict[int, str]:
        if not group_ids:
            return {}
        rows = await self.session.execute(
            select(UserGroup.id, UserGroup.name).where(UserGroup.id.in_(group_ids))
        )
        return {int(group_id): str(name) for group_id, name in rows.all()}

    async def _apply_attendance(self, request: LeaveRequest) -> None:
        """学生请假通过后，把区间内的考勤标记为请假。"""
        if request.student_id is None:
            return
        start = request.start_at.date()
        end = request.end_at.date()
        if (end - start).days > 31:
            return
        course_ids = {
            int(item)
            for item in (
                await self.session.scalars(
                    select(Enrollment.course_id).where(Enrollment.student_id == request.student_id)
                )
            ).all()
        }
        remark = f"请假单#{request.id}"
        for course_id in course_ids:
            day = start
            while day <= end:
                record = await self.session.scalar(
                    select(Attendance).where(
                        Attendance.student_id == request.student_id,
                        Attendance.course_id == course_id,
                        Attendance.date == day,
                    )
                )
                if record is None:
                    self.session.add(
                        Attendance(
                            student_id=request.student_id,
                            course_id=course_id,
                            date=day,
                            status=AttendanceStatus.LEAVE,
                            remark=remark,
                            leave_request_id=request.id,
                        )
                    )
                else:
                    record.status = AttendanceStatus.LEAVE
                    record.remark = remark
                    record.leave_request_id = request.id
                day += timedelta(days=1)

    async def _rollback_attendance(self, request: LeaveRequest) -> None:
        """撤回时清理由该请假单写入的考勤。"""
        rows = await self.session.scalars(
            select(Attendance).where(Attendance.leave_request_id == request.id)
        )
        for record in rows.all():
            record.status = AttendanceStatus.PRESENT
            record.leave_request_id = None
            record.remark = "请假撤回"

    def _event(
        self, request: LeaveRequest, action: LeaveEventAction, access: AccessContext, detail: str
    ) -> None:
        self.session.add(
            LeaveEvent(
                leave_request_id=request.id,
                action=action,
                actor_id=access.user.id,
                actor_name=access.display_name,
                detail=detail,
            )
        )

    def _notify_applicant(self, request: LeaveRequest, title: str, body: str) -> None:
        if request.applicant_user_id is None:
            return
        self.notifications.add(
            {request.applicant_user_id},
            kind=NotificationKind.APPROVAL,
            title=title,
            body=body,
            link=f"/leaves?request={request.id}",
        )

    def _applicant(self, access: AccessContext) -> tuple[ApplicantType, int | None, int | None]:
        if access.teacher_id is not None:
            return ApplicantType.TEACHER, None, access.teacher_id
        if access.student_id is not None:
            return ApplicantType.STUDENT, access.student_id, None
        raise PermissionDeniedError("当前账号没有关联的学生或教师档案")

    async def _require(self, request_id: int) -> LeaveRequest:
        request = await self.repository.get(request_id)
        if request is None:
            raise NotFoundError("请假申请不存在")
        return request

    async def _require_flow(self, flow_id: int) -> LeaveFlow:
        flow = await self.flows.get(flow_id)
        if flow is None:
            raise NotFoundError("请假流程不存在")
        return flow

    async def _student(self, student_id: int | None) -> Student | None:
        if student_id is None:
            return None
        return await self.session.get(Student, student_id)

    async def _teacher(self, teacher_id: int | None) -> Teacher | None:
        if teacher_id is None:
            return None
        return await self.session.get(Teacher, teacher_id)

    async def _user_names(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        names: dict[int, str] = {}
        rows = await self.session.execute(
            select(User.id, User.username).where(User.id.in_(user_ids))
        )
        for user_id, username in rows.all():
            names[int(user_id)] = str(username)
        students = await self.session.execute(
            select(Student.user_id, Student.name).where(Student.user_id.in_(user_ids))
        )
        for student_user_id, name in students.all():
            if student_user_id is not None:
                names[int(student_user_id)] = str(name)
        teachers = await self.session.execute(
            select(Teacher.user_id, Teacher.name).where(Teacher.user_id.in_(user_ids))
        )
        for teacher_user_id, name in teachers.all():
            if teacher_user_id is not None:
                names[int(teacher_user_id)] = str(name)
        return names

    @staticmethod
    def _role_for_type(step: LeaveFlowStep) -> str:
        if step.approver_type is ApproverType.HEAD_TEACHER:
            return "head_teacher"
        if step.approver_type is ApproverType.GROUP:
            return "group"
        return ""

    @staticmethod
    def _type_label(leave_type: LeaveType) -> str:
        labels = {
            LeaveType.PERSONAL: "事假",
            LeaveType.SICK: "病假",
            LeaveType.BUSINESS: "公出",
            LeaveType.COMPENSATORY: "调休",
            LeaveType.BEREAVEMENT: "婚丧",
            LeaveType.MATERNITY: "产假",
            LeaveType.OTHER: "其他",
        }
        return labels.get(leave_type, "请假")

    @staticmethod
    def _days(start: datetime, end: datetime) -> float:
        if end <= start:
            raise ConflictError("结束时间必须晚于开始时间")
        half_days = max(1, round((end - start).total_seconds() / 43200))
        return round(half_days * 0.5, 1)

    def _visible(
        self, access: AccessContext, request: LeaveRequest, student: Student | None
    ) -> bool:
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            return True
        if scope.kind is ScopeKind.SELF:
            return self._is_owner(access, request)
        if scope.kind is ScopeKind.CLASSES:
            if request.teacher_id is not None and request.teacher_id == access.teacher_id:
                return True
            return student is not None and student.class_id in scope.class_ids
        return False

    @staticmethod
    def _is_owner(access: AccessContext, request: LeaveRequest) -> bool:
        if request.student_id is not None:
            return request.student_id == access.student_id
        return request.teacher_id is not None and request.teacher_id == access.teacher_id
