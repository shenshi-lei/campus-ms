"""组织服务：院系、学科、学期与人员树。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import ConflictError, DuplicateKeyError, NotFoundError
from campus.models.enums import SemesterStatus
from campus.models.org import Department, Semester, Subject
from campus.models.school_class import SchoolClass
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.repositories.org import (
    DepartmentRepository,
    SemesterRepository,
    SubjectRepository,
)
from campus.schemas.org import (
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
    OrgNode,
    OrgTreeRead,
    SemesterCreate,
    SemesterRead,
    SemesterUpdate,
    SubjectCreate,
    SubjectRead,
    SubjectUpdate,
)
from campus.services.access import AccessContext, Permission, ScopeKind


class DepartmentService:
    """院系与处室。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DepartmentRepository(session)

    async def list_departments(self) -> list[DepartmentRead]:
        return [DepartmentRead.model_validate(item) for item in await self.repository.list_all()]

    async def create_department(self, payload: DepartmentCreate) -> DepartmentRead:
        if await self.repository.get_by_code(payload.code):
            raise DuplicateKeyError("院系编码已存在")
        if await self.repository.get_by_name(payload.name):
            raise DuplicateKeyError("院系名称已存在")
        if payload.parent_id is not None and not await self.repository.get(payload.parent_id):
            raise NotFoundError("上级院系不存在")
        entity = Department(
            code=payload.code,
            name=payload.name,
            kind=payload.kind,
            parent_id=payload.parent_id,
            is_active=payload.is_active,
        )
        await self.repository.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return DepartmentRead.model_validate(entity)

    async def update_department(
        self, department_id: int, payload: DepartmentUpdate
    ) -> DepartmentRead:
        entity = await self.repository.get(department_id)
        if entity is None:
            raise NotFoundError("院系不存在")
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] != entity.name:
            existing = await self.repository.get_by_name(changes["name"])
            if existing is not None:
                raise DuplicateKeyError("院系名称已存在")
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.commit()
        await self.session.refresh(entity)
        return DepartmentRead.model_validate(entity)


class SubjectService:
    """学科。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SubjectRepository(session)
        self.departments = DepartmentRepository(session)

    async def list_subjects(self) -> list[SubjectRead]:
        return [SubjectRead.model_validate(item) for item in await self.repository.list_all()]

    async def create_subject(self, payload: SubjectCreate) -> SubjectRead:
        if await self.repository.get_by_code(payload.code):
            raise DuplicateKeyError("学科编码已存在")
        if await self.repository.get_by_name(payload.name):
            raise DuplicateKeyError("学科名称已存在")
        if payload.department_id is not None and not await self.departments.get(
            payload.department_id
        ):
            raise NotFoundError("院系不存在")
        entity = Subject(
            code=payload.code,
            name=payload.name,
            department_id=payload.department_id,
            is_active=payload.is_active,
        )
        await self.repository.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return SubjectRead.model_validate(entity)

    async def update_subject(self, subject_id: int, payload: SubjectUpdate) -> SubjectRead:
        entity = await self.repository.get(subject_id)
        if entity is None:
            raise NotFoundError("学科不存在")
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] != entity.name:
            existing = await self.repository.get_by_name(changes["name"])
            if existing is not None:
                raise DuplicateKeyError("学科名称已存在")
        if (
            "department_id" in changes
            and changes["department_id"] is not None
            and not await self.departments.get(changes["department_id"])
        ):
            raise NotFoundError("院系不存在")
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.commit()
        await self.session.refresh(entity)
        return SubjectRead.model_validate(entity)


class SemesterService:
    """学期。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SemesterRepository(session)

    async def list_semesters(self) -> list[SemesterRead]:
        return [SemesterRead.model_validate(item) for item in await self.repository.list_all()]

    async def create_semester(self, payload: SemesterCreate) -> SemesterRead:
        if await self.repository.get_by_name(payload.name):
            raise DuplicateKeyError("学期名称已存在")
        self._validate_dates(payload.start_date, payload.end_date)
        if payload.is_current:
            await self.repository.clear_current()
        entity = Semester(
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=SemesterStatus.ACTIVE if payload.is_current else payload.status,
            is_current=payload.is_current,
            weeks=payload.weeks,
        )
        await self.repository.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return SemesterRead.model_validate(entity)

    async def update_semester(self, semester_id: int, payload: SemesterUpdate) -> SemesterRead:
        entity = await self.repository.get(semester_id)
        if entity is None:
            raise NotFoundError("学期不存在")
        changes = payload.model_dump(exclude_unset=True)
        start = changes.get("start_date", entity.start_date)
        end = changes.get("end_date", entity.end_date)
        self._validate_dates(start, end)
        if changes.pop("is_current", None) is True:
            await self.repository.clear_current(exclude_id=entity.id)
            entity.is_current = True
            entity.status = SemesterStatus.ACTIVE
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.commit()
        await self.session.refresh(entity)
        return SemesterRead.model_validate(entity)

    async def activate(self, semester_id: int) -> SemesterRead:
        entity = await self.repository.get(semester_id)
        if entity is None:
            raise NotFoundError("学期不存在")
        await self.repository.clear_current(exclude_id=entity.id)
        entity.is_current = True
        entity.status = SemesterStatus.ACTIVE
        await self.session.commit()
        await self.session.refresh(entity)
        return SemesterRead.model_validate(entity)

    @staticmethod
    def _validate_dates(start: date, end: date) -> None:
        if end <= start:
            raise ConflictError("学期结束日期必须晚于开始日期")


class OrgTreeService:
    """人员选择树：院系 → 班级 → 学生 / 院系 → 教师。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def tree(
        self,
        access: AccessContext,
        *,
        person_type: str = "student",
        keyword: str | None = None,
    ) -> OrgTreeRead:
        """返回权限范围内的人员树。"""
        access.ensure(
            Permission.STUDENT_READ if person_type == "student" else Permission.TEACHER_READ
        )
        departments = list(
            (await self.session.scalars(select(Department).order_by(Department.code))).all()
        )
        classes = list(
            (await self.session.scalars(select(SchoolClass).order_by(SchoolClass.name))).all()
        )
        students = list(
            (await self.session.scalars(select(Student).order_by(Student.student_no))).all()
        )
        teachers = list(
            (await self.session.scalars(select(Teacher).order_by(Teacher.teacher_no))).all()
        )

        students = [item for item in students if self._student_visible(access, item)]
        teachers = [item for item in teachers if self._teacher_visible(access, item)]
        visible_class_ids = {item.class_id for item in students if item.class_id is not None}
        if access.scope.kind is ScopeKind.CLASSES:
            visible_class_ids |= set(access.scope.class_ids)
        if access.scope.kind is ScopeKind.ALL:
            visible_class_ids = {item.id for item in classes}
        classes = [item for item in classes if item.id in visible_class_ids]

        class_students: dict[int, list[Student]] = defaultdict(list)
        for student in students:
            if student.class_id is not None:
                class_students[student.class_id].append(student)

        dept_teachers: dict[int | None, list[Teacher]] = defaultdict(list)
        for teacher in teachers:
            dept_teachers[teacher.department_id].append(teacher)

        class_by_department: dict[int | None, list[SchoolClass]] = defaultdict(list)
        for school_class in classes:
            class_by_department[school_class.department_id].append(school_class)

        dept_nodes = self._department_nodes(
            departments,
            class_by_department,
            dept_teachers,
            class_students,
            person_type=person_type,
            keyword=keyword,
        )
        total = (
            sum(len(items) for items in class_students.values())
            if person_type == "student"
            else len(teachers)
        )
        return OrgTreeRead(nodes=dept_nodes, total=total)

    def _department_nodes(
        self,
        departments: list[Department],
        class_by_department: dict[int | None, list[SchoolClass]],
        dept_teachers: dict[int | None, list[Teacher]],
        class_students: dict[int, list[Student]],
        *,
        person_type: str,
        keyword: str | None,
    ) -> list[OrgNode]:
        by_parent: dict[int | None, list[Department]] = defaultdict(list)
        for department in departments:
            by_parent[department.parent_id].append(department)

        def build(department: Department) -> OrgNode | None:
            class_nodes: list[OrgNode] = []
            for school_class in class_by_department.get(department.id, []):
                student_nodes = [
                    self._student_node(student)
                    for student in class_students.get(school_class.id, [])
                ]
                if person_type == "student":
                    class_nodes.append(
                        OrgNode(
                            key=f"class:{school_class.id}",
                            type="class",
                            label=school_class.name,
                            subtitle=f"{len(student_nodes)} 名学生",
                            count=len(student_nodes),
                            has_children=bool(student_nodes),
                            children=student_nodes,
                        )
                    )
            teacher_nodes = (
                [self._teacher_node(teacher) for teacher in dept_teachers.get(department.id, [])]
                if person_type == "teacher"
                else []
            )
            child_departments = [
                item
                for child in by_parent.get(department.id, [])
                if (item := build(child)) is not None
            ]
            children = child_departments + class_nodes + teacher_nodes
            count = sum(node.count for node in children)
            node = OrgNode(
                key=f"dept:{department.id}",
                type="department",
                label=department.name,
                subtitle=department.code,
                count=count,
                has_children=bool(children),
                children=children,
            )
            if keyword and not self._match(node, keyword):
                return None
            return node

        roots: list[OrgNode] = []
        for department in by_parent.get(None, []):
            node = build(department)
            if node is not None:
                roots.append(node)

        unknown_classes = [
            item for item in class_by_department.get(None, []) if class_students.get(item.id)
        ]
        unknown_teachers = dept_teachers.get(None, []) if person_type == "teacher" else []
        if unknown_classes or unknown_teachers:
            children = []
            for school_class in unknown_classes:
                student_nodes = [
                    self._student_node(student)
                    for student in class_students.get(school_class.id, [])
                ]
                if person_type == "student":
                    children.append(
                        OrgNode(
                            key=f"class:{school_class.id}",
                            type="class",
                            label=school_class.name,
                            subtitle=f"{len(student_nodes)} 名学生",
                            count=len(student_nodes),
                            has_children=bool(student_nodes),
                            children=student_nodes,
                        )
                    )
            if person_type == "teacher":
                children.extend(self._teacher_node(item) for item in unknown_teachers)
            if children:
                roots.append(
                    OrgNode(
                        key="dept:none",
                        type="department",
                        label="未分配院系",
                        subtitle="",
                        count=sum(item.count for item in children),
                        has_children=True,
                        children=children,
                    )
                )
        if keyword:
            roots = [item for item in roots if self._match(item, keyword)]
        return roots

    def _match(self, node: OrgNode, keyword: str) -> bool:
        if keyword in node.label or keyword in node.subtitle:
            return True
        return any(self._match(child, keyword) for child in node.children)

    @staticmethod
    def _student_node(student: Student) -> OrgNode:
        return OrgNode(
            key=f"student:{student.id}",
            type="student",
            label=student.name,
            subtitle=student.student_no,
            count=1,
            selectable=True,
        )

    @staticmethod
    def _teacher_node(teacher: Teacher) -> OrgNode:
        return OrgNode(
            key=f"teacher:{teacher.id}",
            type="teacher",
            label=teacher.name,
            subtitle=f"{teacher.teacher_no} · {teacher.title}",
            count=1,
            selectable=True,
        )

    @staticmethod
    def _student_visible(access: AccessContext, student: Student) -> bool:
        if access.scope.kind is ScopeKind.ALL:
            return True
        if access.scope.kind is ScopeKind.SELF:
            return student.id == access.student_id
        if access.scope.kind is ScopeKind.CLASSES:
            return student.class_id in access.scope.class_ids
        return False

    @staticmethod
    def _teacher_visible(access: AccessContext, teacher: Teacher) -> bool:
        if access.scope.kind is ScopeKind.ALL:
            return True
        if access.scope.kind is ScopeKind.SELF:
            return teacher.id == access.teacher_id
        if access.scope.kind is ScopeKind.CLASSES:
            return teacher.id == access.teacher_id
        return False
