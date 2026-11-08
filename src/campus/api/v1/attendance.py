"""考勤路由。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.attendance import AttendanceBulk, AttendanceRead
from campus.schemas.common import Page
from campus.services.access import Permission
from campus.services.extras import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("", response_model=Page[AttendanceRead])
async def list_attendance(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.ATTENDANCE_READ)),
    course_id: int | None = Query(default=None, ge=1),
    student_id: int | None = Query(default=None, ge=1),
    day: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[AttendanceRead]:
    """考勤列表（学生本人 / 教师本人课程 / 管理员全量）。"""
    return await AttendanceService(session).list_attendance(
        access=access,
        course_id=course_id,
        student_id=student_id,
        day=day,
        page=page,
        page_size=page_size,
    )


@router.post("/bulk", response_model=list[AttendanceRead], status_code=201)
async def bulk_record(
    payload: AttendanceBulk,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.ATTENDANCE_WRITE)),
) -> list[AttendanceRead]:
    """批量登记考勤（重复登记覆盖）。"""
    return await AttendanceService(session).bulk_record(payload, access)
