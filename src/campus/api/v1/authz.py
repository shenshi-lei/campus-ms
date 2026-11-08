"""权限管理路由：角色、权限点与用户授权配置。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from campus.api.deps import SessionDep, require
from campus.schemas.authz import (
    PermissionRead,
    RolePermissionsUpdate,
    RoleRead,
    UserGrantsRead,
    UserOverridesUpdate,
    UserRolesUpdate,
)
from campus.services.access import Permission
from campus.services.authz import AuthzService

router = APIRouter(prefix="/authz", tags=["authz"])


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    session: SessionDep,
    _: None = Depends(require(Permission.ROLE_MANAGE)),
) -> list[RoleRead]:
    """角色及其权限集合（管理员）。"""
    return await AuthzService(session).list_roles()


@router.put("/roles/{role_id}/permissions", response_model=RoleRead)
async def set_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.ROLE_MANAGE)),
) -> RoleRead:
    """整体替换角色权限（管理员）。"""
    return await AuthzService(session).set_role_permissions(role_id, payload.permissions)


@router.get("/permissions", response_model=list[PermissionRead])
async def list_permissions(
    session: SessionDep,
    _: None = Depends(require(Permission.ROLE_MANAGE)),
) -> list[PermissionRead]:
    """权限点目录（管理员）。"""
    return await AuthzService(session).list_permissions()


@router.get("/users/{user_id}/roles", response_model=UserGrantsRead)
async def read_user_grants(
    user_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.ROLE_MANAGE)),
) -> UserGrantsRead:
    """查看用户的角色与覆盖项（管理员）。"""
    return await AuthzService(session).get_user_grants(user_id)


@router.put("/users/{user_id}/roles", response_model=UserGrantsRead)
async def set_user_roles(
    user_id: int,
    payload: UserRolesUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.ROLE_MANAGE)),
) -> UserGrantsRead:
    """整体替换用户角色（管理员）。"""
    return await AuthzService(session).set_user_roles(user_id, payload.roles)


@router.put("/users/{user_id}/permissions", response_model=UserGrantsRead)
async def set_user_overrides(
    user_id: int,
    payload: UserOverridesUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.ROLE_MANAGE)),
) -> UserGrantsRead:
    """整体替换用户级权限覆盖（管理员）。"""
    items = [(item.code, item.effect) for item in payload.items]
    return await AuthzService(session).set_user_overrides(user_id, items)
