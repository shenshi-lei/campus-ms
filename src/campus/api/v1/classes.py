"""班级路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Message
from campus.schemas.school_class import (
    SchoolClassCreate,
    SchoolClassRead,
    SchoolClassUpdate,
)
from campus.schemas.seat import SeatMap, SeatUpdate
from campus.services.access import Permission
from campus.services.people import SchoolClassService
from campus.services.seat import SeatService

router = APIRouter(prefix="/classes", tags=["classes"])


@router.get("", response_model=list[SchoolClassRead])
async def list_classes(session: SessionDep, access: Access) -> list[SchoolClassRead]:
    """班级列表（数据量小，不分页；按数据范围过滤）。"""
    access.ensure(Permission.CLASS_READ)
    return await SchoolClassService(session).list_classes(access)


@router.post("", response_model=SchoolClassRead, status_code=201)
async def create_class(
    payload: SchoolClassCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.CLASS_MANAGE)),
) -> SchoolClassRead:
    """新增班级（管理员）。"""
    return await SchoolClassService(session).create_class(payload)


@router.get("/{class_id}", response_model=SchoolClassRead)
async def read_class(class_id: int, session: SessionDep, access: Access) -> SchoolClassRead:
    """按 ID 查看班级。"""
    access.ensure(Permission.CLASS_READ)
    return await SchoolClassService(session).get_class(class_id, access)


@router.get("/{class_id}/seats", response_model=SeatMap)
async def read_seat_map(class_id: int, session: SessionDep, access: Access) -> SeatMap:
    """班级座位表。"""
    return await SeatService(session).seat_map(class_id, access)


@router.put("/{class_id}/seats", response_model=SeatMap)
async def update_seat_map(
    class_id: int,
    payload: SeatUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.CLASS_SEAT_MANAGE)),
) -> SeatMap:
    """调整班级座位（班主任/管理员）。"""
    return await SeatService(session).update_seats(class_id, payload, access)


@router.patch("/{class_id}", response_model=SchoolClassRead)
async def update_class(
    class_id: int,
    payload: SchoolClassUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.CLASS_MANAGE)),
) -> SchoolClassRead:
    """部分更新班级（管理员）。"""
    return await SchoolClassService(session).update_class(class_id, payload)


@router.delete("/{class_id}", response_model=Message)
async def delete_class(
    class_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.CLASS_MANAGE)),
) -> Message:
    """删除空班级（管理员）。"""
    return await SchoolClassService(session).delete_class(class_id)
