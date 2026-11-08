"""请假契约：申请、审批、流程配置与流转事件。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from campus.models.enums import (
    ApplicantType,
    ApproverType,
    LeaveEventAction,
    LeaveStatus,
    LeaveType,
)


class LeaveApply(BaseModel):
    """提交请假申请。"""

    leave_type: LeaveType = LeaveType.PERSONAL
    start_at: datetime
    end_at: datetime
    reason: str = Field(min_length=1, max_length=500)


class LeaveDecision(BaseModel):
    """审批意见。"""

    remark: str = Field(default="", max_length=200)


class LeaveApprovalRead(BaseModel):
    """某一级审批记录。"""

    step_no: int
    step_name: str = ""
    approver_type: ApproverType = ApproverType.ROLE
    approver_role_code: str = ""
    status: LeaveStatus
    approver_name: str | None = None
    remark: str = ""
    assigned_at: datetime | None = None
    decided_at: datetime | None = None


class LeaveEventRead(BaseModel):
    """流转时间线事件。"""

    id: int
    action: LeaveEventAction
    actor_name: str
    detail: str
    created_at: datetime


class LeaveActions(BaseModel):
    """当前用户对这条申请可执行的动作。"""

    can_approve: bool = False
    can_reject: bool = False
    can_cancel: bool = False
    can_revoke: bool = False


class LeaveRead(BaseModel):
    """请假申请输出。"""

    id: int
    applicant_type: ApplicantType
    student_id: int | None
    student_name: str | None
    student_no: str | None
    teacher_id: int | None
    teacher_name: str | None
    leave_type: LeaveType
    start_at: datetime
    end_at: datetime
    days: float
    reason: str
    status: LeaveStatus
    current_step: int
    required_steps: int
    flow_id: int | None = None
    flow_name: str = ""
    approvals: list[LeaveApprovalRead] = Field(default_factory=list)
    events: list[LeaveEventRead] = Field(default_factory=list)
    actions: LeaveActions = Field(default_factory=LeaveActions)
    created_at: datetime


class LeaveFlowStepInput(BaseModel):
    """流程节点入参。"""

    step_no: int = Field(ge=1, le=20)
    name: str = Field(min_length=1, max_length=50)
    approver_type: ApproverType = ApproverType.ROLE
    role_code: str | None = Field(default=None, max_length=50)
    user_id: int | None = None
    group_id: int | None = None


class LeaveFlowCreate(BaseModel):
    """新增请假流程。"""

    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    applicant_type: ApplicantType | None = None
    leave_type: LeaveType | None = None
    min_days: float = Field(default=0, ge=0, le=365)
    max_days: float | None = Field(default=None, ge=0, le=365)
    priority: int = Field(default=0, ge=0, le=1000)
    is_active: bool = True
    description: str = Field(default="", max_length=255)
    steps: list[LeaveFlowStepInput] = Field(default_factory=list)


class LeaveFlowUpdate(BaseModel):
    """更新请假流程；提供 steps 时整体替换节点。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    applicant_type: ApplicantType | None = None
    leave_type: LeaveType | None = None
    min_days: float | None = Field(default=None, ge=0, le=365)
    max_days: float | None = Field(default=None, ge=0, le=365)
    priority: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=255)
    steps: list[LeaveFlowStepInput] | None = None


class LeaveFlowStepRead(BaseModel):
    """流程节点输出。"""

    id: int
    step_no: int
    name: str
    approver_type: ApproverType
    role_code: str | None = None
    user_id: int | None = None
    user_name: str | None = None
    group_id: int | None = None
    group_name: str | None = None


class LeaveFlowRead(BaseModel):
    """流程输出。"""

    id: int
    code: str
    name: str
    applicant_type: ApplicantType | None
    leave_type: LeaveType | None
    min_days: float
    max_days: float | None
    priority: int
    is_active: bool
    description: str
    steps: list[LeaveFlowStepRead] = Field(default_factory=list)


class LeaveFlowPreview(BaseModel):
    """按条件预览命中的流程。"""

    flow: LeaveFlowRead | None = None
    matched: bool = False
    reason: str = ""
