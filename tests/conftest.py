from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from campus.core.config import Settings, get_settings
from campus.core.security import hash_password
from campus.db.base import Base
from campus.db.session import build_engine, get_session
from campus.main import create_app
from campus.models.course import Course
from campus.models.enums import Role
from campus.models.school_class import SchoolClass
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.user import User

Headers = dict[str, str]


@pytest.fixture
async def app(tmp_path) -> AsyncIterator[object]:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        jwt_secret="test-secret-for-unit-tests-only-0123456789",
        access_token_expire_minutes=30,
    )
    engine = build_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    application = create_app(settings=settings, engine=engine)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session
    application.dependency_overrides[get_settings] = lambda: settings
    application.state.session_factory = factory
    yield application
    await engine.dispose()


@pytest.fixture
async def client(app: object) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture
async def seed(app: object) -> dict[str, int]:
    factory = app.state.session_factory
    async with factory() as session:
        admin = User(username="admin", password_hash=hash_password("admin123"), role=Role.ADMIN)
        teacher_user = User(
            username="t001", password_hash=hash_password("teacher123"), role=Role.TEACHER
        )
        student_user = User(
            username="s001", password_hash=hash_password("student123"), role=Role.STUDENT
        )
        session.add_all([admin, teacher_user, student_user])
        await session.flush()

        teacher = Teacher(teacher_no="T001", name="教师一", user_id=teacher_user.id)
        session.add(teacher)
        await session.flush()

        school_class = SchoolClass(
            name="计算机2301", grade="2023", major="计算机", head_teacher_id=teacher.id
        )
        session.add(school_class)
        await session.flush()

        student = Student(
            student_no="S001", name="学生一", class_id=school_class.id, user_id=student_user.id
        )
        session.add(student)
        await session.flush()

        course = Course(
            code="CS101",
            name="程序设计",
            credits=4.0,
            hours=64,
            semester="2024-2025-1",
            teacher_id=teacher.id,
            capacity=2,
        )
        session.add(course)
        await session.commit()

    return {
        "teacher_id": teacher.id,
        "student_id": student.id,
        "course_id": course.id,
        "class_id": school_class.id,
        "teacher_user_id": teacher_user.id,
        "student_user_id": student_user.id,
    }


@pytest.fixture
def auth_headers(client: AsyncClient) -> Callable[[str, str], Awaitable[Headers]]:
    async def _login(username: str, password: str) -> Headers:
        response = await client.post(
            "/api/v1/auth/login", json={"username": username, "password": password}
        )
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login
