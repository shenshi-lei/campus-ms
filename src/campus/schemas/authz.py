"""权限管理契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from campus.models.enums import PermissionEffect


class PermissionRead(BaseModel):
    """权限点输出。"""

    id: int
    code: str
    resource: str
    action: str
    name: str
    description: str
    is_active: bool


class RoleRead(BaseModel):
    """角色输出，含已授予的权限码。"""

    id: int
    code: str
    name: str
    description: str
    is_system: bool
    is_active: bool
    permissions: list[str] = Field(default_factory=list)


class RolePermissionsUpdate(BaseModel):
    """整体替换角色的权限集合。"""

    permissions: list[str] = Field(default_factory=list)


class UserOverrideRead(BaseModel):
    """用户级权限覆盖项。"""

    code: str
    effect: PermissionEffect


class UserGrantsRead(BaseModel):
    """用户的角色与覆盖项。"""

    user_id: int
    username: str
    roles: list[str] = Field(default_factory=list)
    overrides: list[UserOverrideRead] = Field(default_factory=list)


class UserRolesUpdate(BaseModel):
    """整体替换用户的角色集合。"""

    roles: list[str] = Field(default_factory=list)


class UserOverridesUpdate(BaseModel):
    """整体替换用户的权限覆盖项。"""

    items: list[UserOverrideRead] = Field(default_factory=list)
