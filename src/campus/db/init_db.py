"""建表：应用启动与测试夹具共用。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

import campus.models  # noqa: F401  确保所有模型注册到 Base.metadata
from campus.db.base import Base


async def create_schema(engine: AsyncEngine) -> None:
    """按 ORM 元数据创建缺失的表。"""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def init_db(engine: AsyncEngine) -> None:
    """应用启动时的数据库初始化。"""
    await create_schema(engine)
