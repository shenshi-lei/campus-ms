"""系统参数仓储。"""

from __future__ import annotations

from sqlalchemy import select

from campus.models.setting import SystemSetting
from campus.repositories.base import BaseRepository


class SystemSettingRepository(BaseRepository[SystemSetting]):
    """键值配置查询。"""

    model = SystemSetting

    async def get_by_key(self, key: str) -> SystemSetting | None:
        return await self.session.scalar(select(SystemSetting).where(SystemSetting.key == key))

    async def list_all(self) -> list[SystemSetting]:
        rows = await self.session.scalars(select(SystemSetting).order_by(SystemSetting.key))
        return list(rows.all())
