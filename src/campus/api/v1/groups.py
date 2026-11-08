"""群组路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.group import GroupCreate, GroupExpandRead, GroupRead, GroupUpdate
from campus.services.access import Permission
from campus.services.group import GroupService

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=list[GroupRead])
async def list_groups(
    session: SessionDep,
    _: None = Depends(require(Permission.GROUP_READ)),
    keyword: str | None = Query(default=None, max_length=50),
) -> list[GroupRead]:
    """群组列表。"""
    return await GroupService(session).list_groups(keyword=keyword)


@router.post("", response_model=GroupRead, status_code=201)
async def create_group(
    payload: GroupCreate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.GROUP_MANAGE)),
) -> GroupRead:
    """新增群组。"""
    return await GroupService(session).create_group(payload, access.user.id)


@router.get("/{group_id}", response_model=GroupRead)
async def read_group(
    group_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.GROUP_READ)),
) -> GroupRead:
    """群组详情。"""
    return await GroupService(session).get_group(group_id)


@router.patch("/{group_id}", response_model=GroupRead)
async def update_group(
    group_id: int,
    payload: GroupUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.GROUP_MANAGE)),
) -> GroupRead:
    """更新群组与成员。"""
    return await GroupService(session).update_group(group_id, payload, access.user.id)


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.GROUP_MANAGE)),
) -> dict[str, str]:
    """删除群组。"""
    await GroupService(session).delete_group(group_id)
    return {"message": "已删除"}


@router.get("/{group_id}/expand", response_model=GroupExpandRead)
async def expand_group(
    group_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.GROUP_READ)),
) -> GroupExpandRead:
    """展开群组实际用户。"""
    return await GroupService(session).expand(group_id)
