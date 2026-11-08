"""教师路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Message, Page
from campus.schemas.teacher import TeacherCreate, TeacherRead, TeacherUpdate
from campus.services.access import Permission
from campus.services.people import TeacherService

router = APIRouter(prefix="/teachers", tags=["teachers"])


@router.get("", response_model=Page[TeacherRead])
async def list_teachers(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.TEACHER_READ)),
    keyword: str | None = Query(default=None, max_length=50),
    department: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[TeacherRead]:
    """分页检索教师（学生只看到简版信息）。"""
    return await TeacherService(session).list_teachers(
        access=access,
        keyword=keyword,
        department=department,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TeacherRead, status_code=201)
async def create_teacher(
    payload: TeacherCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.TEACHER_MANAGE)),
) -> TeacherRead:
    """新增教师（管理员）。"""
    return await TeacherService(session).create_teacher(payload)


@router.get("/{teacher_id}", response_model=TeacherRead)
async def read_teacher(
    teacher_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.TEACHER_READ)),
) -> TeacherRead:
    """按 ID 查看教师（学生只看到简版信息）。"""
    return await TeacherService(session).get_teacher(teacher_id, access)


@router.patch("/{teacher_id}", response_model=TeacherRead)
async def update_teacher(
    teacher_id: int,
    payload: TeacherUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.TEACHER_MANAGE)),
) -> TeacherRead:
    """部分更新教师（管理员）。"""
    return await TeacherService(session).update_teacher(teacher_id, payload)


@router.delete("/{teacher_id}", response_model=Message)
async def deactivate_teacher(
    teacher_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.TEACHER_MANAGE)),
) -> Message:
    """停用教师（软删除）。"""
    return await TeacherService(session).deactivate_teacher(teacher_id)
