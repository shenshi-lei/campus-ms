"""ORM 模型导出：导入本模块即完成全部表注册。"""

from __future__ import annotations

from campus.models.attendance import Attendance
from campus.models.audit import AuditLog
from campus.models.authz import (
    AuthPermission,
    AuthRole,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)
from campus.models.calendar import CalendarEvent, CalendarEventAttendee
from campus.models.course import Course
from campus.models.dorm import Dorm, DormAssignment
from campus.models.enrollment import Enrollment
from campus.models.fee import Fee
from campus.models.group import UserGroup, UserGroupMember
from campus.models.leave import (
    LeaveApproval,
    LeaveEvent,
    LeaveFlow,
    LeaveFlowStep,
    LeavePolicy,
    LeaveRequest,
    StudentStatusHistory,
)
from campus.models.notice import Notice
from campus.models.notification import Notification
from campus.models.org import Department, Semester, Subject
from campus.models.schedule import Schedule
from campus.models.school_class import SchoolClass
from campus.models.score import Score
from campus.models.setting import SystemSetting
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.teaching import CourseClass, CourseTeacher, ScheduleChange
from campus.models.user import User

__all__ = [
    "Attendance",
    "AuditLog",
    "AuthPermission",
    "AuthRole",
    "CalendarEvent",
    "CalendarEventAttendee",
    "Course",
    "CourseClass",
    "CourseTeacher",
    "Department",
    "Dorm",
    "DormAssignment",
    "Enrollment",
    "Fee",
    "LeaveApproval",
    "LeaveEvent",
    "LeaveFlow",
    "LeaveFlowStep",
    "LeavePolicy",
    "LeaveRequest",
    "Notice",
    "Notification",
    "RolePermission",
    "Schedule",
    "ScheduleChange",
    "SchoolClass",
    "Score",
    "Semester",
    "SystemSetting",
    "Student",
    "StudentStatusHistory",
    "Subject",
    "Teacher",
    "User",
    "UserGroup",
    "UserGroupMember",
    "UserPermissionOverride",
    "UserRole",
]
