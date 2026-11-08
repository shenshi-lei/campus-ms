"""认证服务：登录与改密。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.config import Settings
from campus.core.exceptions import (
    PermissionDeniedError,
    UnauthenticatedError,
)
from campus.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from campus.models.user import User
from campus.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UserRead


class AuthService:
    """账号认证。"""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def login(self, payload: LoginRequest) -> TokenResponse:
        """校验账号密码并签发令牌。"""
        user = await self.session.scalar(select(User).where(User.username == payload.username))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise UnauthenticatedError("用户名或密码错误")
        if not user.is_active:
            raise PermissionDeniedError("账号已停用")
        token = create_access_token(user.id, user.role.value, self.settings)
        return TokenResponse(
            access_token=token,
            expires_in=self.settings.access_token_expire_minutes * 60,
            user=UserRead.model_validate(user),
        )

    async def change_password(self, user: User, payload: ChangePasswordRequest) -> None:
        """校验旧密码后更新为新密码。"""
        if not verify_password(payload.old_password, user.password_hash):
            raise UnauthenticatedError("原密码不正确")
        if payload.old_password == payload.new_password:
            raise PermissionDeniedError("新密码不能与原密码相同")
        user.password_hash = hash_password(payload.new_password)
        await self.session.commit()
