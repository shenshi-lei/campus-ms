"""缴费路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.models.enums import FeeStatus
from campus.schemas.common import Page
from campus.schemas.fee import FeeCreate, FeeRead
from campus.services.access import Permission
from campus.services.extras import FeeService

router = APIRouter(prefix="/fees", tags=["fees"])


@router.get("", response_model=Page[FeeRead])
async def list_fees(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.FEE_READ)),
    student_id: int | None = Query(default=None, ge=1),
    status: FeeStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[FeeRead]:
    """费用列表（学生本人 / 教师本班 / 管理员全量）。"""
    return await FeeService(session).list_fees(
        access=access,
        student_id=student_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=FeeRead, status_code=201)
async def create_fee(
    payload: FeeCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.FEE_MANAGE)),
) -> FeeRead:
    """新增费用项（管理员）。"""
    return await FeeService(session).create_fee(payload)


@router.post("/{fee_id}/pay", response_model=FeeRead)
async def pay_fee(
    fee_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.FEE_PAY)),
) -> FeeRead:
    """缴费：学生仅能支付本人费用。"""
    return await FeeService(session).pay(fee_id, access)
