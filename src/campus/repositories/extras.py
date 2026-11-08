"""扩展模块仓储：考勤、课表、宿舍、缴费。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select

from campus.models.attendance import Attendance
from campus.models.course import Course
from campus.models.dorm import Dorm, DormAssignment
from campus.models.enrollment import Enrollment
from campus.models.enums import AttendanceStatus, EnrollmentStatus, FeeStatus
from campus.models.fee import Fee
from campus.models.schedule import Schedule
from campus.models.student import Student
from campus.repositories.base import BaseRepository

AttendanceRow = tuple[Attendance, Student, Course]


class AttendanceRepository(BaseRepository[Attendance]):
    """考勤查询。"""

    model = Attendance

    async def get_one(
        self, student_id: int, course_id: int, day: date, period_no: int = 1
    ) -> Attendance | None:
        return await self.session.scalar(
            select(Attendance).where(
                Attendance.student_id == student_id,
                Attendance.course_id == course_id,
                Attendance.date == day,
                Attendance.period_no == period_no,
            )
        )

    def rows(
        self,
        *,
        course_id: int | None = None,
        student_id: int | None = None,
        day: date | None = None,
        course_ids: frozenset[int] | None = None,
    ) -> Any:
        statement = (
            select(Attendance, Student, Course)
            .join(Student, Attendance.student_id == Student.id)
            .join(Course, Attendance.course_id == Course.id)
        )
        if course_id is not None:
            statement = statement.where(Attendance.course_id == course_id)
        if course_ids is not None:
            statement = statement.where(Attendance.course_id.in_(course_ids))
        if student_id is not None:
            statement = statement.where(Attendance.student_id == student_id)
        if day is not None:
            statement = statement.where(Attendance.date == day)
        return statement.order_by(Attendance.date.desc(), Student.student_no)

    async def paginated_rows(
        self,
        *,
        course_id: int | None,
        student_id: int | None,
        day: date | None,
        page: int,
        page_size: int,
        course_ids: frozenset[int] | None = None,
    ) -> tuple[list[AttendanceRow], int]:
        statement = self.rows(
            course_id=course_id, student_id=student_id, day=day, course_ids=course_ids
        )
        count_statement = select(func.count(Attendance.id))
        if course_id is not None:
            count_statement = count_statement.where(Attendance.course_id == course_id)
        if course_ids is not None:
            count_statement = count_statement.where(Attendance.course_id.in_(course_ids))
        if student_id is not None:
            count_statement = count_statement.where(Attendance.student_id == student_id)
        if day is not None:
            count_statement = count_statement.where(Attendance.date == day)
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        rows = [(row[0], row[1], row[2]) for row in result.all()]
        return rows, total

    async def attendance_rate(self) -> float:
        total = int(await self.session.scalar(select(func.count(Attendance.id))) or 0)
        if total == 0:
            return 0.0
        present = int(
            await self.session.scalar(
                select(func.count(Attendance.id)).where(
                    Attendance.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE])
                )
            )
            or 0
        )
        return round(present * 100.0 / total, 1)

    async def daily_counts(
        self,
        *,
        days: int,
        course_ids: list[int] | None = None,
        student_id: int | None = None,
    ) -> list[tuple[date, AttendanceStatus, int]]:
        """按天与状态统计考勤记录。"""
        start = date.today() - timedelta(days=days - 1)
        statement = (
            select(Attendance.date, Attendance.status, func.count(Attendance.id))
            .where(Attendance.date >= start)
            .group_by(Attendance.date, Attendance.status)
            .order_by(Attendance.date)
        )
        if course_ids is not None:
            statement = statement.where(Attendance.course_id.in_(course_ids))
        if student_id is not None:
            statement = statement.where(Attendance.student_id == student_id)
        rows = await self.session.execute(statement)
        return [(row[0], row[1], int(row[2])) for row in rows.all()]

    async def course_status_counts(
        self, *, course_ids: list[int], days: int
    ) -> list[tuple[int, AttendanceStatus, int]]:
        """按课程与状态统计考勤记录。"""
        start = date.today() - timedelta(days=days - 1)
        statement = (
            select(Attendance.course_id, Attendance.status, func.count(Attendance.id))
            .where(Attendance.course_id.in_(course_ids), Attendance.date >= start)
            .group_by(Attendance.course_id, Attendance.status)
        )
        rows = await self.session.execute(statement)
        return [(int(row[0]), row[1], int(row[2])) for row in rows.all()]

    async def class_status_counts(self) -> list[tuple[int, AttendanceStatus, int]]:
        """按班级与状态统计考勤记录。"""
        statement = (
            select(Student.class_id, Attendance.status, func.count(Attendance.id))
            .join(Student, Attendance.student_id == Student.id)
            .where(Student.class_id.is_not(None))
            .group_by(Student.class_id, Attendance.status)
        )
        rows = await self.session.execute(statement)
        return [(int(row[0] or 0), row[1], int(row[2])) for row in rows.all()]

    async def absent_students(
        self,
        *,
        days: int = 14,
        course_ids: list[int] | None = None,
        limit: int = 5,
    ) -> list[tuple[Student, int]]:
        """返回指定时间窗内缺勤次数最多的学生。"""
        start = date.today() - timedelta(days=days - 1)
        statement = (
            select(Student, func.count(Attendance.id).label("absent_count"))
            .join(Attendance, Attendance.student_id == Student.id)
            .where(Attendance.status == AttendanceStatus.ABSENT, Attendance.date >= start)
            .group_by(Student.id)
            .order_by(func.count(Attendance.id).desc(), Student.student_no)
            .limit(limit)
        )
        if course_ids is not None:
            statement = statement.where(Attendance.course_id.in_(course_ids))
        rows = await self.session.execute(statement)
        return [(row[0], int(row[1])) for row in rows.all()]


class ScheduleRepository(BaseRepository[Schedule]):
    """课表查询。"""

    model = Schedule

    def rows(
        self,
        *,
        class_id: int | None = None,
        teacher_id: int | None = None,
        weekday: int | None = None,
        course_ids: frozenset[int] | None = None,
        student_id: int | None = None,
    ) -> Any:
        statement = select(Schedule, Course).join(Course, Schedule.course_id == Course.id)
        if student_id is not None:
            statement = (
                statement.join(Enrollment, Enrollment.course_id == Schedule.course_id)
                .where(
                    Enrollment.student_id == student_id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
                .distinct()
            )
        if class_id is not None:
            statement = (
                statement.join(Enrollment, Enrollment.course_id == Schedule.course_id)
                .join(Student, Student.id == Enrollment.student_id)
                .where(
                    Student.class_id == class_id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
                .distinct()
            )
        if teacher_id is not None:
            statement = statement.where(Course.teacher_id == teacher_id)
        if course_ids is not None:
            statement = statement.where(Schedule.course_id.in_(course_ids))
        if weekday is not None:
            statement = statement.where(Schedule.weekday == weekday)
        return statement.order_by(Schedule.weekday, Schedule.start_period)

    async def paginated_rows(
        self,
        *,
        class_id: int | None,
        teacher_id: int | None,
        weekday: int | None,
        page: int,
        page_size: int,
        course_ids: frozenset[int] | None = None,
        student_id: int | None = None,
    ) -> tuple[list[tuple[Schedule, Course]], int]:
        statement = self.rows(
            class_id=class_id,
            teacher_id=teacher_id,
            weekday=weekday,
            course_ids=course_ids,
            student_id=student_id,
        )
        count_statement = (
            select(func.count(func.distinct(Schedule.id)))
            .select_from(Schedule)
            .join(Course, Schedule.course_id == Course.id)
        )
        if student_id is not None:
            count_statement = count_statement.join(
                Enrollment, Enrollment.course_id == Schedule.course_id
            ).where(
                Enrollment.student_id == student_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
            )
        if class_id is not None:
            count_statement = (
                count_statement.join(Enrollment, Enrollment.course_id == Schedule.course_id)
                .join(Student, Student.id == Enrollment.student_id)
                .where(Student.class_id == class_id)
            )
        if teacher_id is not None:
            count_statement = count_statement.where(Course.teacher_id == teacher_id)
        if course_ids is not None:
            count_statement = count_statement.where(Schedule.course_id.in_(course_ids))
        if weekday is not None:
            count_statement = count_statement.where(Schedule.weekday == weekday)
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        rows = [(row[0], row[1]) for row in result.all()]
        return rows, total

    async def for_student(self, student_id: int, weekday: int) -> list[tuple[Schedule, Course]]:
        """返回某学生某天的课表。"""
        statement = (
            select(Schedule, Course)
            .join(Course, Schedule.course_id == Course.id)
            .join(Enrollment, Enrollment.course_id == Schedule.course_id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
                Schedule.weekday == weekday,
            )
            .distinct()
            .order_by(Schedule.start_period)
        )
        result = await self.session.execute(statement)
        return [(row[0], row[1]) for row in result.all()]

    async def for_teacher(self, teacher_id: int, weekday: int) -> list[tuple[Schedule, Course]]:
        """返回某教师某天的课表。"""
        statement = (
            select(Schedule, Course)
            .join(Course, Schedule.course_id == Course.id)
            .where(Course.teacher_id == teacher_id, Schedule.weekday == weekday)
            .order_by(Schedule.start_period)
        )
        result = await self.session.execute(statement)
        return [(row[0], row[1]) for row in result.all()]


class DormRepository(BaseRepository[Dorm]):
    """宿舍房间查询。"""

    model = Dorm

    async def paginated_with_occupied(
        self, *, page: int, page_size: int, building: str | None = None
    ) -> tuple[list[tuple[Dorm, int]], int]:
        statement = (
            select(Dorm, func.count(DormAssignment.id))
            .outerjoin(DormAssignment, DormAssignment.dorm_id == Dorm.id)
            .group_by(Dorm.id)
            .order_by(Dorm.building, Dorm.room_no)
        )
        count_statement = select(func.count(Dorm.id))
        if building:
            statement = statement.where(Dorm.building == building)
            count_statement = count_statement.where(Dorm.building == building)
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        rows = [(row[0], int(row[1])) for row in result.all()]
        return rows, total

    async def get_with_occupied(self, dorm_id: int) -> tuple[Dorm, int] | None:
        statement = (
            select(Dorm, func.count(DormAssignment.id))
            .outerjoin(DormAssignment, DormAssignment.dorm_id == Dorm.id)
            .where(Dorm.id == dorm_id)
            .group_by(Dorm.id)
        )
        row = (await self.session.execute(statement)).first()
        if row is None:
            return None
        return row[0], int(row[1])


class DormAssignmentRepository(BaseRepository[DormAssignment]):
    """床位分配查询。"""

    model = DormAssignment

    async def get_by_student(self, student_id: int) -> DormAssignment | None:
        return await self.session.scalar(
            select(DormAssignment).where(DormAssignment.student_id == student_id)
        )

    async def count_for_dorm(self, dorm_id: int) -> int:
        total = await self.session.scalar(
            select(func.count(DormAssignment.id)).where(DormAssignment.dorm_id == dorm_id)
        )
        return int(total or 0)

    async def paginated_rows(
        self,
        *,
        dorm_id: int | None,
        page: int,
        page_size: int,
        class_ids: frozenset[int] | None = None,
        student_id: int | None = None,
    ) -> tuple[list[tuple[DormAssignment, Student, Dorm]], int]:
        statement = (
            select(DormAssignment, Student, Dorm)
            .join(Student, DormAssignment.student_id == Student.id)
            .join(Dorm, DormAssignment.dorm_id == Dorm.id)
        )
        count_statement = select(func.count(DormAssignment.id)).join(
            Student, DormAssignment.student_id == Student.id
        )
        if dorm_id is not None:
            statement = statement.where(DormAssignment.dorm_id == dorm_id)
            count_statement = count_statement.where(DormAssignment.dorm_id == dorm_id)
        if class_ids is not None:
            statement = statement.where(Student.class_id.in_(class_ids))
            count_statement = count_statement.where(Student.class_id.in_(class_ids))
        if student_id is not None:
            statement = statement.where(Student.id == student_id)
            count_statement = count_statement.where(Student.id == student_id)
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            statement.order_by(Dorm.building, Dorm.room_no, DormAssignment.bed_no)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [(row[0], row[1], row[2]) for row in result.all()]
        return rows, total


class FeeRepository(BaseRepository[Fee]):
    """缴费查询。"""

    model = Fee

    def rows(self, *, student_id: int | None = None, status: FeeStatus | None = None) -> Any:
        statement = select(Fee, Student).join(Student, Fee.student_id == Student.id)
        if student_id is not None:
            statement = statement.where(Fee.student_id == student_id)
        if status is not None:
            statement = statement.where(Fee.status == status)
        return statement.order_by(Fee.due_date.desc(), Fee.id.desc())

    async def paginated_rows(
        self,
        *,
        student_id: int | None,
        status: FeeStatus | None,
        page: int,
        page_size: int,
        class_ids: frozenset[int] | None = None,
    ) -> tuple[list[tuple[Fee, Student]], int]:
        statement = self.rows(student_id=student_id, status=status)
        count_statement = select(func.count(Fee.id)).join(Student, Fee.student_id == Student.id)
        if student_id is not None:
            count_statement = count_statement.where(Fee.student_id == student_id)
        if status is not None:
            count_statement = count_statement.where(Fee.status == status)
        if class_ids is not None:
            statement = statement.where(Student.class_id.in_(class_ids))
            count_statement = count_statement.where(Student.class_id.in_(class_ids))
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        rows = [(row[0], row[1]) for row in result.all()]
        return rows, total

    async def unpaid_summary(self) -> tuple[int, float]:
        count = int(
            await self.session.scalar(
                select(func.count(Fee.id)).where(Fee.status == FeeStatus.UNPAID)
            )
            or 0
        )
        amount = await self.session.scalar(
            select(func.coalesce(func.sum(Fee.amount), 0.0)).where(Fee.status == FeeStatus.UNPAID)
        )
        return count, float(amount or 0.0)

    async def status_breakdown(
        self, *, student_id: int | None = None
    ) -> list[tuple[FeeStatus, int, float]]:
        """按状态统计费用笔数与金额。"""
        statement = select(
            Fee.status, func.count(Fee.id), func.coalesce(func.sum(Fee.amount), 0.0)
        ).group_by(Fee.status)
        if student_id is not None:
            statement = statement.where(Fee.student_id == student_id)
        rows = await self.session.execute(statement)
        return [(row[0], int(row[1]), float(row[2])) for row in rows.all()]

    async def overdue_summary(
        self, *, today: date, student_id: int | None = None
    ) -> tuple[int, float]:
        """统计已过截止日期且未缴的费用。"""
        conditions = [Fee.status == FeeStatus.UNPAID, Fee.due_date < today]
        if student_id is not None:
            conditions.append(Fee.student_id == student_id)
        count = int(await self.session.scalar(select(func.count(Fee.id)).where(*conditions)) or 0)
        amount = await self.session.scalar(
            select(func.coalesce(func.sum(Fee.amount), 0.0)).where(*conditions)
        )
        return count, float(amount or 0.0)

    async def top_overdue_students(
        self, *, today: date, limit: int = 5
    ) -> list[tuple[Student, int, float]]:
        """返回逾期金额最高的学生。"""
        statement = (
            select(Student, func.count(Fee.id), func.coalesce(func.sum(Fee.amount), 0.0))
            .join(Fee, Fee.student_id == Student.id)
            .where(Fee.status == FeeStatus.UNPAID, Fee.due_date < today)
            .group_by(Student.id)
            .order_by(func.sum(Fee.amount).desc(), Student.student_no)
            .limit(limit)
        )
        rows = await self.session.execute(statement)
        return [(row[0], int(row[1]), float(row[2])) for row in rows.all()]

    async def recent_payments(
        self, *, student_id: int | None = None, limit: int = 5
    ) -> list[tuple[Fee, Student]]:
        """返回最近的缴费记录。"""
        statement = (
            select(Fee, Student)
            .join(Student, Fee.student_id == Student.id)
            .where(Fee.paid_at.is_not(None))
            .order_by(Fee.paid_at.desc(), Fee.id.desc())
            .limit(limit)
        )
        if student_id is not None:
            statement = statement.where(Fee.student_id == student_id)
        result = await self.session.execute(statement)
        return [(row[0], row[1]) for row in result.all()]
