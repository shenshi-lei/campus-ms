"""请假模型：申请单、两级审批与审批策略。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import (
    ApplicantType,
    ApproverType,
    LeaveEventAction,
    LeaveStatus,
    LeaveType,
    StudentStatus,
)


def _enum(enum_cls: type, length: int = 20) -> SAEnum:
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [item.value for item in cls],
    )


class LeaveFlow(TimestampMixin, Base):
    """可配置请假流程：按申请人类型、请假类型与天数区间匹配。"""

    __tablename__ = "leave_flows"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    applicant_type: Mapped[ApplicantType | None] = mapped_column(
        _enum(ApplicantType), nullable=True
    )
    leave_type: Mapped[LeaveType | None] = mapped_column(_enum(LeaveType), nullable=True)
    min_days: Mapped[float] = mapped_column(Numeric(4, 1, asdecimal=False), default=0.0)
    max_days: Mapped[float | None] = mapped_column(Numeric(4, 1, asdecimal=False), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class LeaveFlowStep(TimestampMixin, Base):
    """流程节点：审批人可以是角色、班主任、指定用户或群组。"""

    __tablename__ = "leave_flow_steps"
    __table_args__ = (UniqueConstraint("flow_id", "step_no", name="uq_leave_flow_steps_flow_step"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    flow_id: Mapped[int] = mapped_column(ForeignKey("leave_flows.id", ondelete="CASCADE"))
    step_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(50))
    approver_type: Mapped[ApproverType] = mapped_column(
        _enum(ApproverType), default=ApproverType.ROLE
    )
    role_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_groups.id", ondelete="SET NULL"), nullable=True
    )


class LeaveRequest(TimestampMixin, Base):
    """一条请假申请；学生与教师共用，student_id/teacher_id 二选一。"""

    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint(
            "(student_id IS NOT NULL) <> (teacher_id IS NOT NULL)",
            name="ck_leave_requests_applicant",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    applicant_type: Mapped[ApplicantType] = mapped_column(_enum(ApplicantType))
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=True
    )
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True
    )
    leave_type: Mapped[LeaveType] = mapped_column(_enum(LeaveType), default=LeaveType.PERSONAL)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    days: Mapped[float] = mapped_column(Numeric(4, 1, asdecimal=False), default=1.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[LeaveStatus] = mapped_column(_enum(LeaveStatus), default=LeaveStatus.PENDING)
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    required_steps: Mapped[int] = mapped_column(Integer, default=1)
    flow_id: Mapped[int | None] = mapped_column(
        ForeignKey("leave_flows.id", ondelete="SET NULL"), nullable=True
    )
    flow_name: Mapped[str] = mapped_column(String(100), default="")
    final_approver_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeaveApproval(TimestampMixin, Base):
    """审批流某一级的处理记录。"""

    __tablename__ = "leave_approvals"
    __table_args__ = (
        UniqueConstraint("leave_request_id", "step_no", name="uq_leave_approvals_request_step"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    leave_request_id: Mapped[int] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="CASCADE")
    )
    step_no: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str] = mapped_column(String(50), default="")
    approver_type: Mapped[ApproverType] = mapped_column(
        _enum(ApproverType), default=ApproverType.ROLE
    )
    approver_role_code: Mapped[str] = mapped_column(String(50), default="")
    approver_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approver_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_groups.id", ondelete="SET NULL"), nullable=True
    )
    approver_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[LeaveStatus] = mapped_column(_enum(LeaveStatus), default=LeaveStatus.PENDING)
    remark: Mapped[str] = mapped_column(String(200), default="")
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeaveEvent(TimestampMixin, Base):
    """请假流转时间线：提交、审批、驳回、撤销、考勤同步。"""

    __tablename__ = "leave_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    leave_request_id: Mapped[int] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="CASCADE")
    )
    action: Mapped[LeaveEventAction] = mapped_column(_enum(LeaveEventAction))
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str] = mapped_column(String(50), default="")
    detail: Mapped[str] = mapped_column(String(500), default="")


class LeavePolicy(TimestampMixin, Base):
    """审批策略：申请类型 + 级别 -> 审批角色 + 生效天数。"""

    __tablename__ = "leave_policies"
    __table_args__ = (
        UniqueConstraint("applicant_type", "step_no", name="uq_leave_policies_type_step"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_type: Mapped[ApplicantType] = mapped_column(_enum(ApplicantType))
    step_no: Mapped[int] = mapped_column(Integer)
    approver_role_code: Mapped[str] = mapped_column(String(50))
    min_days: Mapped[float] = mapped_column(Numeric(4, 1, asdecimal=False), default=0.0)


class StudentStatusHistory(TimestampMixin, Base):
    """学籍异动记录：休学/复学/退学/毕业等。"""

    __tablename__ = "student_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    from_status: Mapped[StudentStatus | None] = mapped_column(_enum(StudentStatus), nullable=True)
    to_status: Mapped[StudentStatus] = mapped_column(_enum(StudentStatus))
    effective_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(200), default="")
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
