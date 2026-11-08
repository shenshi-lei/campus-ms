"""报表仓储：教师工作量、学科与班级聚合。"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.models.attendance import Attendance
from campus.models.course import Course
from campus.models.enrollment import Enrollment
from campus.models.enums import AttendanceStatus, FeeStatus
from campus.models.fee import Fee
from campus.models.org import Subject
from campus.models.schedule import Schedule
from campus.models.school_class import SchoolClass
from campus.models.score import Score
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.teaching import CourseTeacher


class ReportRepository:
    """跨表统计查询。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def workload_data(
        self,
    ) -> tuple[
        list[Teacher],
        dict[int, set[int]],
        dict[int, int],
        dict[int, int],
        dict[int, int],
        dict[int, int],
    ]:
        teachers = list(
            (
                await self.session.scalars(
                    select(Teacher).where(Teacher.is_active.is_(True)).order_by(Teacher.teacher_no)
                )
            ).all()
        )
        links: dict[int, set[int]] = {}
        for course_id, teacher_id in (
            await self.session.execute(
                select(Course.id, Course.teacher_id).where(Course.teacher_id.is_not(None))
            )
        ).all():
            if teacher_id is not None:
                links.setdefault(int(teacher_id), set()).add(int(course_id))
        for teacher_id, course_id in (
            await self.session.execute(select(CourseTeacher.teacher_id, CourseTeacher.course_id))
        ).all():
            links.setdefault(int(teacher_id), set()).add(int(course_id))

        hours = {
            int(course_id): int(value or 0)
            for course_id, value in (
                await self.session.execute(select(Course.id, Course.hours))
            ).all()
        }
        periods = {
            int(course_id): int(value or 0)
            for course_id, value in (
                await self.session.execute(
                    select(
                        Schedule.course_id,
                        func.sum(Schedule.end_period - Schedule.start_period + 1),
                    ).group_by(Schedule.course_id)
                )
            ).all()
        }
        student_counts = {
            int(course_id): int(value or 0)
            for course_id, value in (
                await self.session.execute(
                    select(
                        Enrollment.course_id,
                        func.count(func.distinct(Enrollment.student_id)),
                    ).group_by(Enrollment.course_id)
                )
            ).all()
        }
        class_counts = {
            int(course_id): int(value or 0)
            for course_id, value in (
                await self.session.execute(
                    select(
                        Enrollment.course_id,
                        func.count(func.distinct(Student.class_id)),
                    )
                    .join(Student, Enrollment.student_id == Student.id)
                    .where(Student.class_id.is_not(None))
                    .group_by(Enrollment.course_id)
                )
            ).all()
        }
        return teachers, links, hours, periods, student_counts, class_counts

    async def subject_names(self) -> dict[int, str]:
        rows = await self.session.execute(select(Subject.id, Subject.name))
        return {int(subject_id): str(name) for subject_id, name in rows.all()}

    async def subject_rows(
        self, course_ids: frozenset[int] | None = None
    ) -> list[tuple[int | None, str | None, int, int, float | None, int, int]]:
        statement = (
            select(
                Course.subject_id,
                Subject.name,
                func.count(func.distinct(Course.id)),
                func.count(func.distinct(Enrollment.student_id)),
                func.avg(Score.final_score),
                func.count(Score.final_score),
                func.sum(case((Score.final_score >= 60, 1), else_=0)),
            )
            .join(Subject, Course.subject_id == Subject.id)
            .outerjoin(Enrollment, Enrollment.course_id == Course.id)
            .outerjoin(Score, Score.enrollment_id == Enrollment.id)
            .group_by(Course.subject_id, Subject.name)
        )
        if course_ids is not None:
            statement = statement.where(Course.id.in_(course_ids))
        rows = (await self.session.execute(statement)).all()
        return [
            (
                row[0],
                row[1],
                int(row[2] or 0),
                int(row[3] or 0),
                float(row[4]) if row[4] is not None else None,
                int(row[5] or 0),
                int(row[6] or 0),
            )
            for row in rows
        ]

    async def class_rows(
        self, class_ids: frozenset[int] | None = None
    ) -> list[tuple[SchoolClass, int, float | None, float, float]]:
        statement = select(SchoolClass).order_by(SchoolClass.name)
        if class_ids is not None:
            statement = statement.where(SchoolClass.id.in_(class_ids))
        classes = list((await self.session.scalars(statement)).all())
        student_counts = {
            int(class_id): int(total or 0)
            for class_id, total in (
                await self.session.execute(
                    select(Student.class_id, func.count(Student.id))
                    .where(Student.class_id.is_not(None))
                    .group_by(Student.class_id)
                )
            ).all()
            if class_id is not None
        }
        averages = {
            int(class_id): float(value or 0.0)
            for class_id, value in (
                await self.session.execute(
                    select(Student.class_id, func.avg(Score.final_score))
                    .join(Enrollment, Enrollment.student_id == Student.id)
                    .join(Score, Score.enrollment_id == Enrollment.id)
                    .where(Student.class_id.is_not(None), Score.final_score.is_not(None))
                    .group_by(Student.class_id)
                )
            ).all()
            if class_id is not None
        }
        attendance = {
            int(class_id): float(present * 100.0 / total)
            for class_id, present, total in (
                await self.session.execute(
                    select(
                        Student.class_id,
                        func.sum(
                            case(
                                (
                                    Attendance.status.in_(
                                        [AttendanceStatus.PRESENT, AttendanceStatus.LATE]
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        func.count(Attendance.id),
                    )
                    .join(Attendance, Attendance.student_id == Student.id)
                    .where(Student.class_id.is_not(None))
                    .group_by(Student.class_id)
                )
            ).all()
            if total and class_id is not None
        }
        collection = {
            int(class_id): float(paid * 100.0 / total)
            for class_id, paid, total in (
                await self.session.execute(
                    select(
                        Student.class_id,
                        func.coalesce(
                            func.sum(case((Fee.status == FeeStatus.PAID, Fee.amount), else_=0)),
                            0.0,
                        ),
                        func.coalesce(func.sum(Fee.amount), 0.0),
                    )
                    .join(Fee, Fee.student_id == Student.id)
                    .where(Student.class_id.is_not(None))
                    .group_by(Student.class_id)
                )
            ).all()
            if total and class_id is not None
        }
        return [
            (
                school_class,
                student_counts.get(school_class.id, 0),
                averages.get(school_class.id),
                attendance.get(school_class.id, 0.0),
                collection.get(school_class.id, 0.0),
            )
            for school_class in classes
        ]
