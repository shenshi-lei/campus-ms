"""导入导出服务：CSV/Excel/PDF 导出与 CSV 导入。"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from openpyxl import Workbook  # type: ignore[import-untyped]
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4, landscape  # type: ignore[import-untyped]
from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.models.attendance import Attendance
from campus.models.audit import AuditLog
from campus.models.course import Course
from campus.models.enrollment import Enrollment
from campus.models.enums import (
    ClassRole,
    Gender,
    ResidenceType,
    StudentStatus,
)
from campus.models.fee import Fee
from campus.models.leave import LeaveRequest
from campus.models.schedule import Schedule
from campus.models.school_class import SchoolClass
from campus.models.score import Score
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.schemas.transfer import ImportResult
from campus.services.access import AccessContext, Permission, ScopeKind


class TransferService:
    """CSV 导出与学籍导入。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def export_students(self, access: AccessContext) -> str:
        access.ensure(Permission.STUDENT_READ)
        statement = select(Student)
        scope = access.scope
        if scope.kind is ScopeKind.CLASSES:
            statement = statement.where(Student.class_id.in_(scope.class_ids))
        elif scope.kind is ScopeKind.SELF:
            statement = statement.where(Student.id == scope.student_id)
        elif scope.kind is not ScopeKind.ALL:
            statement = statement.where(Student.id == -1)
        rows = await self.session.scalars(statement.order_by(Student.student_no))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "student_no",
                "name",
                "gender",
                "status",
                "class_id",
                "seat_no",
                "phone",
                "email",
                "enroll_date",
            ]
        )
        for student in rows.all():
            writer.writerow(
                [
                    student.student_no,
                    student.name,
                    student.gender.value,
                    student.status.value,
                    student.class_id or "",
                    student.seat_no or "",
                    student.phone or "",
                    student.email or "",
                    student.enroll_date.isoformat() if student.enroll_date else "",
                ]
            )
        return "\ufeff" + buffer.getvalue()

    async def export_scores(self, access: AccessContext) -> str:
        access.ensure(Permission.SCORE_READ)
        statement = (
            select(Score, Student, Course)
            .join(Enrollment, Score.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Course, Enrollment.course_id == Course.id)
        )
        scope = access.scope
        if scope.kind is ScopeKind.CLASSES:
            statement = statement.where(Enrollment.course_id.in_(scope.course_ids))
        elif scope.kind is ScopeKind.SELF:
            statement = statement.where(
                Enrollment.student_id == scope.student_id, Score.published.is_(True)
            )
        elif scope.kind is not ScopeKind.ALL:
            statement = statement.where(Student.id == -1)
        result = await self.session.execute(statement.order_by(Student.student_no, Course.code))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "student_no",
                "student_name",
                "course_code",
                "course_name",
                "usual_score",
                "midterm_score",
                "exam_score",
                "final_score",
                "published",
            ]
        )
        for score, student, course in result.all():
            writer.writerow(
                [
                    student.student_no,
                    student.name,
                    course.code,
                    course.name,
                    score.usual_score if score.usual_score is not None else "",
                    score.midterm_score if score.midterm_score is not None else "",
                    score.exam_score if score.exam_score is not None else "",
                    score.final_score if score.final_score is not None else "",
                    "1" if score.published else "0",
                ]
            )
        return "\ufeff" + buffer.getvalue()

    async def export_attendance(self, access: AccessContext) -> str:
        access.ensure(Permission.ATTENDANCE_READ)
        statement = (
            select(Attendance, Student, Course)
            .join(Student, Attendance.student_id == Student.id)
            .join(Course, Attendance.course_id == Course.id)
        )
        scope = access.scope
        if scope.kind is ScopeKind.CLASSES:
            statement = statement.where(Attendance.course_id.in_(scope.course_ids))
        elif scope.kind is ScopeKind.SELF:
            statement = statement.where(Attendance.student_id == scope.student_id)
        elif scope.kind is not ScopeKind.ALL:
            statement = statement.where(Student.id == -1)
        result = await self.session.execute(
            statement.order_by(Attendance.date.desc(), Student.student_no)
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "student_no",
                "student_name",
                "course_code",
                "course_name",
                "date",
                "period_no",
                "status",
                "remark",
            ]
        )
        for record, student, course in result.all():
            writer.writerow(
                [
                    student.student_no,
                    student.name,
                    course.code,
                    course.name,
                    record.date.isoformat(),
                    record.period_no,
                    record.status.value,
                    record.remark or "",
                ]
            )
        return "\ufeff" + buffer.getvalue()

    async def import_students(
        self, access: AccessContext, text: str, *, dry_run: bool = False, mode: str = "upsert"
    ) -> ImportResult:
        access.ensure(Permission.STUDENT_MANAGE)
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        result = ImportResult()
        if reader.fieldnames is None or not {"student_no", "name"} <= set(reader.fieldnames):
            result.errors.append("表头必须包含 student_no 与 name")
            return result
        for index, row in enumerate(reader, start=2):
            if dry_run and len(result.preview) < 20:
                result.preview.append({key: value or "" for key, value in row.items()})
            student_no = (row.get("student_no") or "").strip()
            name = (row.get("name") or "").strip()
            if not student_no or not name:
                result.errors.append(f"第 {index} 行缺少学号或姓名")
                continue
            class_id = self._int(row.get("class_id"))
            if class_id is not None and not await self.session.get(SchoolClass, class_id):
                result.errors.append(f"第 {index} 行班级不存在：{class_id}")
                continue
            student = await self.session.scalar(
                select(Student).where(Student.student_no == student_no)
            )
            if student is None:
                student = Student(student_no=student_no, name=name)
                self.session.add(student)
                result.created += 1
            elif mode == "skip":
                result.skipped += 1
                continue
            else:
                student.name = name
                result.updated += 1
            student.gender = self._gender(row.get("gender"), student.gender)
            student.status = self._status(row.get("status"), student.status)
            student.class_role = self._class_role(row.get("class_role"), student.class_role)
            student.residence_type = self._residence(
                row.get("residence_type"), student.residence_type
            )
            if class_id is not None:
                student.class_id = class_id
            seat_no = self._int(row.get("seat_no"))
            if seat_no is not None:
                student.seat_no = seat_no
            for field in ("phone", "email", "address", "guardian_name", "guardian_phone"):
                value = (row.get(field) or "").strip()
                if value:
                    setattr(student, field, value)
        if not dry_run:
            await self.session.commit()
        return result

    async def export_resource(
        self,
        access: AccessContext,
        resource: str,
        *,
        fmt: str = "csv",
        keyword: str | None = None,
    ) -> tuple[bytes, str, str]:
        """按资源导出 CSV / XLSX / PDF。"""
        headers, rows = await self._dataset(access, resource, keyword=keyword)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        if fmt == "xlsx":
            return (
                self._render_xlsx(headers, rows, resource),
                ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                f"{resource}-{stamp}.xlsx",
            )
        if fmt == "pdf":
            return (
                self._render_pdf(headers, rows, resource),
                "application/pdf",
                (f"{resource}-{stamp}.pdf"),
            )
        return (
            self._render_csv(headers, rows),
            "text/csv; charset=utf-8",
            (f"{resource}-{stamp}.csv"),
        )

    async def template_headers(self, resource: str) -> list[str]:
        """返回导入模板表头。"""
        templates = {
            "students": ["student_no", "name", "gender", "status", "class_id", "phone", "email"],
            "teachers": [
                "teacher_no",
                "name",
                "title",
                "department",
                "subject_id",
                "phone",
                "email",
            ],
            "courses": ["code", "name", "credits", "hours", "semester", "teacher_id", "capacity"],
        }
        return templates.get(resource, [])

    @staticmethod
    def template_csv(resource: str, headers: list[str]) -> bytes:
        """生成带 BOM 的 CSV 模板。"""
        buffer = io.StringIO()
        csv.writer(buffer).writerow(headers)
        return ("\ufeff" + buffer.getvalue()).encode("utf-8")

    async def _dataset(
        self, access: AccessContext, resource: str, *, keyword: str | None = None
    ) -> tuple[list[str], list[list[str]]]:
        like = f"%{keyword}%" if keyword else None
        statement: Any
        rows: Any
        if resource == "students":
            access.ensure(Permission.STUDENT_READ)
            statement = select(Student)
            statement = self._student_scope(access, statement)
            if like:
                statement = statement.where(Student.name.like(like) | Student.student_no.like(like))
            rows = list((await self.session.scalars(statement.order_by(Student.student_no))).all())
            headers = ["学号", "姓名", "性别", "学籍状态", "班级ID", "座位号", "手机", "邮箱"]
            data = [
                [
                    item.student_no,
                    item.name,
                    item.gender.value,
                    item.status.value,
                    str(item.class_id or ""),
                    str(item.seat_no or ""),
                    item.phone or "",
                    item.email or "",
                ]
                for item in rows
            ]
            return headers, data
        if resource == "teachers":
            access.ensure(Permission.TEACHER_READ)
            statement = select(Teacher)
            if like:
                statement = statement.where(Teacher.name.like(like) | Teacher.teacher_no.like(like))
            rows = list((await self.session.scalars(statement.order_by(Teacher.teacher_no))).all())
            headers = ["工号", "姓名", "职称", "院系", "学科ID", "职务", "在职状态", "手机", "邮箱"]
            data = [
                [
                    item.teacher_no,
                    item.name,
                    item.title,
                    item.department,
                    str(item.subject_id or ""),
                    item.position,
                    item.employment_status.value,
                    item.phone or "",
                    item.email or "",
                ]
                for item in rows
            ]
            return headers, data
        if resource == "courses":
            access.ensure(Permission.COURSE_READ)
            statement = select(Course)
            if access.scope.kind is ScopeKind.CLASSES:
                statement = statement.where(Course.id.in_(access.scope.course_ids))
            if like:
                statement = statement.where(Course.name.like(like) | Course.code.like(like))
            rows = list((await self.session.scalars(statement.order_by(Course.code))).all())
            headers = ["课程代码", "课程名称", "学分", "学时", "学期", "教师ID", "容量"]
            data = [
                [
                    item.code,
                    item.name,
                    str(item.credits),
                    str(item.hours),
                    item.semester,
                    str(item.teacher_id or ""),
                    str(item.capacity),
                ]
                for item in rows
            ]
            return headers, data
        if resource == "classes":
            access.ensure(Permission.CLASS_READ)
            statement = select(SchoolClass)
            if access.scope.kind is ScopeKind.CLASSES:
                statement = statement.where(SchoolClass.id.in_(access.scope.class_ids))
            elif access.scope.kind is ScopeKind.SELF:
                student = (
                    await self.session.get(Student, access.scope.student_id)
                    if access.scope.student_id
                    else None
                )
                statement = statement.where(SchoolClass.id == (student.class_id if student else -1))
            if like:
                statement = statement.where(SchoolClass.name.like(like))
            rows = list((await self.session.scalars(statement.order_by(SchoolClass.name))).all())
            headers = ["班级", "年级", "专业", "班主任ID", "容量"]
            data = [
                [
                    item.name,
                    item.grade,
                    item.major,
                    str(item.head_teacher_id or ""),
                    str(item.capacity),
                ]
                for item in rows
            ]
            return headers, data
        if resource == "enrollments":
            access.ensure(Permission.ENROLLMENT_READ)
            statement = (
                select(Enrollment, Student, Course)
                .join(Student, Enrollment.student_id == Student.id)
                .join(Course, Enrollment.course_id == Course.id)
            )
            statement = self._academic_scope(access, statement)
            rows = (await self.session.execute(statement)).all()
            headers = ["学号", "学生", "课程代码", "课程", "状态", "选课时间"]
            data = [
                [
                    student.student_no,
                    student.name,
                    course.code,
                    course.name,
                    enrollment.status.value,
                    enrollment.created_at.isoformat() if enrollment.created_at else "",
                ]
                for enrollment, student, course in rows
            ]
            return headers, data
        if resource == "scores":
            access.ensure(Permission.SCORE_READ)
            statement = (
                select(Score, Student, Course)
                .join(Enrollment, Score.enrollment_id == Enrollment.id)
                .join(Student, Enrollment.student_id == Student.id)
                .join(Course, Enrollment.course_id == Course.id)
            )
            statement = self._academic_scope(access, statement, self_only_published=True)
            rows = (await self.session.execute(statement)).all()
            headers = [
                "学号",
                "学生",
                "课程代码",
                "课程",
                "平时分",
                "期中分",
                "考试分",
                "总评",
                "已发布",
            ]
            data = [
                [
                    student.student_no,
                    student.name,
                    course.code,
                    course.name,
                    str(score.usual_score if score.usual_score is not None else ""),
                    str(score.midterm_score if score.midterm_score is not None else ""),
                    str(score.exam_score if score.exam_score is not None else ""),
                    str(score.final_score if score.final_score is not None else ""),
                    "1" if score.published else "0",
                ]
                for score, student, course in rows
            ]
            return headers, data
        if resource == "attendance":
            access.ensure(Permission.ATTENDANCE_READ)
            statement = (
                select(Attendance, Student, Course)
                .join(Student, Attendance.student_id == Student.id)
                .join(Course, Attendance.course_id == Course.id)
            )
            statement = self._academic_scope(access, statement)
            rows = (await self.session.execute(statement)).all()
            headers = ["学号", "学生", "课程代码", "课程", "日期", "节次", "状态", "备注"]
            data = [
                [
                    student.student_no,
                    student.name,
                    course.code,
                    course.name,
                    record.date.isoformat(),
                    str(record.period_no),
                    record.status.value,
                    record.remark or "",
                ]
                for record, student, course in rows
            ]
            return headers, data
        if resource == "leaves":
            access.ensure(Permission.LEAVE_READ)
            statement = (
                select(LeaveRequest, Student, Teacher)
                .outerjoin(Student, LeaveRequest.student_id == Student.id)
                .outerjoin(Teacher, LeaveRequest.teacher_id == Teacher.id)
            )
            statement = self._leave_scope(access, statement)
            rows = (await self.session.execute(statement)).all()
            headers = ["申请人", "类型", "开始", "结束", "天数", "状态", "流程", "原因"]
            data = [
                [
                    (student.name if student else teacher.name if teacher else ""),
                    request.leave_type.value,
                    request.start_at.isoformat(),
                    request.end_at.isoformat(),
                    str(request.days),
                    request.status.value,
                    request.flow_name,
                    request.reason,
                ]
                for request, student, teacher in rows
            ]
            return headers, data
        if resource == "fees":
            access.ensure(Permission.FEE_READ)
            statement = select(Fee, Student).join(Student, Fee.student_id == Student.id)
            if access.scope.kind is ScopeKind.SELF:
                statement = statement.where(Fee.student_id == access.scope.student_id)
            elif access.scope.kind is ScopeKind.CLASSES:
                statement = statement.where(Student.class_id.in_(access.scope.class_ids))
            rows = (await self.session.execute(statement)).all()
            headers = ["学号", "学生", "项目", "金额", "截止日期", "状态", "缴费时间"]
            data = [
                [
                    student.student_no,
                    student.name,
                    fee.item,
                    f"{float(fee.amount):.2f}",
                    fee.due_date.isoformat(),
                    fee.status.value,
                    fee.paid_at.isoformat() if fee.paid_at else "",
                ]
                for fee, student in rows
            ]
            return headers, data
        if resource == "schedules":
            access.ensure(Permission.SCHEDULE_READ)
            statement = select(Schedule, Course).join(Course, Schedule.course_id == Course.id)
            if access.scope.kind is ScopeKind.SELF and access.student_id:
                statement = statement.join(
                    Enrollment, Enrollment.course_id == Schedule.course_id
                ).where(Enrollment.student_id == access.student_id)
            elif access.scope.kind is ScopeKind.CLASSES:
                statement = statement.where(Schedule.course_id.in_(access.scope.course_ids))
            rows = (await self.session.execute(statement)).all()
            headers = ["星期", "节次", "课程代码", "课程", "教室", "周次", "状态"]
            data = [
                [
                    str(schedule.weekday),
                    f"{schedule.start_period}-{schedule.end_period}",
                    course.code,
                    course.name,
                    schedule.classroom,
                    schedule.weeks,
                    schedule.status.value,
                ]
                for schedule, course in rows
            ]
            return headers, data
        if resource == "audit":
            access.ensure(Permission.AUDIT_READ)
            statement = select(AuditLog)
            if like:
                statement = statement.where(AuditLog.path.like(like))
            rows = list(
                (await self.session.scalars(statement.order_by(AuditLog.created_at.desc()))).all()
            )
            headers = ["时间", "用户", "角色", "方法", "路径", "状态码", "详情"]
            data = [
                [
                    item.created_at.isoformat(),
                    item.username,
                    item.role,
                    item.method,
                    item.path,
                    str(item.status_code),
                    item.detail,
                ]
                for item in rows
            ]
            return headers, data
        raise ValueError(f"不支持的导出资源：{resource}")

    def _student_scope(self, access: AccessContext, statement: Any) -> Any:
        if access.scope.kind is ScopeKind.CLASSES:
            return statement.where(Student.class_id.in_(access.scope.class_ids))
        if access.scope.kind is ScopeKind.SELF:
            return statement.where(Student.id == access.scope.student_id)
        if access.scope.kind is not ScopeKind.ALL:
            return statement.where(Student.id == -1)
        return statement

    def _academic_scope(
        self, access: AccessContext, statement: Any, *, self_only_published: bool = False
    ) -> Any:
        if access.scope.kind is ScopeKind.CLASSES:
            return statement.where(Enrollment.course_id.in_(access.scope.course_ids))
        if access.scope.kind is ScopeKind.SELF:
            statement = statement.where(Enrollment.student_id == access.scope.student_id)
            if self_only_published:
                statement = statement.where(Score.published.is_(True))
            return statement
        if access.scope.kind is not ScopeKind.ALL:
            return statement.where(Student.id == -1)
        return statement

    def _leave_scope(self, access: AccessContext, statement: Any) -> Any:
        if access.scope.kind is ScopeKind.SELF:
            if access.student_id is not None:
                return statement.where(LeaveRequest.student_id == access.student_id)
            return statement.where(LeaveRequest.teacher_id == access.teacher_id)
        if access.scope.kind is ScopeKind.CLASSES:
            return statement.where(Student.class_id.in_(access.scope.class_ids))
        if access.scope.kind is not ScopeKind.ALL:
            return statement.where(LeaveRequest.id == -1)
        return statement

    @staticmethod
    def _render_csv(headers: list[str], rows: list[list[str]]) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        return ("\ufeff" + buffer.getvalue()).encode("utf-8")

    @staticmethod
    def _render_xlsx(headers: list[str], rows: list[list[str]], title: str) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = title[:30] or "Sheet1"
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        for index, header in enumerate(headers, start=1):
            width = max(12, min(36, len(header) * 2 + 6))
            sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _render_pdf(headers: list[str], rows: list[list[str]], title: str) -> bytes:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        buffer = io.BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=24,
            rightMargin=24,
            topMargin=28,
            bottomMargin=24,
            title=title,
        )
        styles = getSampleStyleSheet()
        styles["Title"].fontName = "STSong-Light"
        styles["Title"].fontSize = 16
        story: list[Any] = [
            Paragraph(title, styles["Title"]),
            Spacer(1, 8),
        ]
        table_data = [headers, *rows]
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8fafc")],
                    ),
                ]
            )
        )
        story.append(table)
        document.build(story)
        return buffer.getvalue()

    @staticmethod
    def _int(value: str | None) -> int | None:
        if value is None or not value.strip():
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _gender(value: str | None, current: Gender) -> Gender:
        try:
            return Gender((value or "").strip())
        except ValueError:
            return current

    @staticmethod
    def _status(value: str | None, current: StudentStatus) -> StudentStatus:
        try:
            return StudentStatus((value or "").strip())
        except ValueError:
            return current

    @staticmethod
    def _class_role(value: str | None, current: ClassRole) -> ClassRole:
        try:
            return ClassRole((value or "").strip())
        except ValueError:
            return current

    @staticmethod
    def _residence(value: str | None, current: ResidenceType) -> ResidenceType:
        try:
            return ResidenceType((value or "").strip())
        except ValueError:
            return current
