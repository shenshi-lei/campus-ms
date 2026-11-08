"""账号服务：列表、启停用与重置密码。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import ConflictError, NotFoundError
from campus.core.pagination import PageParams
from campus.core.security import hash_password
from campus.models.user import User
from campus.repositories.accounts import AccountRepository
from campus.schemas.account import AccountRead
from campus.schemas.common import Message, Page
from campus.services.access import AccessContext, Permission


class AccountService:
    """管理员账号管理。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AccountRepository(session)

    async def list_accounts(
        self,
        *,
        access: AccessContext,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> Page[AccountRead]:
        access.ensure(Permission.ACCOUNT_MANAGE)
        params = PageParams(page=page, page_size=page_size)
        rows, total = await self.repository.paginated_rows(
            keyword=keyword, page=params.page, page_size=params.page_size
        )
        return Page[AccountRead](
            items=[
                AccountRead(
                    id=user.id,
                    username=user.username,
                    role=user.role,
                    is_active=user.is_active,
                    display_name=student_name or teacher_name or user.username,
                    created_at=user.created_at,
                )
                for user, student_name, teacher_name in rows
            ],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def set_active(self, account_id: int, active: bool, access: AccessContext) -> AccountRead:
        access.ensure(Permission.ACCOUNT_MANAGE)
        if account_id == access.user.id and not active:
            raise ConflictError("不能停用当前登录账号")
        user = await self._require(account_id)
        user.is_active = active
        await self.session.commit()
        return await self._read(user)

    async def reset_password(
        self, account_id: int, new_password: str, access: AccessContext
    ) -> Message:
        access.ensure(Permission.ACCOUNT_MANAGE)
        user = await self._require(account_id)
        user.password_hash = hash_password(new_password)
        await self.session.commit()
        return Message(message=f"已重置 {user.username} 的密码")

    async def _read(self, user: User) -> AccountRead:
        row = await self.repository.get_with_names(user.id)
        display = user.username
        if row is not None:
            display = row[1] or row[2] or user.username
        return AccountRead(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            display_name=display,
            created_at=user.created_at,
        )

    async def _require(self, account_id: int) -> User:
        user = await self.repository.get(account_id)
        if user is None:
            raise NotFoundError("账号不存在")
        return user
