"""授权仓储：角色、权限点与用户授权查询。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.models.authz import (
    AuthPermission,
    AuthRole,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)
from campus.models.enums import PermissionEffect


class AuthzRepository:
    """权限相关查询与批量写入。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_roles(self) -> list[AuthRole]:
        rows = await self.session.scalars(select(AuthRole).order_by(AuthRole.id))
        return list(rows.all())

    async def list_permissions(self) -> list[AuthPermission]:
        rows = await self.session.scalars(
            select(AuthPermission).order_by(AuthPermission.resource, AuthPermission.action)
        )
        return list(rows.all())

    async def get_role(self, role_id: int) -> AuthRole | None:
        return await self.session.get(AuthRole, role_id)

    async def get_role_by_code(self, code: str) -> AuthRole | None:
        return await self.session.scalar(select(AuthRole).where(AuthRole.code == code))

    async def get_permission_by_code(self, code: str) -> AuthPermission | None:
        return await self.session.scalar(select(AuthPermission).where(AuthPermission.code == code))

    async def permission_codes_for_role(self, role_id: int) -> list[str]:
        rows = await self.session.scalars(
            select(AuthPermission.code)
            .join(RolePermission, RolePermission.permission_id == AuthPermission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(AuthPermission.resource, AuthPermission.action)
        )
        return [str(code) for code in rows.all()]

    async def role_permission_map(self) -> dict[int, list[str]]:
        """一次查询返回所有角色的权限码，避免逐角色查询。"""
        rows = await self.session.execute(
            select(RolePermission.role_id, AuthPermission.code)
            .join(AuthPermission, AuthPermission.id == RolePermission.permission_id)
            .order_by(AuthPermission.resource, AuthPermission.action)
        )
        result: dict[int, list[str]] = {}
        for role_id, code in rows.all():
            result.setdefault(int(role_id), []).append(str(code))
        return result

    async def role_codes_for_user(self, user_id: int) -> list[str]:
        rows = await self.session.scalars(
            select(AuthRole.code)
            .join(UserRole, UserRole.role_id == AuthRole.id)
            .where(UserRole.user_id == user_id)
            .order_by(AuthRole.id)
        )
        return [str(code) for code in rows.all()]

    async def overrides_for_user(self, user_id: int) -> list[tuple[str, PermissionEffect]]:
        rows = await self.session.execute(
            select(AuthPermission.code, UserPermissionOverride.effect)
            .join(UserPermissionOverride, UserPermissionOverride.permission_id == AuthPermission.id)
            .where(UserPermissionOverride.user_id == user_id)
            .order_by(AuthPermission.code)
        )
        return [(str(code), effect) for code, effect in rows.all()]

    async def replace_role_permissions(self, role_id: int, permission_ids: list[int]) -> None:
        await self.session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for permission_id in permission_ids:
            self.session.add(RolePermission(role_id=role_id, permission_id=permission_id))
        await self.session.flush()

    async def replace_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        await self.session.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for role_id in role_ids:
            self.session.add(UserRole(user_id=user_id, role_id=role_id))
        await self.session.flush()

    async def replace_user_overrides(
        self, user_id: int, items: list[tuple[int, PermissionEffect]]
    ) -> None:
        await self.session.execute(
            delete(UserPermissionOverride).where(UserPermissionOverride.user_id == user_id)
        )
        for permission_id, effect in items:
            self.session.add(
                UserPermissionOverride(user_id=user_id, permission_id=permission_id, effect=effect)
            )
        await self.session.flush()
