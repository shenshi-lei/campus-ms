"""用户模型：登录凭证与角色。"""

from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import Role

role_type = SAEnum(
    Role,
    native_enum=False,
    length=20,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)


class User(TimestampMixin, Base):
    """系统账号，与教师/学生档案通过 user_id 关联。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(role_type, default=Role.STUDENT)
    is_active: Mapped[bool] = mapped_column(default=True)
