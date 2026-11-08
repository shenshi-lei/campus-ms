"""群组：从组织树选择人员，供通知、审批与日程复用。"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import GroupMemberType


class UserGroup(TimestampMixin, Base):
    """用户群组。"""

    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(30), default="custom")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class UserGroupMember(TimestampMixin, Base):
    """群组成员：支持用户、学生、教师、院系、班级五种来源。"""

    __tablename__ = "user_group_members"
    __table_args__ = (
        UniqueConstraint(
            "group_id", "member_type", "member_id", name="uq_user_group_members_target"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("user_groups.id", ondelete="CASCADE"))
    member_type: Mapped[GroupMemberType] = mapped_column(
        SAEnum(
            GroupMemberType,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        )
    )
    member_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(100), default="")
