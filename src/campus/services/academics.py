"""教务服务：课程、选课、成绩。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import (
    AlreadyEnrolledError,
    ConflictError,
    CourseFullError,
    DuplicateKeyError,
    NotFoundError,
    PermissionDeniedError,
    ReferenceExistsError,
    ScoreLockedError,
)
from campus.core.pagination import PageParams
from campus.db.base import utc_now
from campus.models.course import Course
from campus.models.enrollment import Enrollment
from campus.models.score import Score
from campus.models.student import Student
from campus.models.teaching import CourseTeacher
from campus.repositories.academics import (
    CourseRepository,
    EnrollmentRepository,
    ScoreRepository,
)
from campus.schemas.common import Message, Page
from campus.schemas.course import CourseCreate, CourseRead, CourseUpdate, RosterItem
from campus.schemas.enrollment import EnrollmentCreate, EnrollmentRead
from campus.schemas.score import ScoreBatch, ScoreRead, ScoreUpdate
from campus.services.access import AccessContext, ScopeKind

DEFAULT_GRADE_SCHEME: dict[str, float] = {"usual": 0.4, "midterm": 0.0, "exam": 0.6}


def compute_final(usual: float | None, exam: float | None) -> float | None:
    """总评 = 平时 40% + 考试 60%；任一项缺失则不计算（兼容旧规则）。"""
    if usual is None or exam is None:
        return None
    return round(usual * 0.4 + exam * 0.6, 2)


def normalize_scheme(raw: dict[str, float] | None) -> dict[str, float]:
    """把课程成绩构成归一化为总和 1 的权重。"""
    scheme = dict(DEFAULT_GRADE_SCHEME)
    if raw:
        for key in scheme:
            if key in raw:
                scheme[key] = max(0.0, float(raw[key]))
    total = sum(scheme.values())
    if total <= 0:
        return dict(DEFAULT_GRADE_SCHEME)
    return {key: value / total for key, value in scheme.items()}


def compute_final_with_scheme(
    scheme: dict[str, float] | None,
    usual: float | None,
    midterm: float | None,
    exam: float | None,
) -> float | None:
    """按课程权重计算总评；任一有权重的分项缺失则不计算。"""
    weights = normalize_scheme(scheme)
    total = 0.0
    for key, value in (("usual", usual), ("midterm", midterm), ("exam", exam)):
        weight = weights[key]
        if weight <= 0:
            continue
        if value is None:
            return None
        total += value * weight
    return round(total, 2)


class CourseService:
    """课程管理。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CourseRepository(session)

    async def list_courses(
        self,
        *,
        access: AccessContext,
        keyword: str | None = None,
        semester: str | None = None,
        teacher_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[CourseRead]:
        params = PageParams(page=page, page_size=page_size)
        statement = self.repository.filtered(
            keyword=keyword, semester=semester, teacher_id=teacher_id
        )
        rows, total = await self.repository.paginate(statement, params.page, params.page_size)
        return Page[CourseRead](
            items=[CourseRead.model_validate(row) for row in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def get_course(self, course_id: int, access: AccessContext) -> CourseRead:
        return CourseRead.model_validate(await self._require(course_id))

    async def create_course(self, payload: CourseCreate) -> CourseRead:
        if await self.repository.get_by_code(payload.code):
            raise DuplicateKeyError("课程代码已存在")
        course = Course(**payload.model_dump())
        await self.repository.add(course)
        if course.teacher_id is not None:
            self.session.add(
                CourseTeacher(course_id=course.id, teacher_id=course.teacher_id, role="primary")
            )
        await self.session.commit()
        await self.session.refresh(course)
        return CourseRead.model_validate(course)

    async def update_course(self, course_id: int, payload: CourseUpdate) -> CourseRead:
        course = await self._require(course_id)
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(course, field, value)
        teacher_id = changes.get("teacher_id")
        if teacher_id is not None:
            existing = await self.session.scalar(
                select(CourseTeacher).where(
                    CourseTeacher.course_id == course.id,
                    CourseTeacher.teacher_id == teacher_id,
                )
            )
            if existing is None:
                self.session.add(
                    CourseTeacher(course_id=course.id, teacher_id=teacher_id, role="primary")
                )
        await self.session.commit()
        await self.session.refresh(course)
        return CourseRead.model_validate(course)

    async def set_published(
        self, course_id: int, access: AccessContext, *, published: bool
    ) -> Message:
        """发布或撤回课程成绩。"""
        course = await self._require(course_id)
        if published:
            access.ensure_course_write(course)
        elif "admin" not in access.role_codes:
            raise PermissionDeniedError("只有管理员可以撤回已发布成绩")
        count = await ScoreRepository(self.session).publish_for_course(
            course_id, published=published, at=utc_now() if published else None
        )
        await self.session.commit()
        action = "发布" if published else "撤回"
        return Message(message=f"已{action} {count} 条成绩")

    async def delete_course(self, course_id: int) -> Message:
        course = await self._require(course_id)
        if await EnrollmentRepository(self.session).count_for_course(course_id) > 0:
            raise ReferenceExistsError("课程仍有学生选课，不能删除")
        await self.repository.delete(course)
        await self.session.commit()
        return Message(message="课程已删除")

    async def roster(self, course_id: int, access: AccessContext) -> list[RosterItem]:
        await self._require(course_id)
        if access.scope.kind is ScopeKind.ALL:
            pass
        elif access.scope.kind is ScopeKind.CLASSES:
            if course_id not in access.scope.course_ids:
                raise PermissionDeniedError("只能查看本人所授课程的名单")
        else:
            raise PermissionDeniedError("没有权限查看课程名单")
        rows = await EnrollmentRepository(self.session).roster(course_id)
        return [
            RosterItem(
                enrollment_id=enrollment.id,
                student_id=student.id,
                student_no=student.student_no,
                student_name=student.name,
                status=enrollment.status,
            )
            for enrollment, student in rows
        ]

    async def _require(self, course_id: int) -> Course:
        course = await self.repository.get(course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        return course


class EnrollmentService:
    """选课与退课。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = EnrollmentRepository(session)

    async def list_enrollments(
        self,
        *,
        access: AccessContext,
        student_id: int | None,
        course_id: int | None,
        page: int,
        page_size: int,
    ) -> Page[EnrollmentRead]:
        params = PageParams(page=page, page_size=page_size)
        course_ids: frozenset[int] | None = None
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            pass
        elif scope.kind is ScopeKind.CLASSES:
            if course_id is not None and course_id not in scope.course_ids:
                raise PermissionDeniedError("只能查看本人所授课程的选课")
            course_ids = scope.course_ids
        elif scope.kind is ScopeKind.SELF:
            student_id = access.student_id
        else:
            return Page[EnrollmentRead](
                items=[], total=0, page=params.page, page_size=params.page_size
            )
        rows, total = await self.repository.paginated_rows(
            student_id=student_id,
            course_id=course_id,
            page=params.page,
            page_size=params.page_size,
            course_ids=course_ids,
        )
        return Page[EnrollmentRead](
            items=[
                self._to_read(enrollment, student, course) for enrollment, student, course in rows
            ],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def enroll(self, payload: EnrollmentCreate, access: AccessContext) -> EnrollmentRead:
        """学生自助选课；管理员可代选并指定 student_id。"""
        if access.scope.kind is ScopeKind.SELF:
            if access.student_id is None:
                raise PermissionDeniedError("当前账号没有关联的学生档案")
            target_student_id = access.student_id
        elif access.scope.kind is ScopeKind.ALL:
            if payload.student_id is None:
                raise ConflictError("管理员选课必须指定学生")
            target_student_id = payload.student_id
        else:
            raise PermissionDeniedError("教师不能代学生选课")

        student = await self.session.get(Student, target_student_id)
        if student is None:
            raise NotFoundError("学生不存在")
        if not student.is_active:
            raise ConflictError("学生已停用，不能选课")
        course = await CourseRepository(self.session).get(payload.course_id)
        if course is None:
            raise NotFoundError("课程不存在")
        if await self.repository.get_by_pair(target_student_id, course.id):
            raise AlreadyEnrolledError()
        enrolled = await self.repository.count_for_course(course.id)
        if enrolled >= course.capacity:
            raise CourseFullError()

        enrollment = Enrollment(student_id=target_student_id, course_id=course.id)
        await self.repository.add(enrollment)
        await self.session.commit()
        await self.session.refresh(enrollment)
        return self._to_read(enrollment, student, course)

    async def drop(self, enrollment_id: int, access: AccessContext) -> Message:
        """退课；已录入成绩的选课不允许退。"""
        enrollment = await self.repository.get(enrollment_id)
        if enrollment is None:
            raise NotFoundError("选课记录不存在")
        if access.scope.kind is ScopeKind.SELF:
            if enrollment.student_id != access.student_id:
                raise PermissionDeniedError("只能退选本人课程")
        elif access.scope.kind is not ScopeKind.ALL:
            raise PermissionDeniedError("教师不能代学生退课")
        if await ScoreRepository(self.session).get_by_enrollment(enrollment.id):
            raise ScoreLockedError()
        await self.repository.delete(enrollment)
        await self.session.commit()
        return Message(message="退课成功")

    @staticmethod
    def _to_read(enrollment: Enrollment, student: Student, course: Course) -> EnrollmentRead:
        return EnrollmentRead(
            id=enrollment.id,
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.name,
            course_id=course.id,
            course_code=course.code,
            course_name=course.name,
            status=enrollment.status,
            created_at=enrollment.created_at,
        )


class ScoreService:
    """成绩录入与查询。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ScoreRepository(session)

    async def record_batch(self, payload: ScoreBatch, access: AccessContext) -> list[ScoreRead]:
        """按学生+课程批量录入或更新成绩。"""
        results: list[tuple[Score, Enrollment, Student, Course]] = []
        for item in payload.items:
            enrollment = await EnrollmentRepository(self.session).get_by_pair(
                item.student_id, item.course_id
            )
            if enrollment is None:
                raise ConflictError("该学生未选此课程，无法录入成绩")
            course = await CourseRepository(self.session).get(item.course_id)
            if course is None:
                raise NotFoundError("课程不存在")
            access.ensure_course_write(course)
            student = await self.session.get(Student, item.student_id)
            if student is None:
                raise NotFoundError("学生不存在")
            score = await self.repository.get_by_enrollment(enrollment.id)
            if score is None:
                score = Score(enrollment_id=enrollment.id)
                await self.repository.add(score)
            if item.usual_score is not None:
                score.usual_score = item.usual_score
            if item.midterm_score is not None:
                score.midterm_score = item.midterm_score
            if item.exam_score is not None:
                score.exam_score = item.exam_score
            score.final_score = compute_final_with_scheme(
                course.grade_scheme,
                score.usual_score,
                score.midterm_score,
                score.exam_score,
            )
            score.recorded_by = access.user.id
            score.recorded_at = utc_now()
            results.append((score, enrollment, student, course))
        await self.session.commit()
        return [self._to_read(*row) for row in results]

    async def update_score(
        self, score_id: int, payload: ScoreUpdate, access: AccessContext
    ) -> ScoreRead:
        score = await self.repository.get(score_id)
        if score is None:
            raise NotFoundError("成绩不存在")
        enrollment = await self.session.get(Enrollment, score.enrollment_id)
        if enrollment is None:
            raise NotFoundError("选课记录不存在")
        course = await self.session.get(Course, enrollment.course_id)
        student = await self.session.get(Student, enrollment.student_id)
        if course is None or student is None:
            raise NotFoundError("关联的课程或学生不存在")
        access.ensure_course_write(course)
        if payload.usual_score is not None:
            score.usual_score = payload.usual_score
        if payload.midterm_score is not None:
            score.midterm_score = payload.midterm_score
        if payload.exam_score is not None:
            score.exam_score = payload.exam_score
        score.final_score = compute_final_with_scheme(
            course.grade_scheme,
            score.usual_score,
            score.midterm_score,
            score.exam_score,
        )
        score.recorded_by = access.user.id
        score.recorded_at = utc_now()
        await self.session.commit()
        return self._to_read(score, enrollment, student, course)

    async def list_scores(
        self,
        *,
        access: AccessContext,
        course_id: int | None,
        student_id: int | None,
        semester: str | None,
        page: int,
        page_size: int,
    ) -> Page[ScoreRead]:
        params = PageParams(page=page, page_size=page_size)
        course_ids: frozenset[int] | None = None
        published_only = False
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            pass
        elif scope.kind is ScopeKind.CLASSES:
            if course_id is not None and course_id not in scope.course_ids:
                raise PermissionDeniedError("只能查看本人所授课程的成绩")
            course_ids = scope.course_ids
        elif scope.kind is ScopeKind.SELF:
            student_id = access.student_id
            published_only = True
        else:
            return Page[ScoreRead](items=[], total=0, page=params.page, page_size=params.page_size)
        rows, total = await self.repository.paginated_rows(
            course_id=course_id,
            student_id=student_id,
            semester=semester,
            page=params.page,
            page_size=params.page_size,
            course_ids=course_ids,
            published_only=published_only,
        )
        return Page[ScoreRead](
            items=[self._to_read(*row) for row in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    @staticmethod
    def _to_read(
        score: Score, enrollment: Enrollment, student: Student, course: Course
    ) -> ScoreRead:
        return ScoreRead(
            id=score.id,
            enrollment_id=enrollment.id,
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.name,
            course_id=course.id,
            course_code=course.code,
            course_name=course.name,
            usual_score=score.usual_score,
            midterm_score=score.midterm_score,
            exam_score=score.exam_score,
            final_score=score.final_score,
            published=score.published,
            recorded_at=score.recorded_at,
        )
