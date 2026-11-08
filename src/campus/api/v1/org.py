"""组织路由：院系、学科与学期。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.org import (
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
    OrgTreeRead,
    SemesterCreate,
    SemesterRead,
    SemesterUpdate,
    SubjectCreate,
    SubjectRead,
    SubjectUpdate,
)
from campus.services.access import Permission
from campus.services.org import (
    DepartmentService,
    OrgTreeService,
    SemesterService,
    SubjectService,
)

router = APIRouter(prefix="/org", tags=["org"])


@router.get("/tree", response_model=OrgTreeRead)
async def read_org_tree(
    session: SessionDep,
    access: Access,
    person_type: Literal["student", "teacher"] = Query(default="student"),
    keyword: str | None = Query(default=None, max_length=50),
) -> OrgTreeRead:
    """人员选择树：院系 → 班级 → 学生 / 院系 → 教师。"""
    return await OrgTreeService(session).tree(access, person_type=person_type, keyword=keyword)


@router.get("/departments", response_model=list[DepartmentRead])
async def list_departments(
    session: SessionDep,
    _: None = Depends(require(Permission.DEPARTMENT_READ)),
) -> list[DepartmentRead]:
    """院系列表。"""
    return await DepartmentService(session).list_departments()


@router.post("/departments", response_model=DepartmentRead, status_code=201)
async def create_department(
    payload: DepartmentCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.DEPARTMENT_MANAGE)),
) -> DepartmentRead:
    """新增院系（管理员）。"""
    return await DepartmentService(session).create_department(payload)


@router.patch("/departments/{department_id}", response_model=DepartmentRead)
async def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.DEPARTMENT_MANAGE)),
) -> DepartmentRead:
    """更新院系（管理员）。"""
    return await DepartmentService(session).update_department(department_id, payload)


@router.get("/subjects", response_model=list[SubjectRead])
async def list_subjects(
    session: SessionDep,
    _: None = Depends(require(Permission.SUBJECT_READ)),
) -> list[SubjectRead]:
    """学科列表。"""
    return await SubjectService(session).list_subjects()


@router.post("/subjects", response_model=SubjectRead, status_code=201)
async def create_subject(
    payload: SubjectCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.SUBJECT_MANAGE)),
) -> SubjectRead:
    """新增学科（管理员）。"""
    return await SubjectService(session).create_subject(payload)


@router.patch("/subjects/{subject_id}", response_model=SubjectRead)
async def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.SUBJECT_MANAGE)),
) -> SubjectRead:
    """更新学科（管理员）。"""
    return await SubjectService(session).update_subject(subject_id, payload)


@router.get("/semesters", response_model=list[SemesterRead])
async def list_semesters(
    session: SessionDep,
    _: None = Depends(require(Permission.SEMESTER_READ)),
) -> list[SemesterRead]:
    """学期列表。"""
    return await SemesterService(session).list_semesters()


@router.post("/semesters", response_model=SemesterRead, status_code=201)
async def create_semester(
    payload: SemesterCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.SEMESTER_MANAGE)),
) -> SemesterRead:
    """新增学期（管理员）。"""
    return await SemesterService(session).create_semester(payload)


@router.patch("/semesters/{semester_id}", response_model=SemesterRead)
async def update_semester(
    semester_id: int,
    payload: SemesterUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.SEMESTER_MANAGE)),
) -> SemesterRead:
    """更新学期（管理员）。"""
    return await SemesterService(session).update_semester(semester_id, payload)


@router.post("/semesters/{semester_id}/activate", response_model=SemesterRead)
async def activate_semester(
    semester_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.SEMESTER_MANAGE)),
) -> SemesterRead:
    """设为当前学期（管理员）。"""
    return await SemesterService(session).activate(semester_id)
