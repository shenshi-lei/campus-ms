"""座位表服务。"""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from campus.models.school_class import SchoolClass
from campus.models.student import Student
from campus.repositories.people import SchoolClassRepository
from campus.schemas.seat import SeatAssignment, SeatItem, SeatMap, SeatUpdate
from campus.services.access import AccessContext, Permission


class SeatService:
    """班级座位表查看与调整。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.classes = SchoolClassRepository(session)

    async def seat_map(self, class_id: int, access: AccessContext) -> SeatMap:
        access.ensure(Permission.CLASS_SEAT_READ)
        school_class = await self._require_class(class_id)
        access.ensure_class(class_id)
        rows = await self.session.scalars(
            select(Student)
            .where(Student.class_id == class_id)
            .order_by(Student.seat_row, Student.seat_col, Student.student_no)
        )
        placed = [
            item
            for item in rows.all()
            if item.seat_no is not None and item.seat_row is not None and item.seat_col is not None
        ]
        cols = max([item.seat_col or 0 for item in placed] + [8])
        base_rows = max(4, math.ceil((school_class.capacity or len(placed) or 1) / cols))
        grid_rows = max([item.seat_row or 0 for item in placed] + [base_rows])
        return SeatMap(
            class_id=school_class.id,
            class_name=school_class.name,
            rows=grid_rows,
            cols=cols,
            seats=[
                SeatItem(
                    seat_no=item.seat_no or 0,
                    seat_row=item.seat_row or 0,
                    seat_col=item.seat_col or 0,
                    student_id=item.id,
                    student_no=item.student_no,
                    student_name=item.name,
                    class_role=str(item.class_role.value),
                )
                for item in placed
            ],
        )

    async def update_seats(
        self, class_id: int, payload: SeatUpdate, access: AccessContext
    ) -> SeatMap:
        access.ensure(Permission.CLASS_SEAT_MANAGE)
        await self._require_class(class_id)
        if "admin" not in access.role_codes and class_id not in access.head_class_ids:
            raise PermissionDeniedError("只有班主任可以调整本班座位")
        students = {
            item.id: item
            for item in (
                await self.session.scalars(select(Student).where(Student.class_id == class_id))
            ).all()
        }
        seen_numbers: set[int] = set()
        seen_positions: set[tuple[int, int]] = set()
        for item in payload.items:
            if item.student_id not in students:
                raise NotFoundError("学生不属于该班级")
            if item.seat_no in seen_numbers:
                raise ConflictError("座位号重复")
            if (item.seat_row, item.seat_col) in seen_positions:
                raise ConflictError("座位位置重复")
            if item.seat_col > 8:
                raise ConflictError("座位列不能超过 8")
            seen_numbers.add(item.seat_no)
            seen_positions.add((item.seat_row, item.seat_col))
        for item in payload.items:
            self._apply(students[item.student_id], item)
        await self.session.commit()
        return await self.seat_map(class_id, access)

    @staticmethod
    def _apply(student: Student, item: SeatAssignment) -> None:
        student.seat_no = item.seat_no
        student.seat_row = item.seat_row
        student.seat_col = item.seat_col

    async def _require_class(self, class_id: int) -> SchoolClass:
        school_class = await self.classes.get(class_id)
        if school_class is None:
            raise NotFoundError("班级不存在")
        return school_class
