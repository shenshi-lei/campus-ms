"""异步引擎与会话工厂，附带 SQLite PRAGMA 设置。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from campus.core.config import get_settings


def _install_sqlite_pragmas(engine: AsyncEngine) -> None:
    """为 SQLite 连接开启外键、WAL 与忙等待。"""

    @event.listens_for(engine.sync_engine, "connect")
    def _apply_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


def build_engine(database_url: str) -> AsyncEngine:
    """根据连接串创建异步引擎（测试与生产共用）。"""
    engine = create_async_engine(database_url, pool_pre_ping=True)
    if database_url.startswith("sqlite"):
        _install_sqlite_pragmas(engine)
    return engine


engine: AsyncEngine = build_engine(get_settings().database_url)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求一个会话，退出时自动关闭。"""
    async with SessionFactory() as session:
        yield session
