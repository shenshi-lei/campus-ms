"""宿舍路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Message, Page
from campus.schemas.dorm import (
    DormAssignInput,
    DormAssignmentRead,
    DormCreate,
    DormRead,
)
from campus.services.access import Permission
from campus.services.extras import DormService

router = APIRouter(prefix="/dorms", tags=["dorms"])


@router.get("", response_model=Page[DormRead])
async def list_dorms(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.DORM_READ)),
    building: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[DormRead]:
    """宿舍房间列表（含已住人数）。"""
    return await DormService(session).list_dorms(
        access=access, building=building, page=page, page_size=page_size
    )


@router.get("/me", response_model=DormAssignmentRead | None)
async def read_my_dorm(session: SessionDep, access: Access) -> DormAssignmentRead | None:
    """学生查看本人床位。"""
    return await DormService(session).my_assignment(access)


@router.post("", response_model=DormRead, status_code=201)
async def create_dorm(
    payload: DormCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.DORM_MANAGE)),
) -> DormRead:
    """新增宿舍房间（管理员）。"""
    return await DormService(session).create_dorm(payload)


@router.get("/assignments", response_model=Page[DormAssignmentRead])
async def list_assignments(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.DORM_READ)),
    dorm_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[DormAssignmentRead]:
    """床位分配列表（教师仅本班）。"""
    return await DormService(session).list_assignments(
        access=access, dorm_id=dorm_id, page=page, page_size=page_size
    )


@router.post("/assignments", response_model=DormAssignmentRead, status_code=201)
async def assign_bed(
    payload: DormAssignInput,
    session: SessionDep,
    _: None = Depends(require(Permission.DORM_MANAGE)),
) -> DormAssignmentRead:
    """分配床位（管理员）。"""
    return await DormService(session).assign(payload)


@router.delete("/assignments/{assignment_id}", response_model=Message)
async def unassign_bed(
    assignment_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.DORM_MANAGE)),
) -> Message:
    """退宿（管理员）。"""
    return await DormService(session).unassign(assignment_id)


@router.delete("/{dorm_id}", response_model=Message)
async def delete_dorm(
    dorm_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.DORM_MANAGE)),
) -> Message:
    """删除空房间（管理员）。"""
    return await DormService(session).delete_dorm(dorm_id)
