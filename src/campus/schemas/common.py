"""通用契约：分页、消息与 ORM 基类。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    """允许从 ORM 实例直接校验的基类。"""

    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    """简单文本响应。"""

    message: str


class Page(BaseModel, Generic[T]):
    """统一分页响应。"""

    items: list[T]
    total: int
    page: int
    page_size: int
