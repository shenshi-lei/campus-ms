"""教务相关仓储：课程、选课、成绩。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, case, func, or_, select, update

from campus.models.course import Course
from campus.models.enrollment import Enrollment
from campus.models.enums import EnrollmentStatus
from campus.models.schedule import Schedule
from campus.models.score import Score
from campus.models.student import Student
from campus.repositories.base import BaseRepository

ScoreRow = tuple[Score, Enrollment, Student, Course]


class CourseRepository(BaseRepository[Course]):
    """课程查询。"""

    model = Course

    def filtered(
        self,
        *,
        keyword: str | None = None,
        semester: str | None = None,
        teacher_id: int | None = None,
    ) -> Select[Any]:
        statement = select(Course)
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(or_(Course.name.like(pattern), Course.code.like(pattern)))
        if semester:
            statement = statement.where(Course.semester == semester)
        if teacher_id is not None:
            statement = statement.where(Course.teacher_id == teacher_id)
        return statement.order_by(Course.code)

    async def get_by_code(self, code: str) -> Course | None:
        return await self.session.scalar(select(Course).where(Course.code == code))

    async def count_all(self) -> int:
        total = await self.session.scalar(select(func.count(Course.id)))
        return int(total or 0)

    async def list_names(self) -> dict[int, str]:
        rows = await self.session.execute(select(Course.id, Course.name))
        return {int(row[0]): str(row[1]) for row in rows.all()}

    async def list_for_teacher(self, teacher_id: int) -> list[Course]:
        """返回某教师任教的所有课程。"""
        rows = await self.session.scalars(
            select(Course).where(Course.teacher_id == teacher_id).order_by(Course.code)
        )
        return list(rows.all())

    async def latest_semester(self) -> str | None:
        """返回课程表中最近的学期。"""
        value = await self.session.scalar(select(func.max(Course.semester)))
        return str(value) if value else None

    async def utilization(self, *, limit: int = 8) -> list[tuple[Course, int]]:
        """按选课饱和度倒序返回课程与在选人数。"""
        enrolled = func.count(Enrollment.id)
        capacity = case((Course.capacity <= 0, 1), else_=Course.capacity)
        statement = (
            select(Course, enrolled)
            .outerjoin(
                Enrollment,
                and_(
                    Enrollment.course_id == Course.id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                ),
            )
            .group_by(Course.id)
            .order_by((enrolled * 1.0 / capacity).desc(), Course.code)
            .limit(limit)
        )
        rows = await self.session.execute(statement)
        return [(row[0], int(row[1])) for row in rows.all()]

    async def count_over_capacity(self) -> int:
        """统计在选人数达到或超过容量的课程数。"""
        counts = (
            select(Enrollment.course_id, func.count(Enrollment.id).label("enrolled"))
            .where(Enrollment.status == EnrollmentStatus.ENROLLED)
            .group_by(Enrollment.course_id)
            .subquery()
        )
        total = await self.session.scalar(
            select(func.count(Course.id))
            .join(counts, counts.c.course_id == Course.id)
            .where(counts.c.enrolled >= Course.capacity)
        )
        return int(total or 0)

    async def count_without_schedule(self) -> int:
        """统计尚未排课的课程数。"""
        total = await self.session.scalar(
            select(func.count(Course.id)).where(
                ~select(Schedule.id).where(Schedule.course_id == Course.id).exists()
            )
        )
        return int(total or 0)

    async def count_without_scores(self) -> int:
        """统计有选课但尚未录入任何成绩的课程数。"""
        total = await self.session.scalar(
            select(func.count(Course.id)).where(
                ~select(Enrollment.id)
                .join(Score, Score.enrollment_id == Enrollment.id)
                .where(Enrollment.course_id == Course.id)
                .exists()
            )
        )
        return int(total or 0)


class EnrollmentRepository(BaseRepository[Enrollment]):
    """选课查询。"""

    model = Enrollment

    async def get_by_pair(self, student_id: int, course_id: int) -> Enrollment | None:
        return await self.session.scalar(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id,
            )
        )

    async def count_for_course(self, course_id: int) -> int:
        total = await self.session.scalar(
            select(func.count(Enrollment.id)).where(
                Enrollment.course_id == course_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
            )
        )
        return int(total or 0)

    async def count_all(self) -> int:
        total = await self.session.scalar(select(func.count(Enrollment.id)))
        return int(total or 0)

    def rows(
        self,
        *,
        student_id: int | None = None,
        course_id: int | None = None,
        course_ids: frozenset[int] | None = None,
    ) -> Any:
        statement = (
            select(Enrollment, Student, Course)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Course, Enrollment.course_id == Course.id)
        )
        if student_id is not None:
            statement = statement.where(Enrollment.student_id == student_id)
        if course_id is not None:
            statement = statement.where(Enrollment.course_id == course_id)
        if course_ids is not None:
            statement = statement.where(Enrollment.course_id.in_(course_ids))
        return statement.order_by(Enrollment.created_at.desc(), Enrollment.id.desc())

    async def paginated_rows(
        self,
        *,
        student_id: int | None,
        course_id: int | None,
        page: int,
        page_size: int,
        course_ids: frozenset[int] | None = None,
    ) -> tuple[list[tuple[Enrollment, Student, Course]], int]:
        statement = self.rows(student_id=student_id, course_id=course_id, course_ids=course_ids)
        count_statement = (
            select(func.count(Enrollment.id))
            .join(Student, Enrollment.student_id == Student.id)
            .join(Course, Enrollment.course_id == Course.id)
        )
        if student_id is not None:
            count_statement = count_statement.where(Enrollment.student_id == student_id)
        if course_id is not None:
            count_statement = count_statement.where(Enrollment.course_id == course_id)
        if course_ids is not None:
            count_statement = count_statement.where(Enrollment.course_id.in_(course_ids))
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        rows = [(row[0], row[1], row[2]) for row in result.all()]
        return rows, total

    async def roster(self, course_id: int) -> list[tuple[Enrollment, Student]]:
        statement = (
            select(Enrollment, Student)
            .join(Student, Enrollment.student_id == Student.id)
            .where(Enrollment.course_id == course_id)
            .order_by(Student.student_no)
        )
        result = await self.session.execute(statement)
        return [(row[0], row[1]) for row in result.all()]

    async def counts_by_course(self, *, course_ids: list[int] | None = None) -> dict[int, int]:
        """按课程统计在选人数。"""
        statement = (
            select(Enrollment.course_id, func.count(Enrollment.id))
            .where(Enrollment.status == EnrollmentStatus.ENROLLED)
            .group_by(Enrollment.course_id)
        )
        if course_ids is not None:
            statement = statement.where(Enrollment.course_id.in_(course_ids))
        rows = await self.session.execute(statement)
        return {int(row[0]): int(row[1]) for row in rows.all()}

    async def distinct_students(self, *, course_ids: list[int] | None = None) -> int:
        """统计在选学生人数（去重）。"""
        statement = select(func.count(func.distinct(Enrollment.student_id))).where(
            Enrollment.status == EnrollmentStatus.ENROLLED
        )
        if course_ids is not None:
            statement = statement.where(Enrollment.course_id.in_(course_ids))
        total = await self.session.scalar(statement)
        return int(total or 0)

    async def recent(
        self,
        *,
        student_id: int | None = None,
        course_ids: list[int] | None = None,
        limit: int = 5,
    ) -> list[tuple[Enrollment, Student, Course]]:
        """返回最近的选课记录。"""
        statement = (
            select(Enrollment, Student, Course)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Course, Enrollment.course_id == Course.id)
            .order_by(Enrollment.created_at.desc(), Enrollment.id.desc())
            .limit(limit)
        )
        if student_id is not None:
            statement = statement.where(Enrollment.student_id == student_id)
        if course_ids is not None:
            statement = statement.where(Enrollment.course_id.in_(course_ids))
        result = await self.session.execute(statement)
        return [(row[0], row[1], row[2]) for row in result.all()]


class ScoreRepository(BaseRepository[Score]):
    """成绩查询。"""

    model = Score

    async def get_by_enrollment(self, enrollment_id: int) -> Score | None:
        return await self.session.scalar(select(Score).where(Score.enrollment_id == enrollment_id))

    async def paginated_rows(
        self,
        *,
        course_id: int | None,
        student_id: int | None,
        semester: str | None,
        page: int,
        page_size: int,
        course_ids: frozenset[int] | None = None,
        published_only: bool = False,
    ) -> tuple[list[ScoreRow], int]:
        base = (
            select(Score, Enrollment, Student, Course)
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Course, Enrollment.course_id == Course.id)
        )
        count_statement = (
            select(func.count(Score.id))
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Course, Enrollment.course_id == Course.id)
        )
        conditions = []
        if course_id is not None:
            conditions.append(Enrollment.course_id == course_id)
        if course_ids is not None:
            conditions.append(Enrollment.course_id.in_(course_ids))
        if student_id is not None:
            conditions.append(Enrollment.student_id == student_id)
        if semester:
            conditions.append(Course.semester == semester)
        if published_only:
            conditions.append(Score.published.is_(True))
        for condition in conditions:
            base = base.where(condition)
            count_statement = count_statement.where(condition)
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            base.order_by(Score.recorded_at.desc(), Score.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [(row[0], row[1], row[2], row[3]) for row in result.all()]
        return rows, total

    async def average_final(self) -> float:
        value = await self.session.scalar(
            select(func.avg(Score.final_score)).where(Score.final_score.is_not(None))
        )
        return float(value or 0.0)

    async def publish_for_course(
        self, course_id: int, *, published: bool, at: datetime | None
    ) -> int:
        """发布或撤回某课程的全部成绩。"""
        enrollment_ids = select(Enrollment.id).where(Enrollment.course_id == course_id)
        result = await self.session.execute(
            update(Score)
            .where(Score.enrollment_id.in_(enrollment_ids))
            .values(published=published, published_at=at)
        )
        count = int(getattr(result, "rowcount", 0) or 0)
        return count

    async def distribution(
        self,
        *,
        student_id: int | None = None,
        course_ids: list[int] | None = None,
    ) -> list[tuple[str, int]]:
        """按分数区间统计成绩数量。"""
        bucket = case(
            (Score.final_score < 60, "<60"),
            (Score.final_score < 70, "60-69"),
            (Score.final_score < 80, "70-79"),
            (Score.final_score < 90, "80-89"),
            else_="90-100",
        ).label("bucket")
        statement = (
            select(bucket, func.count(Score.id))
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .where(Score.final_score.is_not(None))
            .group_by(bucket)
        )
        if student_id is not None:
            statement = statement.where(Enrollment.student_id == student_id)
        if course_ids is not None:
            statement = statement.where(Enrollment.course_id.in_(course_ids))
        rows = await self.session.execute(statement)
        return [(str(row[0]), int(row[1])) for row in rows.all()]

    async def summary(
        self,
        *,
        student_id: int | None = None,
        course_ids: list[int] | None = None,
    ) -> tuple[float, int, int]:
        """返回平均分、样本数与及格数。"""
        statement = (
            select(
                func.avg(Score.final_score),
                func.count(Score.id),
                func.sum(case((Score.final_score >= 60, 1), else_=0)),
            )
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .where(Score.final_score.is_not(None))
        )
        if student_id is not None:
            statement = statement.where(Enrollment.student_id == student_id)
        if course_ids is not None:
            statement = statement.where(Enrollment.course_id.in_(course_ids))
        row = (await self.session.execute(statement)).one()
        return float(row[0] or 0.0), int(row[1] or 0), int(row[2] or 0)

    async def recent(
        self,
        *,
        student_id: int | None = None,
        course_ids: list[int] | None = None,
        limit: int = 5,
    ) -> list[tuple[Score, Student, Course]]:
        """返回最近录入的成绩。"""
        statement = (
            select(Score, Student, Course)
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Course, Enrollment.course_id == Course.id)
            .order_by(Score.recorded_at.desc(), Score.id.desc())
            .limit(limit)
        )
        if student_id is not None:
            statement = statement.where(Enrollment.student_id == student_id)
        if course_ids is not None:
            statement = statement.where(Enrollment.course_id.in_(course_ids))
        result = await self.session.execute(statement)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def scores_with_credits(self, student_id: int) -> list[tuple[float, float]]:
        """返回某学生已出成绩的（总分, 学分）列表，用于 GPA 计算。"""
        rows = await self.session.execute(
            select(Score.final_score, Course.credits)
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .join(Course, Enrollment.course_id == Course.id)
            .where(Enrollment.student_id == student_id, Score.final_score.is_not(None))
        )
        return [(float(row[0] or 0.0), float(row[1] or 0.0)) for row in rows.all()]

    async def counts_by_course(self, course_ids: list[int]) -> dict[int, int]:
        """按课程统计已录入成绩的数量。"""
        rows = await self.session.execute(
            select(Enrollment.course_id, func.count(Score.id))
            .join(Score, Score.enrollment_id == Enrollment.id)
            .where(Enrollment.course_id.in_(course_ids))
            .group_by(Enrollment.course_id)
        )
        return {int(row[0]): int(row[1]) for row in rows.all()}

    async def average_by_class(self) -> dict[int, float]:
        """按班级统计平均总分。"""
        rows = await self.session.execute(
            select(Student.class_id, func.avg(Score.final_score))
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .where(Score.final_score.is_not(None), Student.class_id.is_not(None))
            .group_by(Student.class_id)
        )
        return {int(row[0]): float(row[1]) for row in rows.all()}

    async def failed_count(self, student_id: int) -> int:
        """统计某学生不及格课程数。"""
        total = await self.session.scalar(
            select(func.count(Score.id))
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .where(
                Enrollment.student_id == student_id,
                Score.final_score.is_not(None),
                Score.final_score < 60,
            )
        )
        return int(total or 0)
