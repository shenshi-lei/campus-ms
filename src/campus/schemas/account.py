"""账号管理契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from campus.models.enums import Role


class AccountRead(BaseModel):
    """账号输出。"""

    id: int
    username: str
    role: Role
    is_active: bool
    display_name: str
    created_at: datetime


class AccountUpdate(BaseModel):
    """启停用账号。"""

    is_active: bool


class ResetPasswordRequest(BaseModel):
    """管理员重置密码。"""

    new_password: str = Field(min_length=8, max_length=128)
