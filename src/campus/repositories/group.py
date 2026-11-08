"""群组仓储。"""

from __future__ import annotations

from sqlalchemy import Select, and_, func, or_, select

from campus.models.enums import GroupMemberType
from campus.models.group import UserGroup, UserGroupMember
from campus.repositories.base import BaseRepository


class UserGroupRepository(BaseRepository[UserGroup]):
    """群组查询。"""

    model = UserGroup

    def filtered(self, keyword: str | None = None) -> Select[UserGroup]:
        statement = select(UserGroup).order_by(UserGroup.name)
        if keyword:
            like = f"%{keyword}%"
            statement = statement.where(UserGroup.name.like(like) | UserGroup.code.like(like))
        return statement

    async def list_all(self, keyword: str | None = None) -> list[UserGroup]:
        rows = await self.session.scalars(self.filtered(keyword))
        return list(rows.all())

    async def get_by_code(self, code: str) -> UserGroup | None:
        return await self.session.scalar(select(UserGroup).where(UserGroup.code == code))

    async def member_counts(self) -> dict[int, int]:
        rows = await self.session.execute(
            select(UserGroupMember.group_id, func.count(UserGroupMember.id)).group_by(
                UserGroupMember.group_id
            )
        )
        return {int(group_id): int(count) for group_id, count in rows.all()}

    async def members(self, group_id: int) -> list[UserGroupMember]:
        rows = await self.session.scalars(
            select(UserGroupMember)
            .where(UserGroupMember.group_id == group_id)
            .order_by(UserGroupMember.member_type, UserGroupMember.display_name)
        )
        return list(rows.all())

    async def members_for_groups(self, group_ids: list[int]) -> dict[int, list[UserGroupMember]]:
        if not group_ids:
            return {}
        rows = await self.session.scalars(
            select(UserGroupMember).where(UserGroupMember.group_id.in_(group_ids))
        )
        result: dict[int, list[UserGroupMember]] = {}
        for item in rows.all():
            result.setdefault(item.group_id, []).append(item)
        return result

    async def groups_for_user(self, user_id: int) -> list[UserGroup]:
        rows = await self.session.scalars(
            select(UserGroup)
            .join(UserGroupMember, UserGroupMember.group_id == UserGroup.id)
            .where(
                UserGroup.is_active.is_(True),
                or_(
                    UserGroupMember.user_id == user_id,
                    and_(
                        UserGroupMember.member_type == GroupMemberType.USER,
                        UserGroupMember.member_id == user_id,
                    ),
                ),
            )
            .distinct()
        )
        return list(rows.all())
