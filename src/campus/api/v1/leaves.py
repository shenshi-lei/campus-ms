"""请假路由：申请、审批、详情与流程配置。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.models.enums import ApplicantType, LeaveStatus, LeaveType
from campus.schemas.common import Page
from campus.schemas.leave import (
    LeaveApply,
    LeaveDecision,
    LeaveFlowCreate,
    LeaveFlowPreview,
    LeaveFlowRead,
    LeaveFlowUpdate,
    LeaveRead,
)
from campus.services.access import Permission
from campus.services.leave import LeaveService

router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.get("/flows", response_model=list[LeaveFlowRead])
async def list_leave_flows(
    session: SessionDep,
    _: None = Depends(require(Permission.WORKFLOW_MANAGE)),
) -> list[LeaveFlowRead]:
    """请假流程列表。"""
    return await LeaveService(session).list_flows()


@router.get("/flows/preview", response_model=LeaveFlowPreview)
async def preview_leave_flow(
    session: SessionDep,
    _: None = Depends(require(Permission.WORKFLOW_MANAGE)),
    applicant_type: ApplicantType = Query(default=ApplicantType.STUDENT),
    leave_type: LeaveType = Query(default=LeaveType.PERSONAL),
    days: float = Query(default=1, ge=0, le=365),
) -> LeaveFlowPreview:
    """按条件预览命中的流程。"""
    return await LeaveService(session).preview_flow(applicant_type, leave_type, days)


@router.post("/flows", response_model=LeaveFlowRead, status_code=201)
async def create_leave_flow(
    payload: LeaveFlowCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.WORKFLOW_MANAGE)),
) -> LeaveFlowRead:
    """新增请假流程。"""
    return await LeaveService(session).create_flow(payload)


@router.patch("/flows/{flow_id}", response_model=LeaveFlowRead)
async def update_leave_flow(
    flow_id: int,
    payload: LeaveFlowUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.WORKFLOW_MANAGE)),
) -> LeaveFlowRead:
    """更新请假流程。"""
    return await LeaveService(session).update_flow(flow_id, payload)


@router.delete("/flows/{flow_id}")
async def delete_leave_flow(
    flow_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.WORKFLOW_MANAGE)),
) -> dict[str, str]:
    """删除未被使用的请假流程。"""
    await LeaveService(session).delete_flow(flow_id)
    return {"message": "已删除"}


@router.get("", response_model=Page[LeaveRead])
async def list_leaves(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.LEAVE_READ)),
    status: LeaveStatus | None = Query(default=None),
    applicant_type: ApplicantType | None = Query(default=None),
    leave_type: LeaveType | None = Query(default=None),
    mine: bool = Query(default=False),
    keyword: str | None = Query(default=None, max_length=50),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[LeaveRead]:
    """请假列表（本人 / 本班 / 全部）。"""
    return await LeaveService(session).list_leaves(
        access=access,
        status=status,
        applicant_type=applicant_type,
        leave_type=leave_type,
        mine=mine,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/pending", response_model=list[LeaveRead])
async def pending_leaves(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.LEAVE_APPROVE)),
) -> list[LeaveRead]:
    """待我审批的请假（兼容旧接口，最多 100 条）。"""
    page = await LeaveService(session).pending(access, page=1, page_size=100)
    return page.items


@router.get("/pending/page", response_model=Page[LeaveRead])
async def pending_leaves_page(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.LEAVE_APPROVE)),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[LeaveRead]:
    """待我审批的请假（分页）。"""
    return await LeaveService(session).pending(access, page=page, page_size=page_size)


@router.post("", response_model=LeaveRead, status_code=201)
async def apply_leave(
    payload: LeaveApply,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.LEAVE_APPLY)),
) -> LeaveRead:
    """提交请假申请。"""
    return await LeaveService(session).apply(payload, access)


@router.get("/{request_id}", response_model=LeaveRead)
async def read_leave(request_id: int, session: SessionDep, access: Access) -> LeaveRead:
    """请假详情。"""
    return await LeaveService(session).get(request_id, access)


@router.post("/{request_id}/approve", response_model=LeaveRead)
async def approve_leave(
    request_id: int,
    payload: LeaveDecision,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.LEAVE_APPROVE)),
) -> LeaveRead:
    """通过当前审批级。"""
    return await LeaveService(session).approve(request_id, payload, access)


@router.post("/{request_id}/reject", response_model=LeaveRead)
async def reject_leave(
    request_id: int,
    payload: LeaveDecision,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.LEAVE_APPROVE)),
) -> LeaveRead:
    """驳回当前审批级。"""
    return await LeaveService(session).reject(request_id, payload, access)


@router.post("/{request_id}/cancel", response_model=LeaveRead)
async def cancel_leave(
    request_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.LEAVE_APPLY)),
) -> LeaveRead:
    """撤销本人未审批的申请。"""
    return await LeaveService(session).cancel(request_id, access)


@router.post("/{request_id}/revoke", response_model=LeaveRead)
async def revoke_leave(
    request_id: int,
    payload: LeaveDecision,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.LEAVE_APPROVE)),
) -> LeaveRead:
    """管理员撤回已通过的申请。"""
    return await LeaveService(session).revoke(request_id, payload, access)
