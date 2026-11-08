"""宿舍契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from campus.models.enums import Gender
from campus.schemas.common import ORMModel


class DormCreate(BaseModel):
    """新增宿舍房间。"""

    building: str = Field(min_length=1, max_length=20)
    room_no: str = Field(min_length=1, max_length=20)
    capacity: int = Field(default=4, ge=1, le=20)
    gender: Gender = Gender.UNKNOWN


class DormRead(ORMModel):
    """房间输出，附带已住人数。"""

    id: int
    building: str
    room_no: str
    capacity: int
    gender: Gender
    occupied: int = 0


class DormAssignInput(BaseModel):
    """床位分配入参。"""

    student_id: int = Field(ge=1)
    dorm_id: int = Field(ge=1)
    bed_no: int = Field(ge=1, le=20)


class DormAssignmentRead(BaseModel):
    """床位输出。"""

    id: int
    student_id: int
    student_no: str
    student_name: str
    dorm_id: int
    building: str
    room_no: str
    bed_no: int
