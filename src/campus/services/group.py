"""群组服务：组织树人员的选择、展开与复用。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.exceptions import ConflictError, NotFoundError
from campus.models.enums import GroupMemberType
from campus.models.group import UserGroup, UserGroupMember
from campus.models.org import Department
from campus.models.school_class import SchoolClass
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.user import User
from campus.repositories.group import UserGroupRepository
from campus.schemas.group import (
    GroupCreate,
    GroupExpandRead,
    GroupMemberInput,
    GroupMemberRead,
    GroupRead,
    GroupUpdate,
)


class GroupService:
    """群组 CRUD 与成员展开。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = UserGroupRepository(session)

    async def list_groups(self, *, keyword: str | None = None) -> list[GroupRead]:
        groups = await self.repository.list_all(keyword)
        counts = await self.repository.member_counts()
        members = await self.repository.members_for_groups([item.id for item in groups])
        return [
            self._to_read(item, members.get(item.id, []), counts.get(item.id, 0)) for item in groups
        ]

    async def get_group(self, group_id: int) -> GroupRead:
        group = await self._require(group_id)
        members = await self.repository.members(group_id)
        return self._to_read(group, members, len(members))

    async def create_group(self, payload: GroupCreate, user_id: int | None) -> GroupRead:
        existing = await self.repository.get_by_code(payload.code)
        if existing is not None:
            raise ConflictError("群组编码已存在")
        group = UserGroup(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            kind=payload.kind,
            is_active=payload.is_active,
            created_by=user_id,
        )
        self.session.add(group)
        await self.session.flush()
        await self._replace_members(group.id, payload.members)
        await self.session.commit()
        return await self.get_group(group.id)

    async def update_group(
        self, group_id: int, payload: GroupUpdate, user_id: int | None
    ) -> GroupRead:
        group = await self._require(group_id)
        if payload.name is not None:
            group.name = payload.name
        if payload.description is not None:
            group.description = payload.description
        if payload.kind is not None:
            group.kind = payload.kind
        if payload.is_active is not None:
            group.is_active = payload.is_active
        if payload.members is not None:
            await self._replace_members(group_id, payload.members)
        await self.session.commit()
        return await self.get_group(group_id)

    async def delete_group(self, group_id: int) -> None:
        group = await self._require(group_id)
        await self.repository.delete(group)
        await self.session.commit()

    async def expand(self, group_id: int) -> GroupExpandRead:
        await self._require(group_id)
        members = await self.repository.members(group_id)
        user_ids: set[int] = set()
        unresolved = 0
        for member in members:
            resolved = await self._resolve_users(member.member_type, member.member_id)
            if resolved:
                user_ids.update(resolved)
            else:
                unresolved += 1
        return GroupExpandRead(
            user_ids=sorted(user_ids), user_count=len(user_ids), unresolved=unresolved
        )

    async def user_ids_for_group(self, group_id: int) -> set[int]:
        return set((await self.expand(group_id)).user_ids)

    async def group_ids_for_user(self, user_id: int) -> set[int]:
        """用户所属的启用群组。"""
        rows = await self.repository.groups_for_user(user_id)
        return {item.id for item in rows}

    async def user_ids_for_groups(self, group_ids: set[int]) -> set[int]:
        user_ids: set[int] = set()
        for group_id in group_ids:
            user_ids.update(await self.user_ids_for_group(group_id))
        return user_ids

    async def _replace_members(self, group_id: int, members: list[GroupMemberInput]) -> None:
        existing = await self.repository.members(group_id)
        for item in existing:
            await self.session.delete(item)
        await self.session.flush()
        seen: set[tuple[str, int]] = set()
        for raw in members:
            key = (raw.member_type.value, raw.member_id)
            if key in seen:
                continue
            seen.add(key)
            display_name, subtitle = await self._describe(raw.member_type, raw.member_id)
            if not display_name:
                raise NotFoundError("群组成员不存在")
            user_ids = await self._resolve_users(raw.member_type, raw.member_id)
            self.session.add(
                UserGroupMember(
                    group_id=group_id,
                    member_type=raw.member_type,
                    member_id=raw.member_id,
                    user_id=next(iter(user_ids)) if len(user_ids) == 1 else None,
                    display_name=display_name,
                )
            )
        await self.session.flush()

    async def _describe(self, member_type: GroupMemberType, member_id: int) -> tuple[str, str]:
        if member_type is GroupMemberType.USER:
            user = await self.session.get(User, member_id)
            return (user.username if user else "", "用户")
        if member_type is GroupMemberType.STUDENT:
            student = await self.session.get(Student, member_id)
            return (student.name if student else "", student.student_no if student else "")
        if member_type is GroupMemberType.TEACHER:
            teacher = await self.session.get(Teacher, member_id)
            return (teacher.name if teacher else "", teacher.teacher_no if teacher else "")
        if member_type is GroupMemberType.DEPARTMENT:
            department = await self.session.get(Department, member_id)
            return (department.name if department else "", "院系/处室")
        if member_type is GroupMemberType.CLASS:
            school_class = await self.session.get(SchoolClass, member_id)
            return (school_class.name if school_class else "", "班级")
        return ("", "")

    async def _resolve_users(self, member_type: GroupMemberType, member_id: int) -> set[int]:
        if member_type is GroupMemberType.USER:
            user = await self.session.get(User, member_id)
            return {user.id} if user is not None and user.is_active else set()
        if member_type is GroupMemberType.STUDENT:
            student = await self.session.get(Student, member_id)
            return {student.user_id} if student and student.user_id else set()
        if member_type is GroupMemberType.TEACHER:
            teacher = await self.session.get(Teacher, member_id)
            return {teacher.user_id} if teacher and teacher.user_id else set()
        if member_type is GroupMemberType.CLASS:
            return await self._class_users(member_id)
        if member_type is GroupMemberType.DEPARTMENT:
            return await self._department_users(member_id)
        return set()

    async def _class_users(self, class_id: int) -> set[int]:
        user_ids = {
            int(item)
            for item in (
                await self.session.scalars(
                    select(Student.user_id).where(
                        Student.class_id == class_id, Student.user_id.is_not(None)
                    )
                )
            ).all()
            if item is not None
        }
        head_teacher_id = await self.session.scalar(
            select(SchoolClass.head_teacher_id).where(SchoolClass.id == class_id)
        )
        if head_teacher_id is not None:
            user_id = await self.session.scalar(
                select(Teacher.user_id).where(Teacher.id == head_teacher_id)
            )
            if user_id is not None:
                user_ids.add(int(user_id))
        return user_ids

    async def _department_users(self, department_id: int) -> set[int]:
        department = await self.session.get(Department, department_id)
        if department is None:
            return set()
        user_ids = {
            int(item)
            for item in (
                await self.session.scalars(
                    select(Teacher.user_id).where(
                        (Teacher.department_id == department_id)
                        | (Teacher.department == department.name),
                        Teacher.user_id.is_not(None),
                    )
                )
            ).all()
            if item is not None
        }
        class_ids = {
            int(item)
            for item in (
                await self.session.scalars(
                    select(SchoolClass.id).where(SchoolClass.department_id == department_id)
                )
            ).all()
        }
        for class_id in class_ids:
            user_ids.update(await self._class_users(class_id))
        return user_ids

    def _to_read(
        self, group: UserGroup, members: list[UserGroupMember], member_count: int
    ) -> GroupRead:
        return GroupRead(
            id=group.id,
            code=group.code,
            name=group.name,
            description=group.description,
            kind=group.kind,
            is_active=group.is_active,
            member_count=member_count,
            members=[
                GroupMemberRead(
                    id=item.id,
                    member_type=item.member_type,
                    member_id=item.member_id,
                    user_id=item.user_id,
                    display_name=item.display_name,
                )
                for item in members
            ],
        )

    async def _require(self, group_id: int) -> UserGroup:
        group = await self.repository.get(group_id)
        if group is None:
            raise NotFoundError("群组不存在")
        return group
