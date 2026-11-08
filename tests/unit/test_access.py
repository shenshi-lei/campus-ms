from __future__ import annotations

from campus.models.student import Student
from campus.services.access import (
    DEFAULT_ROLE_PERMISSIONS,
    DataScope,
    Permission,
    ScopeKind,
)


def test_admin_has_every_permission() -> None:
    assert DEFAULT_ROLE_PERMISSIONS["admin"] == frozenset(Permission)


def test_student_cannot_manage_students() -> None:
    permissions = DEFAULT_ROLE_PERMISSIONS["student"]

    assert Permission.STUDENT_SELF_READ in permissions
    assert Permission.STUDENT_MANAGE not in permissions
    assert Permission.ROLE_MANAGE not in permissions


def test_all_scope_allows_any_student() -> None:
    scope = DataScope(kind=ScopeKind.ALL)
    student = Student(student_no="S1", name="张三", class_id=9)

    assert scope.allows_student(student)
    assert scope.allows_class(999)
    assert scope.allows_course(999)


def test_self_scope_only_allows_own_student() -> None:
    scope = DataScope(kind=ScopeKind.SELF, student_id=1)
    own = Student(id=1, student_no="S1", name="张三", class_id=9)
    other = Student(id=2, student_no="S2", name="李四", class_id=9)

    assert scope.allows_student(own)
    assert not scope.allows_student(other)


def test_class_scope_checks_class_membership() -> None:
    scope = DataScope(kind=ScopeKind.CLASSES, class_ids=frozenset({3, 4}))
    inside = Student(student_no="S1", name="张三", class_id=3)
    outside = Student(student_no="S2", name="李四", class_id=5)

    assert scope.allows_student(inside)
    assert not scope.allows_student(outside)
    assert scope.allows_class(3)
    assert not scope.allows_class(5)
