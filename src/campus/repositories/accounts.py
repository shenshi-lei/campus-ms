"""账号仓储：用户与档案姓名联表。"""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select

from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.user import User
from campus.repositories.base import BaseRepository


class AccountRepository(BaseRepository[User]):
    """账号查询。"""

    model = User

    def filtered(self, *, keyword: str | None = None) -> Select[User, str, str]:
        statement = (
            select(User, Student.name, Teacher.name)
            .outerjoin(Student, Student.user_id == User.id)
            .outerjoin(Teacher, Teacher.user_id == User.id)
        )
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    User.username.like(pattern),
                    Student.name.like(pattern),
                    Teacher.name.like(pattern),
                )
            )
        return statement.order_by(User.id)

    async def get_with_names(self, user_id: int) -> tuple[User, str | None, str | None] | None:
        statement = (
            select(User, Student.name, Teacher.name)
            .outerjoin(Student, Student.user_id == User.id)
            .outerjoin(Teacher, Teacher.user_id == User.id)
            .where(User.id == user_id)
        )
        row = (await self.session.execute(statement)).first()
        if row is None:
            return None
        return row[0], row[1], row[2]

    async def paginated_rows(
        self, *, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[tuple[User, str, str]], int]:
        statement = self.filtered(keyword=keyword)
        count_statement = select(func.count()).select_from(statement.subquery())
        total = int(await self.session.scalar(count_statement) or 0)
        result = await self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        rows = [(row[0], row[1], row[2]) for row in result.all()]
        return rows, total
