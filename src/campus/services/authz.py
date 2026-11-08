"""权限管理服务：默认授权同步与角色/用户授权配置。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import NotFoundError
from campus.models.authz import AuthPermission, AuthRole, RolePermission, UserRole
from campus.models.enums import PermissionEffect
from campus.models.user import User
from campus.repositories.authz import AuthzRepository
from campus.schemas.authz import (
    PermissionRead,
    RoleRead,
    UserGrantsRead,
    UserOverrideRead,
)
from campus.services.access import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_CATALOG,
    ROLE_CATALOG,
)


class AuthzService:
    """角色与权限配置。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AuthzRepository(session)

    async def sync_defaults(self) -> None:
        """幂等同步权限点、内置角色、默认授权与用户主角色。"""
        permissions = {item.code: item for item in await self.repository.list_permissions()}
        for permission, (name, description) in PERMISSION_CATALOG.items():
            resource, _, action = permission.value.partition(":")
            entity = permissions.get(permission.value)
            if entity is None:
                entity = AuthPermission(
                    code=permission.value,
                    resource=resource,
                    action=action,
                    name=name,
                    description=description,
                )
                self.session.add(entity)
                permissions[permission.value] = entity
            else:
                entity.name = name
                entity.description = description
                entity.resource = resource
                entity.action = action
        await self.session.flush()

        roles = {item.code: item for item in await self.repository.list_roles()}
        created_roles: set[str] = set()
        for code, (name, description) in ROLE_CATALOG.items():
            role = roles.get(code)
            if role is None:
                role = AuthRole(
                    code=code,
                    name=name,
                    description=description,
                    is_system=True,
                )
                self.session.add(role)
                roles[code] = role
                created_roles.add(code)
        await self.session.flush()

        for code in created_roles:
            for permission in DEFAULT_ROLE_PERMISSIONS.get(code, frozenset()):
                entity = permissions.get(permission.value)
                if entity is not None:
                    self.session.add(
                        RolePermission(role_id=roles[code].id, permission_id=entity.id)
                    )
        await self.session.flush()

        await self._ensure_primary_roles(roles)
        await self.session.commit()

    async def _ensure_primary_roles(self, roles: dict[str, AuthRole]) -> None:
        """保证每个账号的主角色在 user_roles 中存在。"""
        pairs = {
            (int(user_id), int(role_id))
            for user_id, role_id in (
                await self.session.execute(select(UserRole.user_id, UserRole.role_id))
            ).all()
        }
        users = await self.session.scalars(select(User))
        for user in users.all():
            role = roles.get(user.role.value)
            if role is None:
                continue
            if (user.id, role.id) not in pairs:
                self.session.add(UserRole(user_id=user.id, role_id=role.id))
        await self.session.flush()

    async def list_roles(self) -> list[RoleRead]:
        """列出全部角色及其权限码。"""
        roles = await self.repository.list_roles()
        permission_map = await self.repository.role_permission_map()
        return [
            RoleRead(
                id=role.id,
                code=role.code,
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                is_active=role.is_active,
                permissions=permission_map.get(role.id, []),
            )
            for role in roles
        ]

    async def list_permissions(self) -> list[PermissionRead]:
        """列出全部权限点。"""
        return [
            PermissionRead(
                id=item.id,
                code=item.code,
                resource=item.resource,
                action=item.action,
                name=item.name,
                description=item.description,
                is_active=item.is_active,
            )
            for item in await self.repository.list_permissions()
        ]

    async def set_role_permissions(self, role_id: int, codes: list[str]) -> RoleRead:
        """整体替换角色权限。"""
        role = await self.repository.get_role(role_id)
        if role is None:
            raise NotFoundError("角色不存在")
        permission_ids: list[int] = []
        for code in dict.fromkeys(codes):
            permission = await self.repository.get_permission_by_code(code)
            if permission is None:
                raise NotFoundError(f"权限点不存在：{code}")
            permission_ids.append(permission.id)
        await self.repository.replace_role_permissions(role.id, permission_ids)
        await self.session.commit()
        return RoleRead(
            id=role.id,
            code=role.code,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            is_active=role.is_active,
            permissions=await self.repository.permission_codes_for_role(role.id),
        )

    async def get_user_grants(self, user_id: int) -> UserGrantsRead:
        """查看用户的角色与覆盖项。"""
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("账号不存在")
        return UserGrantsRead(
            user_id=user.id,
            username=user.username,
            roles=await self.repository.role_codes_for_user(user.id),
            overrides=[
                UserOverrideRead(code=code, effect=effect)
                for code, effect in await self.repository.overrides_for_user(user.id)
            ],
        )

    async def set_user_roles(self, user_id: int, codes: list[str]) -> UserGrantsRead:
        """整体替换用户角色。"""
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("账号不存在")
        role_ids: list[int] = []
        for code in dict.fromkeys(codes):
            role = await self.repository.get_role_by_code(code)
            if role is None:
                raise NotFoundError(f"角色不存在：{code}")
            role_ids.append(role.id)
        await self.repository.replace_user_roles(user.id, role_ids)
        await self.session.commit()
        return await self.get_user_grants(user.id)

    async def set_user_overrides(
        self, user_id: int, items: list[tuple[str, PermissionEffect]]
    ) -> UserGrantsRead:
        """整体替换用户级权限覆盖。"""
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("账号不存在")
        pairs: list[tuple[int, PermissionEffect]] = []
        for code, effect in items:
            permission = await self.repository.get_permission_by_code(code)
            if permission is None:
                raise NotFoundError(f"权限点不存在：{code}")
            pairs.append((permission.id, effect))
        await self.repository.replace_user_overrides(user.id, pairs)
        await self.session.commit()
        return await self.get_user_grants(user.id)
