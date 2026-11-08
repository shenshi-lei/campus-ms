"""通知服务。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import NotFoundError, PermissionDeniedError
from campus.core.pagination import PageParams
from campus.db.base import utc_now
from campus.models.enums import NoticeAudience
from campus.models.notice import Notice
from campus.repositories.notice import NoticeRepository
from campus.schemas.common import Message, Page
from campus.schemas.notice import NoticeCreate, NoticeRead, NoticeUpdate
from campus.services.access import AccessContext, Permission
from campus.services.group import GroupService


class NoticeService:
    """通知公告的发布与阅读。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = NoticeRepository(session)
        self.groups = GroupService(session)

    async def list_notices(
        self, *, access: AccessContext, page: int, page_size: int
    ) -> Page[NoticeRead]:
        access.ensure(Permission.NOTICE_READ)
        params = PageParams(page=page, page_size=page_size)
        group_ids = frozenset(await self.groups.group_ids_for_user(access.user.id))
        rows, total = await self.repository.paginated_visible(
            role_codes=access.role_codes,
            class_ids=access.scope.class_ids,
            group_ids=group_ids,
            now=utc_now(),
            page=params.page,
            page_size=params.page_size,
        )
        return Page[NoticeRead](
            items=[NoticeRead.model_validate(item) for item in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create_notice(self, payload: NoticeCreate, access: AccessContext) -> NoticeRead:
        access.ensure(Permission.NOTICE_MANAGE)
        self._ensure_publish_scope(access, payload.audience, payload.class_id, payload.group_id)
        entity = Notice(
            title=payload.title,
            content=payload.content,
            audience=payload.audience,
            class_id=payload.class_id,
            group_id=payload.group_id,
            publisher_id=access.user.id,
            published_at=utc_now(),
            is_pinned=payload.is_pinned,
            expires_at=payload.expires_at,
        )
        await self.repository.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return NoticeRead.model_validate(entity)

    async def update_notice(
        self, notice_id: int, payload: NoticeUpdate, access: AccessContext
    ) -> NoticeRead:
        access.ensure(Permission.NOTICE_MANAGE)
        entity = await self._require(notice_id)
        self._ensure_edit(access, entity)
        changes = payload.model_dump(exclude_unset=True)
        if "audience" in changes or "class_id" in changes or "group_id" in changes:
            self._ensure_publish_scope(
                access,
                changes.get("audience", entity.audience),
                changes.get("class_id", entity.class_id),
                changes.get("group_id", entity.group_id),
            )
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.commit()
        await self.session.refresh(entity)
        return NoticeRead.model_validate(entity)

    async def delete_notice(self, notice_id: int, access: AccessContext) -> Message:
        access.ensure(Permission.NOTICE_MANAGE)
        entity = await self._require(notice_id)
        self._ensure_edit(access, entity)
        await self.repository.delete(entity)
        await self.session.commit()
        return Message(message="通知已删除")

    @staticmethod
    def _ensure_publish_scope(
        access: AccessContext,
        audience: NoticeAudience,
        class_id: int | None,
        group_id: int | None,
    ) -> None:
        if "admin" in access.role_codes:
            if audience is NoticeAudience.GROUP and group_id is None:
                raise PermissionDeniedError("群组通知必须选择群组")
            return
        if audience is NoticeAudience.GROUP:
            raise PermissionDeniedError("只有管理员可以发布群组通知")
        if audience is not NoticeAudience.CLASS:
            raise PermissionDeniedError("教师只能发布班级通知")
        if class_id is None or class_id not in access.head_class_ids:
            raise PermissionDeniedError("只能发布本人担任班主任的班级通知")

    @staticmethod
    def _ensure_edit(access: AccessContext, notice: Notice) -> None:
        if "admin" in access.role_codes:
            return
        if (
            notice.class_id is not None
            and notice.class_id in access.head_class_ids
            and notice.publisher_id == access.user.id
        ):
            return
        raise PermissionDeniedError("只能维护本人发布的班级通知")

    async def _require(self, notice_id: int) -> Notice:
        entity = await self.repository.get(notice_id)
        if entity is None:
            raise NotFoundError("通知不存在")
        return entity
