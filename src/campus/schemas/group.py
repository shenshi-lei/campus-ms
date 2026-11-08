"""群组契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from campus.models.enums import GroupMemberType


class GroupMemberInput(BaseModel):
    """群组成员来源。"""

    member_type: GroupMemberType
    member_id: int = Field(ge=1)


class GroupCreate(BaseModel):
    """新增群组。"""

    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=255)
    kind: str = Field(default="custom", max_length=30)
    is_active: bool = True
    members: list[GroupMemberInput] = Field(default_factory=list)


class GroupUpdate(BaseModel):
    """更新群组；提供 members 时整体替换成员。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    kind: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None
    members: list[GroupMemberInput] | None = None


class GroupMemberRead(BaseModel):
    """群组成员输出。"""

    id: int
    member_type: GroupMemberType
    member_id: int
    user_id: int | None
    display_name: str
    subtitle: str = ""


class GroupRead(BaseModel):
    """群组输出。"""

    id: int
    code: str
    name: str
    description: str
    kind: str
    is_active: bool
    member_count: int
    members: list[GroupMemberRead] = Field(default_factory=list)


class GroupExpandRead(BaseModel):
    """群组展开后的实际用户。"""

    user_ids: list[int]
    user_count: int
    unresolved: int
