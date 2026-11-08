"""报表路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from campus.api.deps import Access, SessionDep, require
from campus.schemas.report import ClassReportItem, SubjectReportItem, WorkloadItem
from campus.services.access import Permission
from campus.services.report import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/workload", response_model=list[WorkloadItem])
async def read_workload(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.DASHBOARD_READ)),
) -> list[WorkloadItem]:
    """教师工作量（管理员全量 / 教师本人）。"""
    return await ReportService(session).workload(access)


@router.get("/subjects", response_model=list[SubjectReportItem])
async def read_subject_report(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.DASHBOARD_READ)),
) -> list[SubjectReportItem]:
    """学科成绩分析（教师限本人课程）。"""
    return await ReportService(session).subjects(access)


@router.get("/classes", response_model=list[ClassReportItem])
async def read_class_report(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.DASHBOARD_READ)),
) -> list[ClassReportItem]:
    """班级对比（教师限本人班级）。"""
    return await ReportService(session).classes(access)
