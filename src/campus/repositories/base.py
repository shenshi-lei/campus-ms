"""数据访问基类：只做查询与持久化，不做业务判断。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """通用 CRUD；子类通过 ``model`` 绑定实体。"""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: int) -> ModelT | None:
        """按主键读取，未命中返回 ``None``。"""
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """持久化并 flush（事务由 service 提交）。"""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """删除并 flush。"""
        await self.session.delete(entity)
        await self.session.flush()

    async def count(self, statement: Select[Any]) -> int:
        """统计查询结果行数。"""
        total = await self.session.scalar(select(func.count()).select_from(statement.subquery()))
        return int(total or 0)

    async def paginate(
        self, statement: Select[Any], page: int, page_size: int
    ) -> tuple[list[Any], int]:
        """执行分页查询，返回 ``(行列表, 总数)``。"""
        total = await self.count(statement)
        window = statement.offset((page - 1) * page_size).limit(page_size)
        rows = await self.session.scalars(window)
        return list(rows.all()), total
