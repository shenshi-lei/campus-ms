"""课程路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Message, Page
from campus.schemas.course import CourseCreate, CourseRead, CourseUpdate, RosterItem
from campus.schemas.teaching import (
    CourseClassRead,
    CourseClassUpdate,
    CourseTeacherRead,
    CourseTeacherUpdate,
)
from campus.services.academics import CourseService
from campus.services.access import Permission
from campus.services.teaching import CourseRosterService

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=Page[CourseRead])
async def list_courses(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.COURSE_READ)),
    keyword: str | None = Query(default=None, max_length=50),
    semester: str | None = Query(default=None, max_length=20),
    teacher_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[CourseRead]:
    """分页检索课程（登录且具备课程读权限）。"""
    return await CourseService(session).list_courses(
        access=access,
        keyword=keyword,
        semester=semester,
        teacher_id=teacher_id,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CourseRead, status_code=201)
async def create_course(
    payload: CourseCreate,
    session: SessionDep,
    _: None = Depends(require(Permission.COURSE_MANAGE)),
) -> CourseRead:
    """新增课程（管理员）。"""
    return await CourseService(session).create_course(payload)


@router.get("/{course_id}", response_model=CourseRead)
async def read_course(
    course_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.COURSE_READ)),
) -> CourseRead:
    """按 ID 查看课程。"""
    return await CourseService(session).get_course(course_id, access)


@router.patch("/{course_id}", response_model=CourseRead)
async def update_course(
    course_id: int,
    payload: CourseUpdate,
    session: SessionDep,
    _: None = Depends(require(Permission.COURSE_MANAGE)),
) -> CourseRead:
    """部分更新课程（管理员）。"""
    return await CourseService(session).update_course(course_id, payload)


@router.delete("/{course_id}", response_model=Message)
async def delete_course(
    course_id: int,
    session: SessionDep,
    _: None = Depends(require(Permission.COURSE_MANAGE)),
) -> Message:
    """删除无选课的课程（管理员）。"""
    return await CourseService(session).delete_course(course_id)


@router.get("/{course_id}/roster", response_model=list[RosterItem])
async def read_roster(
    course_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.ENROLLMENT_READ)),
) -> list[RosterItem]:
    """课程选课名单（教师仅本人课程）。"""
    return await CourseService(session).roster(course_id, access)


@router.get("/{course_id}/teachers", response_model=list[CourseTeacherRead])
async def list_course_teachers(
    course_id: int, session: SessionDep, access: Access
) -> list[CourseTeacherRead]:
    """课程教师列表。"""
    return await CourseRosterService(session).list_teachers(course_id, access)


@router.put("/{course_id}/teachers", response_model=list[CourseTeacherRead])
async def set_course_teachers(
    course_id: int,
    payload: CourseTeacherUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.COURSE_MANAGE)),
) -> list[CourseTeacherRead]:
    """配置课程教师（管理员）。"""
    return await CourseRosterService(session).set_teachers(course_id, payload, access)


@router.get("/{course_id}/classes", response_model=list[CourseClassRead])
async def list_course_classes(
    course_id: int, session: SessionDep, access: Access
) -> list[CourseClassRead]:
    """课程面向班级。"""
    return await CourseRosterService(session).list_classes(course_id, access)


@router.put("/{course_id}/classes", response_model=list[CourseClassRead])
async def set_course_classes(
    course_id: int,
    payload: CourseClassUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.COURSE_MANAGE)),
) -> list[CourseClassRead]:
    """配置课程面向班级（管理员）。"""
    return await CourseRosterService(session).set_classes(course_id, payload, access)


@router.post("/{course_id}/publish-scores", response_model=Message)
async def publish_course_scores(
    course_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCORE_PUBLISH)),
) -> Message:
    """发布课程成绩（教师本人课程 / 管理员）。"""
    return await CourseService(session).set_published(course_id, access, published=True)


@router.post("/{course_id}/unpublish-scores", response_model=Message)
async def unpublish_course_scores(
    course_id: int,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCORE_UNLOCK)),
) -> Message:
    """撤回已发布成绩（管理员）。"""
    return await CourseService(session).set_published(course_id, access, published=False)
