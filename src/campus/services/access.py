"""访问控制：权限点、数据范围与字段策略。

权限点存数据库；本模块只保存权限码规范、默认授权（首次种子/兜底）与访问上下文计算。
数据范围由关系推导：admin=ALL，教师=班主任/任课班级，学生=SELF。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import PermissionDeniedError
from campus.models.authz import (
    AuthPermission,
    AuthRole,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)
from campus.models.course import Course
from campus.models.enrollment import Enrollment
from campus.models.enums import PermissionEffect, Role
from campus.models.school_class import SchoolClass
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.teaching import CourseTeacher
from campus.models.user import User
from campus.schemas.auth import NavGroup, NavItem


class Permission(StrEnum):
    """权限码：``资源:动作``。"""

    DASHBOARD_READ = "dashboard:read"

    STUDENT_READ = "student:read"
    STUDENT_SELF_READ = "student:self:read"
    STUDENT_READ_DETAIL = "student:read_detail"
    STUDENT_MANAGE = "student:manage"
    STUDENT_SENSITIVE_READ = "student:sensitive:read"

    TEACHER_READ = "teacher:read"
    TEACHER_READ_DETAIL = "teacher:read_detail"
    TEACHER_MANAGE = "teacher:manage"

    CLASS_READ = "class:read"
    CLASS_MANAGE = "class:manage"
    CLASS_SEAT_READ = "class:seat:read"
    CLASS_SEAT_MANAGE = "class:seat:manage"

    DEPARTMENT_READ = "department:read"
    DEPARTMENT_MANAGE = "department:manage"
    SUBJECT_READ = "subject:read"
    SUBJECT_MANAGE = "subject:manage"
    SEMESTER_READ = "semester:read"
    SEMESTER_MANAGE = "semester:manage"

    COURSE_READ = "course:read"
    COURSE_MANAGE = "course:manage"

    ENROLLMENT_READ = "enrollment:read"
    ENROLLMENT_MANAGE = "enrollment:manage"
    ENROLLMENT_SELF = "enrollment:self"

    SCORE_READ = "score:read"
    SCORE_WRITE = "score:write"
    SCORE_PUBLISH = "score:publish"
    SCORE_UNLOCK = "score:unlock"

    ATTENDANCE_READ = "attendance:read"
    ATTENDANCE_WRITE = "attendance:write"

    SCHEDULE_READ = "schedule:read"
    SCHEDULE_MANAGE = "schedule:manage"
    SCHEDULE_CHANGE = "schedule:change"

    DORM_READ = "dorm:read"
    DORM_MANAGE = "dorm:manage"
    DORM_SELF = "dorm:self"

    FEE_READ = "fee:read"
    FEE_MANAGE = "fee:manage"
    FEE_PAY = "fee:pay"

    LEAVE_APPLY = "leave:apply"
    LEAVE_READ = "leave:read"
    LEAVE_APPROVE = "leave:approve"

    CALENDAR_READ = "calendar:read"
    CALENDAR_MANAGE = "calendar:manage"
    CALENDAR_MANAGE_ALL = "calendar:manage_all"

    GROUP_READ = "group:read"
    GROUP_MANAGE = "group:manage"
    WORKFLOW_MANAGE = "workflow:manage"
    SETTING_MANAGE = "setting:manage"

    NOTIFICATION_READ = "notification:read"

    NOTICE_READ = "notice:read"
    NOTICE_MANAGE = "notice:manage"

    AUDIT_READ = "audit:read"
    ACCOUNT_MANAGE = "account:manage"
    ROLE_MANAGE = "role:manage"
    PERMISSION_MANAGE = "permission:manage"


PERMISSION_CATALOG: dict[Permission, tuple[str, str]] = {
    Permission.DASHBOARD_READ: ("查看仪表盘", "按角色返回仪表盘聚合数据"),
    Permission.STUDENT_READ: ("查看学生列表", "按数据范围查看学生档案"),
    Permission.STUDENT_SELF_READ: ("查看本人档案", "学生查看自己的档案与成绩单"),
    Permission.STUDENT_READ_DETAIL: ("查看学生详情", "查看权限范围内的学生完整档案"),
    Permission.STUDENT_MANAGE: ("管理学生", "新增、修改、停用学生"),
    Permission.STUDENT_SENSITIVE_READ: ("查看学生敏感信息", "查看身份证、住址、监护人"),
    Permission.TEACHER_READ: ("查看教师目录", "查看教师简版信息"),
    Permission.TEACHER_READ_DETAIL: ("查看教师详情", "查看教师完整档案"),
    Permission.TEACHER_MANAGE: ("管理教师", "新增、修改、停用教师"),
    Permission.CLASS_READ: ("查看班级", "查看权限范围内的班级"),
    Permission.CLASS_MANAGE: ("管理班级", "新增、修改、删除班级"),
    Permission.CLASS_SEAT_READ: ("查看座位表", "查看班级座位表"),
    Permission.CLASS_SEAT_MANAGE: ("调整座位", "调整班级座位"),
    Permission.DEPARTMENT_READ: ("查看院系", "查看院系与部门"),
    Permission.DEPARTMENT_MANAGE: ("管理院系", "新增、修改院系"),
    Permission.SUBJECT_READ: ("查看学科", "查看学科目录"),
    Permission.SUBJECT_MANAGE: ("管理学科", "新增、修改学科"),
    Permission.SEMESTER_READ: ("查看学期", "查看学期设置"),
    Permission.SEMESTER_MANAGE: ("管理学期", "新增、修改、切换学期"),
    Permission.COURSE_READ: ("查看课程", "查看课程目录"),
    Permission.COURSE_MANAGE: ("管理课程", "新增、修改、删除课程"),
    Permission.ENROLLMENT_READ: ("查看选课", "按数据范围查看选课记录"),
    Permission.ENROLLMENT_MANAGE: ("管理选课", "代学生选课与退课"),
    Permission.ENROLLMENT_SELF: ("本人选退课", "学生本人选课与退课"),
    Permission.SCORE_READ: ("查看成绩", "按数据范围查看成绩"),
    Permission.SCORE_WRITE: ("录入成绩", "录入或修改本人课程成绩"),
    Permission.SCORE_PUBLISH: ("发布成绩", "发布本人课程成绩"),
    Permission.SCORE_UNLOCK: ("解锁成绩", "解锁已发布成绩"),
    Permission.ATTENDANCE_READ: ("查看考勤", "按数据范围查看考勤"),
    Permission.ATTENDANCE_WRITE: ("登记考勤", "登记本人课程考勤"),
    Permission.SCHEDULE_READ: ("查看课表", "按数据范围查看课表"),
    Permission.SCHEDULE_MANAGE: ("排课", "维护本人课程课表"),
    Permission.SCHEDULE_CHANGE: ("调课", "申请或审批调课停课"),
    Permission.DORM_READ: ("查看宿舍", "按数据范围查看宿舍"),
    Permission.DORM_MANAGE: ("管理宿舍", "维护房间与床位分配"),
    Permission.DORM_SELF: ("查看本人床位", "学生查看本人宿舍床位"),
    Permission.FEE_READ: ("查看缴费", "按数据范围查看费用"),
    Permission.FEE_MANAGE: ("管理缴费", "创建费用项、减免与退费"),
    Permission.FEE_PAY: ("本人缴费", "学生支付本人费用"),
    Permission.LEAVE_APPLY: ("申请请假", "提交与撤销本人请假"),
    Permission.LEAVE_READ: ("查看请假", "查看本人或权限范围内的请假"),
    Permission.LEAVE_APPROVE: ("审批请假", "审批权限范围内的请假"),
    Permission.CALENDAR_READ: ("查看日程", "查看本人、班级、院系与全校日程"),
    Permission.CALENDAR_MANAGE: ("管理本人日程", "新建、修改、删除本人日程"),
    Permission.CALENDAR_MANAGE_ALL: ("管理全部日程", "管理全校日程与可见范围"),
    Permission.GROUP_READ: ("查看群组", "查看群组与成员"),
    Permission.GROUP_MANAGE: ("管理群组", "新建群组、维护成员"),
    Permission.WORKFLOW_MANAGE: ("管理审批流程", "配置请假审批流程与节点"),
    Permission.SETTING_MANAGE: ("管理系统参数", "维护节次时间与系统参数"),
    Permission.NOTIFICATION_READ: ("查看消息", "查看站内消息与未读数"),
    Permission.NOTICE_READ: ("查看通知", "查看通知公告"),
    Permission.NOTICE_MANAGE: ("发布通知", "发布与撤回通知"),
    Permission.AUDIT_READ: ("查看审计", "查看操作审计日志"),
    Permission.ACCOUNT_MANAGE: ("管理账号", "重置密码、启停用、绑定档案"),
    Permission.ROLE_MANAGE: ("管理角色", "配置角色与授权"),
    Permission.PERMISSION_MANAGE: ("管理权限点", "查看与维护权限点"),
}

ROLE_CATALOG: dict[str, tuple[str, str]] = {
    "admin": ("管理员", "拥有全部权限"),
    "teacher": ("教师", "任课教师与班主任"),
    "student": ("学生", "在校学生"),
    "student_affairs": ("学工处", "学生请假与学工事务审批"),
    "academic_director": ("教务主任", "教师请假与教学事务审批"),
}

_TEACHER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.DASHBOARD_READ,
        Permission.STUDENT_READ,
        Permission.STUDENT_READ_DETAIL,
        Permission.TEACHER_READ,
        Permission.TEACHER_READ_DETAIL,
        Permission.CLASS_READ,
        Permission.CLASS_SEAT_READ,
        Permission.CLASS_SEAT_MANAGE,
        Permission.DEPARTMENT_READ,
        Permission.SUBJECT_READ,
        Permission.SEMESTER_READ,
        Permission.COURSE_READ,
        Permission.ENROLLMENT_READ,
        Permission.SCORE_READ,
        Permission.SCORE_WRITE,
        Permission.SCORE_PUBLISH,
        Permission.ATTENDANCE_READ,
        Permission.ATTENDANCE_WRITE,
        Permission.SCHEDULE_READ,
        Permission.SCHEDULE_MANAGE,
        Permission.SCHEDULE_CHANGE,
        Permission.DORM_READ,
        Permission.FEE_READ,
        Permission.LEAVE_APPLY,
        Permission.LEAVE_READ,
        Permission.LEAVE_APPROVE,
        Permission.CALENDAR_READ,
        Permission.CALENDAR_MANAGE,
        Permission.GROUP_READ,
        Permission.NOTIFICATION_READ,
        Permission.NOTICE_READ,
        Permission.NOTICE_MANAGE,
    }
)

_STUDENT_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.DASHBOARD_READ,
        Permission.STUDENT_SELF_READ,
        Permission.TEACHER_READ,
        Permission.CLASS_READ,
        Permission.CLASS_SEAT_READ,
        Permission.COURSE_READ,
        Permission.ENROLLMENT_READ,
        Permission.ENROLLMENT_SELF,
        Permission.SCORE_READ,
        Permission.ATTENDANCE_READ,
        Permission.SCHEDULE_READ,
        Permission.DORM_SELF,
        Permission.FEE_READ,
        Permission.FEE_PAY,
        Permission.LEAVE_APPLY,
        Permission.LEAVE_READ,
        Permission.CALENDAR_READ,
        Permission.CALENDAR_MANAGE,
        Permission.NOTIFICATION_READ,
        Permission.NOTICE_READ,
    }
)

DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "admin": frozenset(Permission),
    "teacher": _TEACHER_PERMISSIONS,
    "student": _STUDENT_PERMISSIONS,
    "student_affairs": _TEACHER_PERMISSIONS | {Permission.LEAVE_APPROVE},
    "academic_director": _TEACHER_PERMISSIONS | {Permission.LEAVE_APPROVE},
}

_PERMISSION_VALUES = frozenset(item.value for item in Permission)


class ScopeKind(StrEnum):
    """数据范围类型。"""

    ALL = "all"
    DEPARTMENT = "department"
    CLASSES = "classes"
    SELF = "self"
    NONE = "none"


class FieldLevel(StrEnum):
    """字段可见级别。"""

    ADMIN = "admin"
    STAFF = "staff"
    SELF = "self"


@dataclass(frozen=True)
class DataScope:
    """一次请求的数据范围。"""

    kind: ScopeKind
    class_ids: frozenset[int] = frozenset()
    course_ids: frozenset[int] = frozenset()
    student_id: int | None = None
    department_id: int | None = None

    def allows_class(self, class_id: int | None) -> bool:
        if self.kind is ScopeKind.ALL:
            return True
        if class_id is None:
            return False
        return class_id in self.class_ids

    def allows_student(self, student: Student) -> bool:
        if self.kind is ScopeKind.ALL:
            return True
        if self.kind is ScopeKind.SELF:
            return student.id == self.student_id
        if self.kind is ScopeKind.CLASSES:
            return student.class_id in self.class_ids
        return False

    def allows_course(self, course_id: int) -> bool:
        if self.kind is ScopeKind.ALL:
            return True
        return course_id in self.course_ids


@dataclass(frozen=True)
class AccessContext:
    """请求级访问上下文：权限集合 + 数据范围 + 字段级别。"""

    user: User
    role: Role
    display_name: str
    role_codes: frozenset[str]
    permissions: frozenset[Permission]
    student_id: int | None
    teacher_id: int | None
    head_class_ids: frozenset[int]
    teaching_class_ids: frozenset[int]
    teaching_course_ids: frozenset[int]
    scope: DataScope
    field_level: FieldLevel

    def can(self, permission: Permission) -> bool:
        """是否拥有指定权限点。"""
        return permission in self.permissions

    def ensure(self, permission: Permission, message: str | None = None) -> None:
        """缺少权限点时抛出 403。"""
        if not self.can(permission):
            raise PermissionDeniedError(message or f"缺少权限：{permission.value}")

    def ensure_student(self, student: Student) -> None:
        """学生是否在数据范围内。"""
        if not self.scope.allows_student(student):
            raise PermissionDeniedError("只能访问权限范围内的学生")

    def ensure_class(self, class_id: int | None) -> None:
        """班级是否在数据范围内。"""
        if not self.scope.allows_class(class_id):
            raise PermissionDeniedError("只能访问权限范围内的班级")

    def ensure_course(self, course_id: int) -> None:
        """课程是否在数据范围内。"""
        if not self.scope.allows_course(course_id):
            raise PermissionDeniedError("只能访问权限范围内的课程")

    def ensure_course_write(self, course: Course) -> None:
        """管理员不限；教师仅限本人主讲或辅导的课程。"""
        if self.scope.kind is ScopeKind.ALL:
            return
        if course.id in self.teaching_course_ids:
            return
        if self.teacher_id is not None and course.teacher_id == self.teacher_id:
            return
        raise PermissionDeniedError("只能操作本人所授课程的数据")


async def _load_role_codes(session: AsyncSession, user: User) -> frozenset[str]:
    """主角色 + 数据库中附加角色。"""
    codes = {user.role.value}
    rows = await session.scalars(
        select(AuthRole.code)
        .join(UserRole, UserRole.role_id == AuthRole.id)
        .where(UserRole.user_id == user.id, AuthRole.is_active.is_(True))
    )
    codes.update(str(code) for code in rows.all())
    return frozenset(codes)


async def _load_permissions(
    session: AsyncSession, user_id: int, role_codes: frozenset[str]
) -> frozenset[Permission]:
    """角色权限并集 + 用户级 allow/deny；权限表为空时回退到内置默认值。"""
    rows = await session.execute(
        select(AuthPermission.code)
        .join(RolePermission, RolePermission.permission_id == AuthPermission.id)
        .join(AuthRole, AuthRole.id == RolePermission.role_id)
        .where(
            AuthRole.code.in_(role_codes),
            AuthRole.is_active.is_(True),
            AuthPermission.is_active.is_(True),
        )
    )
    codes = {str(row[0]) for row in rows.all()}
    if not codes:
        total = int(await session.scalar(select(func.count(AuthPermission.id))) or 0)
        if total == 0:
            for code in role_codes:
                codes.update(item.value for item in DEFAULT_ROLE_PERMISSIONS.get(code, frozenset()))

    overrides = await session.execute(
        select(AuthPermission.code, UserPermissionOverride.effect)
        .join(UserPermissionOverride, UserPermissionOverride.permission_id == AuthPermission.id)
        .where(UserPermissionOverride.user_id == user_id, AuthPermission.is_active.is_(True))
    )
    for code, effect in overrides.all():
        if effect is PermissionEffect.DENY:
            codes.discard(str(code))
        else:
            codes.add(str(code))
    return frozenset(Permission(code) for code in codes if code in _PERMISSION_VALUES)


async def _load_teacher_scope(
    session: AsyncSession, teacher_id: int
) -> tuple[frozenset[int], frozenset[int], frozenset[int]]:
    """班主任班级、任课课程与被任课课程覆盖的班级。"""
    head_ids = frozenset(
        int(item)
        for item in (
            await session.scalars(
                select(SchoolClass.id).where(SchoolClass.head_teacher_id == teacher_id)
            )
        ).all()
    )
    course_ids = {
        int(item)
        for item in (
            await session.scalars(select(Course.id).where(Course.teacher_id == teacher_id))
        ).all()
    }
    course_ids.update(
        int(item)
        for item in (
            await session.scalars(
                select(CourseTeacher.course_id).where(CourseTeacher.teacher_id == teacher_id)
            )
        ).all()
    )
    course_id_set = frozenset(course_ids)
    class_ids: set[int] = set(head_ids)
    if course_id_set:
        rows = await session.scalars(
            select(Student.class_id)
            .join(Enrollment, Enrollment.student_id == Student.id)
            .where(Enrollment.course_id.in_(course_id_set), Student.class_id.is_not(None))
            .distinct()
        )
        class_ids.update(int(item) for item in rows.all() if item is not None)
    return head_ids, frozenset(class_ids), course_id_set


async def build_access_context(session: AsyncSession, user: User) -> AccessContext:
    """构建请求级访问上下文（每个请求调用一次）。"""
    role_codes = await _load_role_codes(session, user)
    permissions = await _load_permissions(session, user.id, role_codes)

    student = await session.scalar(select(Student).where(Student.user_id == user.id))
    teacher = await session.scalar(select(Teacher).where(Teacher.user_id == user.id))

    student_id = student.id if student is not None else None
    teacher_id = teacher.id if teacher is not None else None

    head_ids: frozenset[int] = frozenset()
    teaching_class_ids: frozenset[int] = frozenset()
    teaching_course_ids: frozenset[int] = frozenset()

    if Role.ADMIN.value in role_codes:
        scope = DataScope(kind=ScopeKind.ALL)
        field_level = FieldLevel.ADMIN
    elif teacher_id is not None:
        head_ids, teaching_class_ids, teaching_course_ids = await _load_teacher_scope(
            session, teacher_id
        )
        scope = DataScope(
            kind=ScopeKind.CLASSES,
            class_ids=teaching_class_ids,
            course_ids=teaching_course_ids,
        )
        field_level = FieldLevel.STAFF
    elif student is not None:
        own_class_ids = (
            frozenset({student.class_id}) if student.class_id is not None else frozenset()
        )
        scope = DataScope(
            kind=ScopeKind.SELF,
            class_ids=own_class_ids,
            student_id=student.id,
        )
        field_level = FieldLevel.SELF
    else:
        scope = DataScope(kind=ScopeKind.NONE)
        field_level = FieldLevel.SELF

    return AccessContext(
        user=user,
        role=user.role,
        display_name=(
            student.name
            if student is not None
            else teacher.name
            if teacher is not None
            else user.username
        ),
        role_codes=role_codes,
        permissions=permissions,
        student_id=student_id,
        teacher_id=teacher_id,
        head_class_ids=head_ids,
        teaching_class_ids=teaching_class_ids,
        teaching_course_ids=teaching_course_ids,
        scope=scope,
        field_level=field_level,
    )


def nav_for(access: AccessContext) -> list[NavGroup]:
    """按权限点生成侧边栏导航。"""
    groups: list[NavGroup] = []
    for label, entries in NAV_DEFINITION:
        items = [
            NavItem(id=item_id, label=item_label, icon=icon_name)
            for item_id, item_label, icon_name, permission in entries
            if access.can(permission)
        ]
        if items:
            groups.append(NavGroup(label=label, items=items))
    return groups


NAV_DEFINITION: tuple[tuple[str, tuple[tuple[str, str, str, Permission], ...]], ...] = (
    (
        "总览",
        (
            ("dashboard", "仪表盘", "dashboard", Permission.DASHBOARD_READ),
            ("reports", "报表", "scores", Permission.DASHBOARD_READ),
        ),
    ),
    (
        "教务",
        (
            ("students", "学生", "students", Permission.STUDENT_READ),
            ("teachers", "教师", "teachers", Permission.TEACHER_READ),
            ("classes", "班级", "classes", Permission.CLASS_READ),
            ("courses", "课程", "courses", Permission.COURSE_READ),
            ("enrollments", "选课", "enrollments", Permission.ENROLLMENT_READ),
            ("scores", "成绩", "scores", Permission.SCORE_READ),
            ("attendance", "考勤", "attendance", Permission.ATTENDANCE_READ),
            ("schedules", "课表", "schedules", Permission.SCHEDULE_READ),
            ("leaves", "请假", "clock", Permission.LEAVE_READ),
        ),
    ),
    (
        "生活服务",
        (
            ("dorms", "宿舍", "dorms", Permission.DORM_READ),
            ("fees", "缴费", "fees", Permission.FEE_READ),
            ("notices", "通知", "bell", Permission.NOTICE_READ),
        ),
    ),
    (
        "协作",
        (
            ("calendar", "日程", "calendar", Permission.CALENDAR_READ),
            ("notifications", "消息", "bell", Permission.NOTIFICATION_READ),
        ),
    ),
    (
        "系统",
        (
            ("settings", "系统设置", "settings", Permission.ROLE_MANAGE),
            ("audit", "审计日志", "alert", Permission.AUDIT_READ),
        ),
    ),
)
