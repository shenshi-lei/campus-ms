"""账号管理路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.account import AccountRead, AccountUpdate, ResetPasswordRequest
from campus.schemas.common import Message, Page
from campus.services.access import Permission
from campus.services.accounts import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=Page[AccountRead])
async def list_accounts(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.ACCOUNT_MANAGE)),
    keyword: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[AccountRead]:
    """账号列表（管理员）。"""
    return await AccountService(session).list_accounts(
        access=access, keyword=keyword, page=page, page_size=page_size
    )


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: int,
    payload: AccountUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.ACCOUNT_MANAGE)),
) -> AccountRead:
    """启用或停用账号（管理员）。"""
    return await AccountService(session).set_active(account_id, payload.is_active, access)


@router.post("/{account_id}/reset-password", response_model=Message)
async def reset_password(
    account_id: int,
    payload: ResetPasswordRequest,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.ACCOUNT_MANAGE)),
) -> Message:
    """重置账号密码（管理员）。"""
    return await AccountService(session).reset_password(account_id, payload.new_password, access)
