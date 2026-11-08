"""成绩路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from campus.api.deps import Access, SessionDep, require
from campus.schemas.common import Page
from campus.schemas.score import ScoreBatch, ScoreRead, ScoreUpdate
from campus.services.academics import ScoreService
from campus.services.access import Permission

router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("", response_model=Page[ScoreRead])
async def list_scores(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCORE_READ)),
    course_id: int | None = Query(default=None, ge=1),
    student_id: int | None = Query(default=None, ge=1),
    semester: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[ScoreRead]:
    """成绩列表（学生本人 / 教师本人课程 / 管理员全量）。"""
    return await ScoreService(session).list_scores(
        access=access,
        course_id=course_id,
        student_id=student_id,
        semester=semester,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=list[ScoreRead], status_code=201)
async def record_scores(
    payload: ScoreBatch,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCORE_WRITE)),
) -> list[ScoreRead]:
    """批量录入/更新成绩（教师仅限本人课程）。"""
    return await ScoreService(session).record_batch(payload, access)


@router.patch("/{score_id}", response_model=ScoreRead)
async def update_score(
    score_id: int,
    payload: ScoreUpdate,
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.SCORE_WRITE)),
) -> ScoreRead:
    """修改单条成绩。"""
    return await ScoreService(session).update_score(score_id, payload, access)
