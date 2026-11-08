"""人员相关仓储：学生、教师、班级。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, or_, select

from campus.models.school_class import SchoolClass
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.repositories.base import BaseRepository


class StudentRepository(BaseRepository[Student]):
    """学生查询。"""

    model = Student

    def filtered(
        self,
        *,
        keyword: str | None = None,
        class_id: int | None = None,
        is_active: bool | None = None,
        class_ids: frozenset[int] | None = None,
        student_id: int | None = None,
    ) -> Select[Any]:
        statement = select(Student)
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(Student.name.like(pattern), Student.student_no.like(pattern))
            )
        if class_id is not None:
            statement = statement.where(Student.class_id == class_id)
        if class_ids is not None:
            statement = statement.where(Student.class_id.in_(class_ids))
        if student_id is not None:
            statement = statement.where(Student.id == student_id)
        if is_active is not None:
            statement = statement.where(Student.is_active.is_(is_active))
        return statement.order_by(Student.student_no)

    async def get_by_no(self, student_no: str) -> Student | None:
        return await self.session.scalar(select(Student).where(Student.student_no == student_no))

    async def get_by_user(self, user_id: int) -> Student | None:
        return await self.session.scalar(select(Student).where(Student.user_id == user_id))

    async def count_active(self) -> int:
        total = await self.session.scalar(
            select(func.count(Student.id)).where(Student.is_active.is_(True))
        )
        return int(total or 0)

    async def count_by_class(self) -> dict[int, int]:
        """按班级统计在册学生人数。"""
        rows = await self.session.execute(
            select(Student.class_id, func.count(Student.id))
            .where(Student.class_id.is_not(None), Student.is_active.is_(True))
            .group_by(Student.class_id)
        )
        counts: dict[int, int] = {}
        for class_id, total in rows.all():
            if class_id is None:
                continue
            counts[int(class_id)] = int(total)
        return counts


class TeacherRepository(BaseRepository[Teacher]):
    """教师查询。"""

    model = Teacher

    def filtered(self, *, keyword: str | None = None, department: str | None = None) -> Select[Any]:
        statement = select(Teacher)
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(Teacher.name.like(pattern), Teacher.teacher_no.like(pattern))
            )
        if department:
            statement = statement.where(Teacher.department == department)
        return statement.order_by(Teacher.teacher_no)

    async def get_by_no(self, teacher_no: str) -> Teacher | None:
        return await self.session.scalar(select(Teacher).where(Teacher.teacher_no == teacher_no))

    async def get_by_user(self, user_id: int) -> Teacher | None:
        return await self.session.scalar(select(Teacher).where(Teacher.user_id == user_id))

    async def count_active(self) -> int:
        total = await self.session.scalar(
            select(func.count(Teacher.id)).where(Teacher.is_active.is_(True))
        )
        return int(total or 0)

    async def list_names(self) -> dict[int, str]:
        """返回教师 ID 到姓名的映射。"""
        rows = await self.session.execute(select(Teacher.id, Teacher.name))
        return {int(row[0]): str(row[1]) for row in rows.all()}


class SchoolClassRepository(BaseRepository[SchoolClass]):
    """班级查询。"""

    model = SchoolClass

    async def list_all(self) -> list[SchoolClass]:
        rows = await self.session.scalars(select(SchoolClass).order_by(SchoolClass.name))
        return list(rows.all())

    async def get_by_name(self, name: str) -> SchoolClass | None:
        return await self.session.scalar(select(SchoolClass).where(SchoolClass.name == name))

    async def count_students(self, class_id: int) -> int:
        total = await self.session.scalar(
            select(func.count(Student.id)).where(Student.class_id == class_id)
        )
        return int(total or 0)

    async def count_all(self) -> int:
        total = await self.session.scalar(select(func.count(SchoolClass.id)))
        return int(total or 0)
