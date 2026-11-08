"""组织仓储：院系、学科与学期。"""

from __future__ import annotations

from sqlalchemy import select, update

from campus.models.org import Department, Semester, Subject
from campus.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    """院系/处室查询。"""

    model = Department

    async def list_all(self) -> list[Department]:
        rows = await self.session.scalars(select(Department).order_by(Department.code))
        return list(rows.all())

    async def get_by_code(self, code: str) -> Department | None:
        return await self.session.scalar(select(Department).where(Department.code == code))

    async def get_by_name(self, name: str) -> Department | None:
        return await self.session.scalar(select(Department).where(Department.name == name))


class SubjectRepository(BaseRepository[Subject]):
    """学科查询。"""

    model = Subject

    async def list_all(self) -> list[Subject]:
        rows = await self.session.scalars(select(Subject).order_by(Subject.code))
        return list(rows.all())

    async def get_by_code(self, code: str) -> Subject | None:
        return await self.session.scalar(select(Subject).where(Subject.code == code))

    async def get_by_name(self, name: str) -> Subject | None:
        return await self.session.scalar(select(Subject).where(Subject.name == name))


class SemesterRepository(BaseRepository[Semester]):
    """学期查询。"""

    model = Semester

    async def list_all(self) -> list[Semester]:
        rows = await self.session.scalars(select(Semester).order_by(Semester.start_date.desc()))
        return list(rows.all())

    async def get_by_name(self, name: str) -> Semester | None:
        return await self.session.scalar(select(Semester).where(Semester.name == name))

    async def get_current(self) -> Semester | None:
        return await self.session.scalar(select(Semester).where(Semester.is_current.is_(True)))

    async def clear_current(self, exclude_id: int | None = None) -> None:
        statement = update(Semester).where(Semester.is_current.is_(True))
        if exclude_id is not None:
            statement = statement.where(Semester.id != exclude_id)
        await self.session.execute(statement.values(is_current=False))
