"""系统参数路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from campus.api.deps import SessionDep, require
from campus.schemas.setting import PeriodSlot, SettingRead, SettingUpdate
from campus.services.access import Permission
from campus.services.setting import SystemSettingService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingRead])
async def list_settings(
    session: SessionDep,
    _: None = Depends(require(Permission.SETTING_MANAGE)),
) -> list[SettingRead]:
    """系统参数列表。"""
    return await SystemSettingService(session).list_all()


@router.get("/periods", response_model=list[PeriodSlot])
async def period_times(
    session: SessionDep,
    _: None = Depends(require(Permission.SETTING_MANAGE)),
) -> list[dict[str, object]]:
    """节次时间。"""
    return await SystemSettingService(session).period_times()


@router.put("/{key}", response_model=SettingRead)
async def update_setting(
    key: str,
    payload: SettingUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.SETTING_MANAGE)),
) -> SettingRead:
    """更新系统参数。"""
    return await SystemSettingService(session).set(key, payload.value, payload.description)
