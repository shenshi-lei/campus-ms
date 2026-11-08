"""权限判定：集中管理角色与数据归属。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import NotFoundError, PermissionDeniedError
from campus.models.enums import Role
from campus.models.user import User
from campus.repositories.people import StudentRepository, TeacherRepository


def ensure_admin(user: User) -> None:
    """仅管理员可通过。"""
    if user.role is not Role.ADMIN:
        raise PermissionDeniedError("仅管理员可执行该操作")


def ensure_staff(user: User) -> None:
    """管理员或教师可通过。"""
    if user.role not in {Role.ADMIN, Role.TEACHER}:
        raise PermissionDeniedError("仅管理员或教师可执行该操作")


def ensure_can_write_course(
    user: User,
    *,
    course_teacher_id: int | None,
    user_teacher_id: int | None,
) -> None:
    """管理员放行；教师仅限本人所授课程。"""
    if user.role is Role.ADMIN:
        return
    if (
        user.role is Role.TEACHER
        and course_teacher_id is not None
        and course_teacher_id == user_teacher_id
    ):
        return
    raise PermissionDeniedError("只能操作本人所授课程的数据")


async def current_teacher_id(session: AsyncSession, user: User) -> int | None:
    """返回当前用户对应的教师 ID（非教师返回 None）。"""
    teacher = await TeacherRepository(session).get_by_user(user.id)
    return teacher.id if teacher is not None else None


async def current_student_id(session: AsyncSession, user: User) -> int:
    """返回当前学生用户的学生 ID。"""
    student = await StudentRepository(session).get_by_user(user.id)
    if student is None:
        raise NotFoundError("当前账号没有关联的学生档案")
    return student.id


async def ensure_owns_student(session: AsyncSession, user: User, student_id: int) -> None:
    """学生只能访问自己的数据；管理员与教师不限制。"""
    if user.role is not Role.STUDENT:
        return
    own_id = await current_student_id(session, user)
    if own_id != student_id:
        raise PermissionDeniedError("只能访问本人数据")
