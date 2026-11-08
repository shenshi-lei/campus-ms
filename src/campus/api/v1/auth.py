"""认证路由。"""

from __future__ import annotations

from fastapi import APIRouter

from campus.api.deps import Access, CurrentUser, SessionDep, SettingsDep
from campus.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeRead,
    ScopeInfo,
    TokenResponse,
)
from campus.schemas.common import Message
from campus.services.access import nav_for
from campus.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    """用户名密码登录，返回 JWT。"""
    return await AuthService(session, settings).login(payload)


@router.get("/me", response_model=MeRead)
async def read_me(access: Access) -> MeRead:
    """返回当前登录用户、权限点、导航与数据范围。"""
    return MeRead(
        id=access.user.id,
        username=access.user.username,
        role=access.user.role,
        is_active=access.user.is_active,
        display_name=access.display_name,
        permissions=sorted(item.value for item in access.permissions),
        nav=nav_for(access),
        scope=ScopeInfo(
            student_id=access.student_id,
            teacher_id=access.teacher_id,
            class_ids=sorted(access.scope.class_ids),
            course_ids=sorted(access.teaching_course_ids),
        ),
    )


@router.post("/change-password", response_model=Message)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> Message:
    """修改当前账号密码。"""
    await AuthService(session, settings).change_password(user, payload)
    return Message(message="密码已更新")
