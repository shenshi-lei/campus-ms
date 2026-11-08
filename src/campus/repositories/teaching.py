"""教学运行仓储：课程教师、面向班级与调课申请。"""

from __future__ import annotations

from sqlalchemy import Select, delete, func, select

from campus.models.course import Course
from campus.models.schedule import Schedule
from campus.models.school_class import SchoolClass
from campus.models.teacher import Teacher
from campus.models.teaching import CourseClass, CourseTeacher, ScheduleChange
from campus.repositories.base import BaseRepository


class CourseTeacherRepository(BaseRepository[CourseTeacher]):
    """课程教师关系。"""

    model = CourseTeacher

    async def list_for(self, course_id: int) -> list[tuple[CourseTeacher, Teacher]]:
        rows = await self.session.execute(
            select(CourseTeacher, Teacher)
            .join(Teacher, CourseTeacher.teacher_id == Teacher.id)
            .where(CourseTeacher.course_id == course_id)
            .order_by(CourseTeacher.id)
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def replace(self, course_id: int, items: list[tuple[int, str]]) -> None:
        await self.session.execute(
            delete(CourseTeacher).where(CourseTeacher.course_id == course_id)
        )
        for teacher_id, role in items:
            self.session.add(CourseTeacher(course_id=course_id, teacher_id=teacher_id, role=role))
        await self.session.flush()


class CourseClassRepository(BaseRepository[CourseClass]):
    """课程面向班级关系。"""

    model = CourseClass

    async def list_for(self, course_id: int) -> list[tuple[CourseClass, SchoolClass]]:
        rows = await self.session.execute(
            select(CourseClass, SchoolClass)
            .join(SchoolClass, CourseClass.class_id == SchoolClass.id)
            .where(CourseClass.course_id == course_id)
            .order_by(CourseClass.id)
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def replace(self, course_id: int, class_ids: list[int]) -> None:
        await self.session.execute(delete(CourseClass).where(CourseClass.course_id == course_id))
        for class_id in class_ids:
            self.session.add(CourseClass(course_id=course_id, class_id=class_id))
        await self.session.flush()


class ScheduleChangeRepository(BaseRepository[ScheduleChange]):
    """调课申请查询。"""

    model = ScheduleChange

    def filtered(
        self,
        *,
        status: str | None = None,
        course_ids: frozenset[int] | None = None,
    ) -> Select[ScheduleChange, Schedule, Course]:
        statement = (
            select(ScheduleChange, Schedule, Course)
            .join(Schedule, ScheduleChange.schedule_id == Schedule.id)
            .join(Course, Schedule.course_id == Course.id)
        )
        if status is not None:
            statement = statement.where(ScheduleChange.status == status)
        if course_ids is not None:
            statement = statement.where(Schedule.course_id.in_(course_ids))
        return statement.order_by(ScheduleChange.created_at.desc(), ScheduleChange.id.desc())

    async def paginated_rows(
        self,
        *,
        status: str | None,
        course_ids: frozenset[int] | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[ScheduleChange, Schedule, Course]], int]:
        statement = self.filtered(status=status, course_ids=course_ids)
        count_statement = select(func.count(ScheduleChange.id)).join(
            Schedule, ScheduleChange.schedule_id == Schedule.id
        )
        if status is not None:
            count_statement = count_statement.where(ScheduleChange.status == status)
        if course_ids is not None:
            count_statement = count_statement.where(Schedule.course_id.in_(course_ids))
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        rows = [(row[0], row[1], row[2]) for row in result.all()]
        return rows, total
