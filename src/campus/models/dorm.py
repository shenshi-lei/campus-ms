"""宿舍与床位分配。"""

from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin
from campus.models.enums import Gender


class Dorm(TimestampMixin, Base):
    """宿舍房间：楼栋 + 房间号唯一。"""

    __tablename__ = "dorms"
    __table_args__ = (UniqueConstraint("building", "room_no", name="uq_dorms_building_room"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    building: Mapped[str] = mapped_column(String(20))
    room_no: Mapped[str] = mapped_column(String(20))
    capacity: Mapped[int] = mapped_column(Integer, default=4)
    gender: Mapped[Gender] = mapped_column(
        SAEnum(
            Gender,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=Gender.UNKNOWN,
    )


class DormAssignment(TimestampMixin, Base):
    """床位分配：一个学生只能有一个床位，房间内床位号唯一。"""

    __tablename__ = "dorm_assignments"
    __table_args__ = (UniqueConstraint("dorm_id", "bed_no", name="uq_dorm_assignments_dorm_bed"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), unique=True
    )
    dorm_id: Mapped[int] = mapped_column(ForeignKey("dorms.id", ondelete="CASCADE"))
    bed_no: Mapped[int] = mapped_column(Integer)
