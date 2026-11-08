"""导入导出路由。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response

from campus.api.deps import Access, SessionDep, require
from campus.schemas.transfer import ImportRequest, ImportResult
from campus.services.access import Permission
from campus.services.audit import AuditService
from campus.services.transfer import TransferService

router = APIRouter(prefix="/transfer", tags=["transfer"])


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _file_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )


@router.get("/export/resource/{resource}")
async def export_resource(
    resource: str,
    session: SessionDep,
    access: Access,
    fmt: str = Query(default="csv", pattern="^(csv|xlsx|pdf)$"),
    keyword: str | None = Query(default=None, max_length=50),
) -> Response:
    """通用导出：学生/教师/课程/班级/选课/成绩/考勤/请假/缴费/课表/审计。"""
    content, media_type, filename = await TransferService(session).export_resource(
        access, resource, fmt=fmt, keyword=keyword
    )
    await AuditService(session).record(
        access,
        method="GET",
        path=f"/api/v1/transfer/export/resource/{resource}",
        detail=f"export {resource} as {fmt}",
    )
    return _file_response(content, media_type, filename)


@router.get("/template/{resource}")
async def download_template(
    resource: str,
    session: SessionDep,
    _: None = Depends(require(Permission.STUDENT_MANAGE)),
) -> Response:
    """下载 CSV 导入模板。"""
    headers = await TransferService(session).template_headers(resource)
    return _file_response(
        TransferService.template_csv(resource, headers),
        "text/csv; charset=utf-8",
        f"{resource}-template.csv",
    )


@router.get("/export/students")
async def export_students(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.STUDENT_READ)),
) -> Response:
    """导出学生 CSV（按数据范围）。"""
    content = await TransferService(session).export_students(access)
    await AuditService(session).record(
        access, method="GET", path="/api/v1/transfer/export/students", detail="export students"
    )
    return _csv_response(content, "students.csv")


@router.get("/export/scores")
async def export_scores(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCORE_READ)),
) -> Response:
    """导出成绩 CSV（按数据范围，学生仅已发布）。"""
    content = await TransferService(session).export_scores(access)
    await AuditService(session).record(
        access, method="GET", path="/api/v1/transfer/export/scores", detail="export scores"
    )
    return _csv_response(content, "scores.csv")


@router.get("/export/attendance")
async def export_attendance(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.ATTENDANCE_READ)),
) -> Response:
    """导出考勤 CSV（按数据范围）。"""
    content = await TransferService(session).export_attendance(access)
    await AuditService(session).record(
        access, method="GET", path="/api/v1/transfer/export/attendance", detail="export attendance"
    )
    return _csv_response(content, "attendance.csv")


@router.post("/import/students", response_model=ImportResult)
async def import_students(
    payload: ImportRequest,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.STUDENT_MANAGE)),
) -> ImportResult:
    """导入学生 CSV（管理员）。"""
    return await TransferService(session).import_students(
        access, payload.csv, dry_run=payload.dry_run, mode=payload.mode
    )
