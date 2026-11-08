"""认证相关契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from campus.models.enums import Role
from campus.schemas.common import ORMModel


class LoginRequest(BaseModel):
    """登录入参。"""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class UserRead(ORMModel):
    """用户公开信息，绝不包含密码哈希。"""

    id: int
    username: str
    role: Role
    is_active: bool


class NavItem(BaseModel):
    """导航项。"""

    id: str
    label: str
    icon: str


class NavGroup(BaseModel):
    """导航分组。"""

    label: str
    items: list[NavItem] = Field(default_factory=list)


class ScopeInfo(BaseModel):
    """前端可见的数据范围摘要。"""

    student_id: int | None = None
    teacher_id: int | None = None
    class_ids: list[int] = Field(default_factory=list)
    course_ids: list[int] = Field(default_factory=list)


class MeRead(UserRead):
    """当前登录用户：账号信息 + 权限 + 导航 + 数据范围。"""

    display_name: str
    permissions: list[str] = Field(default_factory=list)
    nav: list[NavGroup] = Field(default_factory=list)
    scope: ScopeInfo


class TokenResponse(BaseModel):
    """登录成功响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class ChangePasswordRequest(BaseModel):
    """修改密码入参。"""

    old_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
