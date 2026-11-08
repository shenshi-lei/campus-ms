"""组织契约：院系、学科与学期。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from campus.models.enums import DepartmentKind, SemesterStatus
from campus.schemas.common import ORMModel


class DepartmentCreate(BaseModel):
    """新增院系/处室。"""

    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=1, max_length=50)
    kind: DepartmentKind = DepartmentKind.COLLEGE
    parent_id: int | None = None
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    """部分更新院系。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    kind: DepartmentKind | None = None
    parent_id: int | None = None
    is_active: bool | None = None


class DepartmentRead(ORMModel):
    """院系输出。"""

    id: int
    code: str
    name: str
    kind: DepartmentKind
    parent_id: int | None
    is_active: bool


class SubjectCreate(BaseModel):
    """新增学科。"""

    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=1, max_length=50)
    department_id: int | None = None
    is_active: bool = True


class SubjectUpdate(BaseModel):
    """部分更新学科。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    department_id: int | None = None
    is_active: bool | None = None


class SubjectRead(ORMModel):
    """学科输出。"""

    id: int
    code: str
    name: str
    department_id: int | None
    is_active: bool


class SemesterCreate(BaseModel):
    """新增学期。"""

    name: str = Field(min_length=4, max_length=20)
    start_date: date
    end_date: date
    status: SemesterStatus = SemesterStatus.PLANNED
    weeks: int = Field(default=20, ge=1, le=30)
    is_current: bool = False


class SemesterUpdate(BaseModel):
    """部分更新学期。"""

    start_date: date | None = None
    end_date: date | None = None
    status: SemesterStatus | None = None
    weeks: int | None = Field(default=None, ge=1, le=30)
    is_current: bool | None = None


class SemesterRead(ORMModel):
    """学期输出。"""

    id: int
    name: str
    start_date: date
    end_date: date
    status: SemesterStatus
    weeks: int
    is_current: bool


class OrgNode(BaseModel):
    """组织树节点：院系/班级/人员。"""

    key: str
    type: str
    label: str
    subtitle: str = ""
    count: int = 0
    selectable: bool = False
    has_children: bool = False
    children: list[OrgNode] = []


class OrgTreeRead(BaseModel):
    """组织树输出。"""

    nodes: list[OrgNode] = []
    total: int = 0
