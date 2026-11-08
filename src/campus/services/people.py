"""人员服务：学生、教师、班级。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import (
    ConflictError,
    DuplicateKeyError,
    NotFoundError,
    PermissionDeniedError,
    ReferenceExistsError,
)
from campus.core.pagination import PageParams
from campus.models.course import Course
from campus.models.enrollment import Enrollment
from campus.models.leave import StudentStatusHistory
from campus.models.school_class import SchoolClass
from campus.models.score import Score
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.repositories.leave import StudentStatusRepository
from campus.repositories.org import DepartmentRepository, SubjectRepository
from campus.repositories.people import (
    SchoolClassRepository,
    StudentRepository,
    TeacherRepository,
)
from campus.schemas.common import Message, Page
from campus.schemas.school_class import (
    SchoolClassCreate,
    SchoolClassRead,
    SchoolClassUpdate,
)
from campus.schemas.student import (
    StudentCreate,
    StudentRead,
    StudentUpdate,
    TranscriptItem,
)
from campus.schemas.student_status import (
    StudentStatusChange,
    StudentStatusHistoryRead,
)
from campus.schemas.teacher import TeacherCreate, TeacherRead, TeacherUpdate
from campus.services.access import AccessContext, FieldLevel, Permission, ScopeKind


class StudentService:
    """学生档案与成绩单。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = StudentRepository(session)

    async def list_students(
        self,
        *,
        access: AccessContext,
        keyword: str | None = None,
        class_id: int | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[StudentRead]:
        params = PageParams(page=page, page_size=page_size)
        class_ids: frozenset[int] | None = None
        student_id: int | None = None
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            pass
        elif scope.kind is ScopeKind.CLASSES:
            if class_id is not None:
                if class_id not in scope.class_ids:
                    raise PermissionDeniedError("只能查看权限范围内的班级")
                class_ids = frozenset({class_id})
            else:
                class_ids = scope.class_ids
        else:
            student_id = access.student_id
            if student_id is None:
                return Page[StudentRead](
                    items=[], total=0, page=params.page, page_size=params.page_size
                )
        statement = self.repository.filtered(
            keyword=keyword,
            class_id=class_id if class_ids is None else None,
            is_active=is_active,
            class_ids=class_ids,
            student_id=student_id,
        )
        rows, total = await self.repository.paginate(statement, params.page, params.page_size)
        return Page[StudentRead](
            items=[self._to_read(row, access) for row in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def get_student(self, student_id: int, access: AccessContext) -> StudentRead:
        student = await self._require(student_id)
        access.ensure_student(student)
        return self._to_read(student, access)

    async def create_student(self, payload: StudentCreate) -> StudentRead:
        if await self.repository.get_by_no(payload.student_no):
            raise DuplicateKeyError("学号已存在")
        if payload.class_id is not None and not await SchoolClassRepository(self.session).get(
            payload.class_id
        ):
            raise NotFoundError("班级不存在")
        student = Student(**payload.model_dump())
        await self.repository.add(student)
        await self.session.commit()
        await self.session.refresh(student)
        return StudentRead.model_validate(student)

    async def update_student(
        self, student_id: int, payload: StudentUpdate, access: AccessContext
    ) -> StudentRead:
        student = await self._require(student_id)
        changes = payload.model_dump(exclude_unset=True)
        if (
            "class_id" in changes
            and changes["class_id"] is not None
            and not await SchoolClassRepository(self.session).get(changes["class_id"])
        ):
            raise NotFoundError("班级不存在")
        new_status = changes.get("status")
        if new_status is not None and new_status != student.status:
            self.session.add(
                StudentStatusHistory(
                    student_id=student.id,
                    from_status=student.status,
                    to_status=new_status,
                    effective_date=date.today(),
                    reason="资料更新",
                    operator_id=access.user.id,
                )
            )
        for field, value in changes.items():
            setattr(student, field, value)
        await self.session.commit()
        await self.session.refresh(student)
        return self._to_read(student, access)

    async def change_status(
        self, student_id: int, payload: StudentStatusChange, access: AccessContext
    ) -> StudentRead:
        """变更学籍状态并留痕。"""
        access.ensure(Permission.STUDENT_MANAGE)
        student = await self._require(student_id)
        if student.status is payload.status:
            raise ConflictError("学籍状态未变化")
        self.session.add(
            StudentStatusHistory(
                student_id=student.id,
                from_status=student.status,
                to_status=payload.status,
                effective_date=payload.effective_date,
                reason=payload.reason,
                operator_id=access.user.id,
            )
        )
        student.status = payload.status
        await self.session.commit()
        await self.session.refresh(student)
        return self._to_read(student, access)

    async def status_history(
        self, student_id: int, access: AccessContext
    ) -> list[StudentStatusHistoryRead]:
        """学籍异动时间线。"""
        student = await self._require(student_id)
        access.ensure_student(student)
        rows = await StudentStatusRepository(self.session).history(student.id)
        return [
            StudentStatusHistoryRead(
                id=item.id,
                from_status=item.from_status,
                to_status=item.to_status,
                effective_date=item.effective_date,
                reason=item.reason,
            )
            for item in rows
        ]

    async def deactivate_student(self, student_id: int) -> Message:
        """停用而非物理删除，保留历史选课与成绩。"""
        student = await self._require(student_id)
        student.is_active = False
        await self.session.commit()
        return Message(message="学生已停用")

    async def transcript(self, student_id: int) -> list[TranscriptItem]:
        """学生成绩单：课程、学分与总评。"""
        await self._require(student_id)
        statement = (
            select(Course.code, Course.name, Course.credits, Course.semester, Score.final_score)
            .join(Enrollment, Enrollment.course_id == Course.id)
            .outerjoin(Score, Score.enrollment_id == Enrollment.id)
            .where(Enrollment.student_id == student_id)
            .order_by(Course.semester, Course.code)
        )
        result = await self.session.execute(statement)
        return [
            TranscriptItem(
                course_code=str(row[0]),
                course_name=str(row[1]),
                credits=float(row[2]),
                semester=str(row[3]),
                final_score=float(row[4]) if row[4] is not None else None,
            )
            for row in result.all()
        ]

    async def transcript_for(self, student_id: int, access: AccessContext) -> list[TranscriptItem]:
        """成绩单访问控制：学生仅限本人，教师限数据范围。"""
        scope = access.scope
        if scope.kind is ScopeKind.SELF:
            if student_id != scope.student_id:
                raise PermissionDeniedError("只能查看本人成绩单")
            return await self.transcript(student_id)
        student = await self._require(student_id)
        if scope.kind is ScopeKind.CLASSES and not scope.allows_student(student):
            raise PermissionDeniedError("只能查看权限范围内学生的成绩单")
        if scope.kind not in {ScopeKind.ALL, ScopeKind.CLASSES}:
            raise PermissionDeniedError("没有权限查看该成绩单")
        return await self.transcript(student_id)

    @staticmethod
    def _to_read(student: Student, access: AccessContext) -> StudentRead:
        data = StudentRead.model_validate(student)
        if access.field_level is FieldLevel.SELF:
            data.phone = None
            data.email = None
        sensitive = access.field_level is FieldLevel.ADMIN or (
            student.class_id is not None and student.class_id in access.head_class_ids
        )
        if not sensitive:
            data.id_card_masked = None
            data.address = None
            data.guardian_name = None
            data.guardian_phone = None
        return data

    async def _require(self, student_id: int) -> Student:
        student = await self.repository.get(student_id)
        if student is None:
            raise NotFoundError("学生不存在")
        return student


class TeacherService:
    """教师档案。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = TeacherRepository(session)

    async def list_teachers(
        self,
        *,
        access: AccessContext,
        keyword: str | None = None,
        department: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[TeacherRead]:
        params = PageParams(page=page, page_size=page_size)
        statement = self.repository.filtered(keyword=keyword, department=department)
        rows, total = await self.repository.paginate(statement, params.page, params.page_size)
        return Page[TeacherRead](
            items=[self._to_read(row, access) for row in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def get_teacher(self, teacher_id: int, access: AccessContext) -> TeacherRead:
        teacher = await self._require(teacher_id)
        return self._to_read(teacher, access)

    async def create_teacher(self, payload: TeacherCreate) -> TeacherRead:
        if await self.repository.get_by_no(payload.teacher_no):
            raise DuplicateKeyError("工号已存在")
        await self._ensure_subject(payload.subject_id)
        teacher = Teacher(**payload.model_dump())
        await self.repository.add(teacher)
        await self.session.commit()
        await self.session.refresh(teacher)
        return TeacherRead.model_validate(teacher)

    async def update_teacher(self, teacher_id: int, payload: TeacherUpdate) -> TeacherRead:
        teacher = await self._require(teacher_id)
        changes = payload.model_dump(exclude_unset=True)
        if "subject_id" in changes:
            await self._ensure_subject(changes["subject_id"])
        for field, value in changes.items():
            setattr(teacher, field, value)
        await self.session.commit()
        await self.session.refresh(teacher)
        return TeacherRead.model_validate(teacher)

    async def _ensure_subject(self, subject_id: int | None) -> None:
        if subject_id is None:
            return
        if not await SubjectRepository(self.session).get(subject_id):
            raise NotFoundError("学科不存在")

    async def deactivate_teacher(self, teacher_id: int) -> Message:
        teacher = await self._require(teacher_id)
        teacher.is_active = False
        await self.session.commit()
        return Message(message="教师已停用")

    @staticmethod
    def _to_read(teacher: Teacher, access: AccessContext) -> TeacherRead:
        data = TeacherRead.model_validate(teacher)
        if access.field_level is FieldLevel.SELF:
            data.phone = None
            data.email = None
        return data

    async def _require(self, teacher_id: int) -> Teacher:
        teacher = await self.repository.get(teacher_id)
        if teacher is None:
            raise NotFoundError("教师不存在")
        return teacher


class SchoolClassService:
    """班级管理。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SchoolClassRepository(session)

    async def list_classes(self, access: AccessContext) -> list[SchoolClassRead]:
        classes = await self.repository.list_all()
        scope = access.scope
        if scope.kind is ScopeKind.ALL:
            visible = classes
        elif scope.kind in {ScopeKind.CLASSES, ScopeKind.SELF}:
            visible = [item for item in classes if item.id in scope.class_ids]
        else:
            visible = []
        return [SchoolClassRead.model_validate(item) for item in visible]

    async def get_class(self, class_id: int, access: AccessContext) -> SchoolClassRead:
        entity = await self.repository.get(class_id)
        if entity is None:
            raise NotFoundError("班级不存在")
        access.ensure_class(class_id)
        return SchoolClassRead.model_validate(entity)

    async def create_class(self, payload: SchoolClassCreate) -> SchoolClassRead:
        if await self.repository.get_by_name(payload.name):
            raise DuplicateKeyError("班级名称已存在")
        if payload.department_id is not None and not await DepartmentRepository(self.session).get(
            payload.department_id
        ):
            raise NotFoundError("院系不存在")
        entity = SchoolClass(**payload.model_dump())
        await self.repository.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return SchoolClassRead.model_validate(entity)

    async def update_class(self, class_id: int, payload: SchoolClassUpdate) -> SchoolClassRead:
        entity = await self.repository.get(class_id)
        if entity is None:
            raise NotFoundError("班级不存在")
        changes = payload.model_dump(exclude_unset=True)
        if (
            "department_id" in changes
            and changes["department_id"] is not None
            and not await DepartmentRepository(self.session).get(changes["department_id"])
        ):
            raise NotFoundError("院系不存在")
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.commit()
        await self.session.refresh(entity)
        return SchoolClassRead.model_validate(entity)

    async def delete_class(self, class_id: int) -> Message:
        entity = await self.repository.get(class_id)
        if entity is None:
            raise NotFoundError("班级不存在")
        if await self.repository.count_students(class_id) > 0:
            raise ReferenceExistsError("班级下仍有学生，不能删除")
        await self.repository.delete(entity)
        await self.session.commit()
        return Message(message="班级已删除")
