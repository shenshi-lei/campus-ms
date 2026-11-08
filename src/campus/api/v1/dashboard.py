"""仪表盘路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.dashboard import DashboardOverview, DashboardSummary
from campus.services.access import Permission
from campus.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def read_summary(
    session: SessionDep,
    _: None = Depends(require(Permission.DASHBOARD_READ)),
) -> DashboardSummary:
    """首页关键指标（兼容旧接口）。"""
    return await DashboardService(session).summary()


@router.get("/overview", response_model=DashboardOverview)
async def read_overview(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.DASHBOARD_READ)),
    days: int = Query(30, ge=7, le=90),
) -> DashboardOverview:
    """按角色返回仪表盘聚合数据。"""
    return await DashboardService(session).overview(access, days=days)
