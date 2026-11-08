"""系统参数服务：节次时间与键值配置。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import NotFoundError
from campus.models.setting import SystemSetting
from campus.repositories.setting import SystemSettingRepository
from campus.schemas.setting import SettingRead

DEFAULT_PERIOD_TIMES: list[dict[str, Any]] = [
    {"no": 1, "start": "08:00", "end": "08:45"},
    {"no": 2, "start": "08:55", "end": "09:40"},
    {"no": 3, "start": "10:00", "end": "10:45"},
    {"no": 4, "start": "10:55", "end": "11:40"},
    {"no": 5, "start": "14:00", "end": "14:45"},
    {"no": 6, "start": "14:55", "end": "15:40"},
    {"no": 7, "start": "16:00", "end": "16:45"},
    {"no": 8, "start": "16:55", "end": "17:40"},
]
PERIOD_TIMES_KEY = "period_times"


class SystemSettingService:
    """键值配置读写。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SystemSettingRepository(session)

    async def ensure_defaults(self) -> None:
        """幂等写入默认参数。"""
        existing = await self.repository.get_by_key(PERIOD_TIMES_KEY)
        if existing is None:
            self.session.add(
                SystemSetting(
                    key=PERIOD_TIMES_KEY,
                    value=json.dumps(DEFAULT_PERIOD_TIMES, ensure_ascii=False),
                    description="节次时间，用于课表日/周视图",
                )
            )
            await self.session.commit()

    async def list_all(self) -> list[SettingRead]:
        rows = await self.repository.list_all()
        return [
            SettingRead(key=item.key, value=item.value, description=item.description)
            for item in rows
        ]

    async def get(self, key: str) -> SettingRead:
        row = await self.repository.get_by_key(key)
        if row is None:
            raise NotFoundError("系统参数不存在")
        return SettingRead(key=row.key, value=row.value, description=row.description)

    async def set(self, key: str, value: str, description: str | None = None) -> SettingRead:
        row = await self.repository.get_by_key(key)
        if row is None:
            row = SystemSetting(key=key, value=value, description=description or "")
            self.session.add(row)
        else:
            row.value = value
            if description is not None:
                row.description = description
        await self.session.commit()
        return SettingRead(key=row.key, value=row.value, description=row.description)

    async def period_times(self) -> list[dict[str, Any]]:
        row = await self.repository.get_by_key(PERIOD_TIMES_KEY)
        if row is None:
            return list(DEFAULT_PERIOD_TIMES)
        try:
            data = json.loads(row.value)
        except (TypeError, ValueError):
            return list(DEFAULT_PERIOD_TIMES)
        if not isinstance(data, list):
            return list(DEFAULT_PERIOD_TIMES)
        slots: list[dict[str, Any]] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            no = int(item.get("no", index))
            slots.append(
                {
                    "no": no,
                    "start": str(item.get("start", "08:00")),
                    "end": str(item.get("end", "08:45")),
                }
            )
        return slots or list(DEFAULT_PERIOD_TIMES)
