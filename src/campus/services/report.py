"""报表服务：教师工作量、学科分析与班级对比。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import PermissionDeniedError
from campus.repositories.report import ReportRepository
from campus.schemas.report import (
    ClassReportItem,
    SubjectReportItem,
    WorkloadItem,
)
from campus.services.access import AccessContext, Permission, ScopeKind


class ReportService:
    """管理与教学报表。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ReportRepository(session)

    async def workload(self, access: AccessContext) -> list[WorkloadItem]:
        access.ensure(Permission.DASHBOARD_READ)
        if access.teacher_id is None and "admin" not in access.role_codes:
            raise PermissionDeniedError("仅教师或管理员可查看工作量")
        (
            teachers,
            links,
            hours,
            periods,
            student_counts,
            class_counts,
        ) = await self.repository.workload_data()
        subject_names = await self.repository.subject_names()
        target = (
            teachers
            if "admin" in access.role_codes
            else [item for item in teachers if item.id == access.teacher_id]
        )
        result: list[WorkloadItem] = []
        for teacher in target:
            course_ids = links.get(teacher.id, set())
            result.append(
                WorkloadItem(
                    teacher_id=teacher.id,
                    teacher_no=teacher.teacher_no,
                    teacher_name=teacher.name,
                    department=teacher.department,
                    subject_name=(
                        subject_names.get(teacher.subject_id)
                        if teacher.subject_id is not None
                        else None
                    ),
                    position=teacher.position,
                    course_count=len(course_ids),
                    weekly_periods=sum(periods.get(item, 0) for item in course_ids),
                    hours=sum(hours.get(item, 0) for item in course_ids),
                    student_count=sum(student_counts.get(item, 0) for item in course_ids),
                    class_count=sum(class_counts.get(item, 0) for item in course_ids),
                )
            )
        return result

    async def subjects(self, access: AccessContext) -> list[SubjectReportItem]:
        access.ensure(Permission.DASHBOARD_READ)
        course_ids = self._course_scope(access)
        rows = await self.repository.subject_rows(course_ids)
        items: list[SubjectReportItem] = []
        for subject_id, name, course_count, student_count, average, count, passed in rows:
            items.append(
                SubjectReportItem(
                    subject_id=subject_id,
                    subject_name=name or "未分类",
                    course_count=course_count,
                    student_count=student_count,
                    average_score=round(average, 1) if average is not None else None,
                    pass_rate=round(passed * 100.0 / count, 1) if count else 0.0,
                )
            )
        return sorted(items, key=lambda item: item.subject_name)

    async def classes(self, access: AccessContext) -> list[ClassReportItem]:
        access.ensure(Permission.DASHBOARD_READ)
        class_ids = self._class_scope(access)
        rows = await self.repository.class_rows(class_ids)
        return [
            ClassReportItem(
                class_id=school_class.id,
                class_name=school_class.name,
                student_count=students,
                average_score=round(average, 1) if average is not None else None,
                attendance_rate=round(attendance, 1),
                collection_rate=round(collection, 1),
            )
            for school_class, students, average, attendance, collection in rows
        ]

    @staticmethod
    def _course_scope(access: AccessContext) -> frozenset[int] | None:
        if "admin" in access.role_codes:
            return None
        if access.scope.kind is ScopeKind.CLASSES:
            return access.scope.course_ids
        raise PermissionDeniedError("仅教师或管理员可查看学科报表")

    @staticmethod
    def _class_scope(access: AccessContext) -> frozenset[int] | None:
        if "admin" in access.role_codes:
            return None
        if access.scope.kind is ScopeKind.CLASSES:
            return access.scope.class_ids
        raise PermissionDeniedError("仅教师或管理员可查看班级报表")
