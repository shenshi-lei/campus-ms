"""领域枚举：以字符串入库，避免魔法数字。"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """用户角色。"""

    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class Gender(StrEnum):
    """性别。"""

    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class EnrollmentStatus(StrEnum):
    """选课状态。"""

    ENROLLED = "enrolled"
    DROPPED = "dropped"


class AttendanceStatus(StrEnum):
    """考勤状态。"""

    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    LEAVE = "leave"


class FeeStatus(StrEnum):
    """缴费状态。"""

    UNPAID = "unpaid"
    PAID = "paid"
    REFUNDED = "refunded"


class PermissionEffect(StrEnum):
    """用户级权限覆盖效果。"""

    ALLOW = "allow"
    DENY = "deny"


class DepartmentKind(StrEnum):
    """院系/部门类型。"""

    COLLEGE = "college"
    OFFICE = "office"


class SemesterStatus(StrEnum):
    """学期状态。"""

    PLANNED = "planned"
    ACTIVE = "active"
    CLOSED = "closed"


class StudentStatus(StrEnum):
    """学籍状态。"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    WITHDRAWN = "withdrawn"
    GRADUATED = "graduated"
    RETAINED = "retained"


class EmploymentStatus(StrEnum):
    """教师在职状态。"""

    ACTIVE = "active"
    PART_TIME = "part_time"
    RETIRED = "retired"
    RESIGNED = "resigned"


class StaffType(StrEnum):
    """教师编制类型。"""

    PERMANENT = "permanent"
    CONTRACT = "contract"
    PART_TIME = "part_time"
    INTERN = "intern"


class Education(StrEnum):
    """学历。"""

    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTOR = "doctor"
    OTHER = "other"


class ClassRole(StrEnum):
    """班干部角色。"""

    NONE = "none"
    MONITOR = "monitor"
    VICE_MONITOR = "vice_monitor"
    SECRETARY = "secretary"
    STUDY = "study"
    LIFE = "life"


class ResidenceType(StrEnum):
    """住宿类型。"""

    BOARDING = "boarding"
    DAY = "day"


class ClassStatus(StrEnum):
    """班级状态。"""

    ACTIVE = "active"
    GRADUATED = "graduated"
    INACTIVE = "inactive"


class LeaveType(StrEnum):
    """请假类型。"""

    PERSONAL = "personal"
    SICK = "sick"
    BUSINESS = "business"
    COMPENSATORY = "compensatory"
    BEREAVEMENT = "bereavement"
    MATERNITY = "maternity"
    OTHER = "other"


class LeaveStatus(StrEnum):
    """请假/审批状态。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApplicantType(StrEnum):
    """申请人类型。"""

    STUDENT = "student"
    TEACHER = "teacher"


class NoticeAudience(StrEnum):
    """通知受众。"""

    ALL = "all"
    TEACHER = "teacher"
    STUDENT = "student"
    CLASS = "class"
    GROUP = "group"


class CourseType(StrEnum):
    """课程类型。"""

    REQUIRED = "required"
    ELECTIVE = "elective"
    PRACTICE = "practice"
    PUBLIC = "public"


class AssessmentType(StrEnum):
    """考核方式。"""

    EXAM = "exam"
    CHECK = "check"
    PAPER = "paper"
    PROJECT = "project"


class ScheduleStatus(StrEnum):
    """排课状态。"""

    ACTIVE = "active"
    CANCELLED = "cancelled"


class ScheduleChangeKind(StrEnum):
    """调课类型。"""

    SWAP = "swap"
    CANCEL = "cancel"
    SUBSTITUTE = "substitute"


class RequestStatus(StrEnum):
    """通用审批状态：调课等。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApproverType(StrEnum):
    """审批节点解析方式。"""

    ROLE = "role"
    HEAD_TEACHER = "head_teacher"
    USER = "user"
    GROUP = "group"


class LeaveEventAction(StrEnum):
    """请假流转事件。"""

    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    CANCEL = "cancel"
    REVOKE = "revoke"
    ATTENDANCE_SYNC = "attendance_sync"
    COMMENT = "comment"


class CalendarEventKind(StrEnum):
    """日程类型。"""

    MEETING = "meeting"
    ACTIVITY = "activity"
    EXAM = "exam"
    HOLIDAY = "holiday"
    PERSONAL = "personal"
    OTHER = "other"


class CalendarVisibility(StrEnum):
    """日程可见范围。"""

    PERSONAL = "personal"
    DEPARTMENT = "department"
    CLASS = "class"
    SCHOOL = "school"


class ParticipantResponse(StrEnum):
    """日程参与人回复状态。"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class GroupMemberType(StrEnum):
    """群组成员类型。"""

    USER = "user"
    STUDENT = "student"
    TEACHER = "teacher"
    DEPARTMENT = "department"
    CLASS = "class"


class NotificationKind(StrEnum):
    """站内消息类型。"""

    APPROVAL = "approval"
    CALENDAR = "calendar"
    NOTICE = "notice"
    SYSTEM = "system"
