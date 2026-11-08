"""FastAPI 依赖：会话、当前用户、访问上下文与权限守卫。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.config import Settings, get_settings
from campus.core.exceptions import (
    PermissionDeniedError,
    TokenExpiredError,
    UnauthenticatedError,
)
from campus.core.security import decode_access_token
from campus.db.session import get_session
from campus.models.enums import Role
from campus.models.student import Student
from campus.models.user import User
from campus.repositories.people import StudentRepository
from campus.services.access import (
    AccessContext,
    Permission,
    build_access_context,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    """解析 Bearer 令牌并加载有效用户。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthenticatedError("缺少访问令牌")
    try:
        payload = decode_access_token(credentials.credentials, settings)
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("无效的访问令牌") from exc
    try:
        user_id = int(str(payload.get("sub")))
    except (TypeError, ValueError) as exc:
        raise UnauthenticatedError("无效的访问令牌") from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthenticatedError("账号不存在或已停用")
    request.state.current_user = user
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_access(user: CurrentUser, session: SessionDep) -> AccessContext:
    """构建当前请求的权限与数据范围上下文。"""
    return await build_access_context(session, user)


Access = Annotated[AccessContext, Depends(get_access)]


def require(permission: Permission) -> Callable[[AccessContext], Awaitable[AccessContext]]:
    """生成权限守卫依赖：缺少权限点返回 403。"""

    async def dependency(access: Access) -> AccessContext:
        access.ensure(permission)
        return access

    return dependency


async def require_admin(access: Access) -> AccessContext:
    """角色守卫：仅管理员（兼容旧依赖）。"""
    if access.role is not Role.ADMIN:
        raise PermissionDeniedError("仅管理员可执行该操作")
    return access


async def require_staff(access: Access) -> AccessContext:
    """角色守卫：管理员或教师（兼容旧依赖）。"""
    if access.role not in {Role.ADMIN, Role.TEACHER}:
        raise PermissionDeniedError("仅管理员或教师可执行该操作")
    return access


AdminUser = Annotated[AccessContext, Depends(require_admin)]
StaffUser = Annotated[AccessContext, Depends(require_staff)]


async def get_current_student(user: CurrentUser, session: SessionDep) -> Student:
    """当前学生账号对应的学生档案。"""
    if user.role is not Role.STUDENT:
        raise PermissionDeniedError("仅学生账号可访问该资源")
    student = await StudentRepository(session).get_by_user(user.id)
    if student is None:
        raise UnauthenticatedError("当前账号没有关联的学生档案")
    return student


CurrentStudent = Annotated[Student, Depends(get_current_student)]
