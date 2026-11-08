"""选课路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Message, Page
from campus.schemas.enrollment import EnrollmentCreate, EnrollmentRead
from campus.services.academics import EnrollmentService
from campus.services.access import Permission

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.get("", response_model=Page[EnrollmentRead])
async def list_enrollments(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.ENROLLMENT_READ)),
    student_id: int | None = Query(default=None, ge=1),
    course_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[EnrollmentRead]:
    """选课列表（学生本人 / 教师本人课程 / 管理员全量）。"""
    return await EnrollmentService(session).list_enrollments(
        access=access,
        student_id=student_id,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=EnrollmentRead, status_code=201)
async def enroll(payload: EnrollmentCreate, session: SessionDep, access: Access) -> EnrollmentRead:
    """选课：学生自助，管理员可代选。"""
    return await EnrollmentService(session).enroll(payload, access)


@router.delete("/{enrollment_id}", response_model=Message)
async def drop(enrollment_id: int, session: SessionDep, access: Access) -> Message:
    """退课（已录入成绩则拒绝）。"""
    return await EnrollmentService(session).drop(enrollment_id, access)
