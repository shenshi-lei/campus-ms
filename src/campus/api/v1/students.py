"""学生路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, CurrentStudent, SessionDep, require
from campus.schemas.common import Message, Page
from campus.schemas.student import (
    StudentCreate,
    StudentRead,
    StudentUpdate,
    TranscriptItem,
)
from campus.schemas.student_status import (
    StudentStatusChange,
    StudentStatusHistoryRead,
)
from campus.services.access import Permission
from campus.services.people import StudentService

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=Page[StudentRead])
async def list_students(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.STUDENT_READ)),
    keyword: str | None = Query(default=None, max_length=50),
    class_id: int | None = Query(default=None, ge=1),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[StudentRead]:
    """分页检索学生（按数据范围过滤）。"""
    return await StudentService(session).list_students(
        access=access,
        keyword=keyword,
        class_id=class_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get("/me", response_model=StudentRead)
async def read_my_profile(student: CurrentStudent) -> StudentRead:
    """学生查看本人档案。"""
    return StudentRead.model_validate(student)


@router.post("", response_model=StudentRead, status_code=201)
async def create_student(
    payload: StudentCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.STUDENT_MANAGE)),
) -> StudentRead:
    """新增学生（管理员）。"""
    return await StudentService(session).create_student(payload)


@router.get("/{student_id}", response_model=StudentRead)
async def read_student(
    student_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.STUDENT_READ)),
) -> StudentRead:
    """按 ID 查看学生（按数据范围过滤）。"""
    return await StudentService(session).get_student(student_id, access)


@router.patch("/{student_id}", response_model=StudentRead)
async def update_student(
    student_id: int,
    payload: StudentUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.STUDENT_MANAGE)),
) -> StudentRead:
    """部分更新学生（管理员）。"""
    return await StudentService(session).update_student(student_id, payload, access)


@router.post("/{student_id}/status", response_model=StudentRead)
async def change_student_status(
    student_id: int,
    payload: StudentStatusChange,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.STUDENT_MANAGE)),
) -> StudentRead:
    """变更学籍状态并留痕（管理员）。"""
    return await StudentService(session).change_status(student_id, payload, access)


@router.get("/{student_id}/status-history", response_model=list[StudentStatusHistoryRead])
async def read_status_history(
    student_id: int, session: SessionDep, access: Access
) -> list[StudentStatusHistoryRead]:
    """学籍异动时间线（本人/本班教师/管理员）。"""
    return await StudentService(session).status_history(student_id, access)


@router.delete("/{student_id}", response_model=Message)
async def deactivate_student(
    student_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.STUDENT_MANAGE)),
) -> Message:
    """停用学生（软删除）。"""
    return await StudentService(session).deactivate_student(student_id)


@router.get("/{student_id}/transcript", response_model=list[TranscriptItem])
async def read_transcript(
    student_id: int, session: SessionDep, access: Access
) -> list[TranscriptItem]:
    """成绩单：管理员/教师按范围，学生仅本人。"""
    return await StudentService(session).transcript_for(student_id, access)
