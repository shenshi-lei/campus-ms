"""演示数据：可重复执行，按业务键幂等。"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.core.config import get_settings
from campus.core.security import hash_password
from campus.db.base import utc_now
from campus.db.init_db import create_schema
from campus.db.session import build_engine
from campus.models.attendance import Attendance
from campus.models.authz import AuthRole, UserRole
from campus.models.calendar import CalendarEvent, CalendarEventAttendee
from campus.models.course import Course
from campus.models.dorm import Dorm, DormAssignment
from campus.models.enrollment import Enrollment
from campus.models.enums import (
    ApplicantType,
    AssessmentType,
    AttendanceStatus,
    CalendarEventKind,
    CalendarVisibility,
    ClassRole,
    ClassStatus,
    CourseType,
    Education,
    EmploymentStatus,
    FeeStatus,
    Gender,
    GroupMemberType,
    LeaveStatus,
    LeaveType,
    NoticeAudience,
    ParticipantResponse,
    ResidenceType,
    Role,
    SemesterStatus,
    StaffType,
    StudentStatus,
)
from campus.models.fee import Fee
from campus.models.group import UserGroup, UserGroupMember
from campus.models.leave import LeaveApproval, LeaveRequest
from campus.models.notice import Notice
from campus.models.org import Department, Semester, Subject
from campus.models.schedule import Schedule
from campus.models.school_class import SchoolClass
from campus.models.score import Score
from campus.models.student import Student
from campus.models.teacher import Teacher
from campus.models.teaching import CourseClass, CourseTeacher
from campus.models.user import User
from campus.services.authz import AuthzService
from campus.services.leave import LeaveService
from campus.services.setting import SystemSettingService

logger = logging.getLogger("campus.seed")

CLASS_NAMES = ["计算机2301", "计算机2302", "软件2301", "网络2301"]
DEPARTMENT_DATA = [
    ("CSE", "计算机学院", "college"),
    ("SE", "软件学院", "college"),
    ("MATH", "理学院", "college"),
    ("FL", "外国语学院", "college"),
    ("AFF", "学工处", "office"),
    ("ACA", "教务处", "office"),
]
SUBJECT_DATA = [
    ("CS", "计算机", "CSE"),
    ("SE", "软件工程", "SE"),
    ("MA", "数学", "MATH"),
    ("EN", "英语", "FL"),
    ("PE", "体育", "MATH"),
]
SEMESTER_DATA = [
    ("2023-2024-2", date(2024, 2, 20), date(2024, 7, 10), SemesterStatus.CLOSED, False),
    ("2024-2025-1", date(2024, 9, 1), date(2025, 1, 15), SemesterStatus.CLOSED, False),
    ("2024-2025-2", date(2025, 2, 20), date(2025, 7, 10), SemesterStatus.CLOSED, False),
    ("2026-2027-1", date(2026, 9, 1), date(2027, 1, 20), SemesterStatus.ACTIVE, True),
]
COURSE_DATA = [
    ("CS101", "程序设计基础", 4.0, 64),
    ("CS102", "数据结构", 4.0, 64),
    ("CS201", "数据库原理", 3.0, 48),
    ("CS202", "操作系统", 3.5, 56),
    ("CS301", "计算机网络", 3.0, 48),
    ("SE101", "软件工程导论", 2.5, 40),
    ("SE201", "Web 开发技术", 3.0, 48),
    ("MA101", "高等数学", 5.0, 80),
    ("EN101", "大学英语", 3.0, 48),
    ("PE101", "体育", 1.0, 32),
]


async def _seed_users(session: AsyncSession) -> None:
    if await session.scalar(select(User).where(User.username == "admin")) is None:
        session.add(
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                role=Role.ADMIN,
            )
        )

    for index in range(1, 6):
        username = f"t{index:03d}"
        if await session.scalar(select(User).where(User.username == username)) is None:
            session.add(
                User(
                    username=username,
                    password_hash=hash_password("teacher123"),
                    role=Role.TEACHER,
                )
            )

    for index in range(1, 31):
        username = f"s{index:03d}"
        if await session.scalar(select(User).where(User.username == username)) is None:
            session.add(
                User(
                    username=username,
                    password_hash=hash_password("student123"),
                    role=Role.STUDENT,
                )
            )
    await session.commit()


async def _seed_org(
    session: AsyncSession,
) -> tuple[dict[str, Department], dict[str, Subject]]:
    """院系、学科与学期：可重复执行，按业务键幂等。"""
    departments: dict[str, Department] = {}
    for code, name, kind in DEPARTMENT_DATA:
        department = await session.scalar(select(Department).where(Department.code == code))
        if department is None:
            department = Department(code=code, name=name, kind=kind)
            session.add(department)
            await session.flush()
        departments[code] = department

    subjects: dict[str, Subject] = {}
    for code, name, department_code in SUBJECT_DATA:
        subject = await session.scalar(select(Subject).where(Subject.code == code))
        if subject is None:
            subject = Subject(
                code=code,
                name=name,
                department_id=departments[department_code].id,
            )
            session.add(subject)
            await session.flush()
        subjects[code] = subject

    for name, start, end, status, current in SEMESTER_DATA:
        semester = await session.scalar(select(Semester).where(Semester.name == name))
        if semester is None:
            session.add(
                Semester(
                    name=name,
                    start_date=start,
                    end_date=end,
                    status=status,
                    is_current=current,
                )
            )
    await session.flush()
    current_semester = await session.scalar(select(Semester).where(Semester.name == "2026-2027-1"))
    if current_semester is not None:
        for semester in (await session.scalars(select(Semester))).all():
            semester.is_current = semester.id == current_semester.id
        current_semester.status = SemesterStatus.ACTIVE
    await session.commit()
    return departments, subjects


async def _seed_people(
    session: AsyncSession,
    departments: dict[str, Department],
    subjects: dict[str, Subject],
) -> None:
    await _seed_users(session)

    classes: list[SchoolClass] = []
    for offset, name in enumerate(CLASS_NAMES):
        school_class = await session.scalar(select(SchoolClass).where(SchoolClass.name == name))
        if school_class is None:
            school_class = SchoolClass(name=name, grade="2023", major=name[:2])
            session.add(school_class)
            await session.flush()
        school_class.grade_year = school_class.grade_year or 2023
        default_department = (
            departments["SE"].id if name.startswith("软件") else departments["CSE"].id
        )
        school_class.department_id = school_class.department_id or default_department
        school_class.classroom = school_class.classroom or f"{'ABCD'[offset % 4]}{201 + offset}"
        school_class.capacity = school_class.capacity or 45
        school_class.status = ClassStatus.ACTIVE
        classes.append(school_class)

    teachers: list[Teacher] = []
    subject_codes = ["CS", "SE", "MA", "EN", "PE"]
    educations = [
        Education.DOCTOR,
        Education.MASTER,
        Education.MASTER,
        Education.BACHELOR,
        Education.MASTER,
    ]
    for index in range(1, 6):
        teacher_no = f"T{index:03d}"
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_no == teacher_no))
        user = await session.scalar(select(User).where(User.username == f"t{index:03d}"))
        if teacher is None:
            teacher = Teacher(
                teacher_no=teacher_no,
                name=f"教师{index}",
                title=["教授", "副教授", "讲师", "讲师", "助教"][index - 1],
                department=f"学院{(index - 1) % 3 + 1}",
                user_id=user.id if user else None,
            )
            session.add(teacher)
            await session.flush()
        teacher.subject_id = teacher.subject_id or subjects[subject_codes[index - 1]].id
        teacher.position = teacher.position or (
            "教务主任" if index == 1 else "教研组长" if index == 3 else ""
        )
        teacher.hire_date = teacher.hire_date or date(2012 + index, 7, 1)
        teacher.employment_status = EmploymentStatus.ACTIVE
        teacher.staff_type = StaffType.PERMANENT
        teacher.education = educations[index - 1]
        teacher.office = teacher.office or f"教学楼{index}0{index}"
        teacher.workload_limit = teacher.workload_limit or 16
        teachers.append(teacher)

    for offset, class_entity in enumerate(classes):
        if class_entity.head_teacher_id is None:
            class_entity.head_teacher_id = teachers[offset % len(teachers)].id
    await session.commit()

    for index in range(1, 31):
        student_no = f"S{index:03d}"
        user = await session.scalar(select(User).where(User.username == f"s{index:03d}"))
        student = await session.scalar(select(Student).where(Student.student_no == student_no))
        if student is None:
            gender = Gender.MALE if index % 2 == 1 else Gender.FEMALE
            student = Student(
                student_no=student_no,
                name=f"学生{index:02d}",
                gender=gender,
                birth_date=date(2005, (index % 12) + 1, (index % 27) + 1),
                phone=f"1380000{index:04d}",
                email=f"s{index:03d}@campus.example",
                class_id=classes[(index - 1) % len(classes)].id,
                user_id=user.id if user else None,
            )
            session.add(student)
        seat_no = (index - 1) % 40 + 1
        student.enroll_date = student.enroll_date or date(2023, 9, 1)
        student.status = StudentStatus.ACTIVE
        student.seat_no = student.seat_no or seat_no
        student.seat_row = student.seat_row or (seat_no - 1) // 8 + 1
        student.seat_col = student.seat_col or (seat_no - 1) % 8 + 1
        student.id_card_masked = student.id_card_masked or f"3301**********{1000 + index:04d}"
        student.address = student.address or f"浙江省杭州市示例路{index}号"
        student.guardian_name = student.guardian_name or f"{student.name}家长"
        student.guardian_phone = student.guardian_phone or f"1390000{index:04d}"
        student.class_role = ClassRole.MONITOR if index % 10 == 1 else ClassRole.NONE
        student.residence_type = ResidenceType.BOARDING
    await session.commit()


async def _seed_courses(session: AsyncSession) -> None:
    teachers = list((await session.scalars(select(Teacher).order_by(Teacher.id))).all())
    subjects = {item.code: item for item in (await session.scalars(select(Subject))).all()}
    semester = await session.scalar(select(Semester).where(Semester.name == "2024-2025-1"))
    subject_codes = {
        "CS": "CS",
        "SE": "SE",
        "MA": "MA",
        "EN": "EN",
        "PE": "PE",
    }
    for index, (code, name, credits, hours) in enumerate(COURSE_DATA):
        course = await session.scalar(select(Course).where(Course.code == code))
        if course is None:
            course = Course(
                code=code,
                name=name,
                credits=credits,
                hours=hours,
                semester="2024-2025-1",
                teacher_id=teachers[index % len(teachers)].id if teachers else None,
                capacity=10 if index == 0 else 15 + (index % 4) * 10,
                description=f"{name} 课程，{hours} 学时。",
            )
            session.add(course)
            await session.flush()
        prefix = code[:2]
        course.subject_id = course.subject_id or (
            subjects[subject_codes[prefix]].id if prefix in subject_codes else None
        )
        course.semester_id = course.semester_id or (semester.id if semester else None)
        course.course_type = CourseType.ELECTIVE if code == "SE101" else CourseType.REQUIRED
        course.assessment_type = (
            AssessmentType.CHECK if code in {"PE101", "SE101"} else AssessmentType.EXAM
        )
        course.grade_scheme = course.grade_scheme or {
            "usual": 0.4,
            "midterm": 0.0,
            "exam": 0.6,
        }
        course.textbook = course.textbook or f"《{name}》教材"
        course.grade_year = course.grade_year or 2023
        course.is_active = True
    await session.commit()


async def _seed_course_links(session: AsyncSession) -> None:
    """补齐课程教师与面向班级关系。"""
    courses = list((await session.scalars(select(Course).order_by(Course.id))).all())
    for course in courses:
        if course.teacher_id is not None:
            exists = await session.scalar(
                select(CourseTeacher).where(
                    CourseTeacher.course_id == course.id,
                    CourseTeacher.teacher_id == course.teacher_id,
                )
            )
            if exists is None:
                session.add(
                    CourseTeacher(
                        course_id=course.id,
                        teacher_id=course.teacher_id,
                        role="primary",
                    )
                )
        class_ids = {
            int(item)
            for item in (
                await session.scalars(
                    select(Student.class_id)
                    .join(Enrollment, Enrollment.student_id == Student.id)
                    .where(
                        Enrollment.course_id == course.id,
                        Student.class_id.is_not(None),
                    )
                    .distinct()
                )
            ).all()
            if item is not None
        }
        for class_id in class_ids:
            exists = await session.scalar(
                select(CourseClass).where(
                    CourseClass.course_id == course.id,
                    CourseClass.class_id == class_id,
                )
            )
            if exists is None:
                session.add(CourseClass(course_id=course.id, class_id=class_id))
    await session.commit()


async def _seed_academics(session: AsyncSession) -> None:
    students = list((await session.scalars(select(Student).order_by(Student.id))).all())
    courses = list((await session.scalars(select(Course).order_by(Course.id))).all())
    for offset, student in enumerate(students):
        for step in range(4):
            course = courses[(offset + step) % len(courses)]
            enrollment = await session.scalar(
                select(Enrollment).where(
                    Enrollment.student_id == student.id,
                    Enrollment.course_id == course.id,
                )
            )
            if enrollment is None:
                enrollment = Enrollment(student_id=student.id, course_id=course.id)
                session.add(enrollment)
                await session.flush()
            if step >= 3:
                continue
            if await session.scalar(select(Score.id).where(Score.enrollment_id == enrollment.id)):
                continue
            usual = float(55 + (offset * 3 + step * 7) % 41)
            exam = float(35 + (offset * 11 + step * 13) % 60)
            session.add(
                Score(
                    enrollment_id=enrollment.id,
                    usual_score=usual,
                    exam_score=exam,
                    final_score=round(usual * 0.4 + exam * 0.6, 2),
                    recorded_at=utc_now() - timedelta(days=(offset * 2 + step * 5) % 28),
                )
            )
    await session.commit()


async def _seed_schedules(session: AsyncSession) -> None:
    """为每门课程安排一个固定时段，保证课表和今日视图有数据。"""
    courses = list((await session.scalars(select(Course).order_by(Course.id))).all())
    for index, course in enumerate(courses):
        weekday = index % 5 + 1
        start_period = 1 + (index % 4) * 2
        existing = await session.scalar(
            select(Schedule).where(
                Schedule.course_id == course.id,
                Schedule.weekday == weekday,
                Schedule.start_period == start_period,
            )
        )
        if existing is not None:
            continue
        session.add(
            Schedule(
                course_id=course.id,
                semester_id=course.semester_id,
                weekday=weekday,
                start_period=start_period,
                end_period=start_period + 1,
                classroom=f"{'ABC'[index % 3]}{100 + index}",
                weeks="1-16",
            )
        )
    await session.commit()


async def _seed_attendance(session: AsyncSession) -> None:
    students = list((await session.scalars(select(Student).order_by(Student.id))).all())
    courses = list((await session.scalars(select(Course).order_by(Course.id))).all())
    today = date.today()
    for offset, student in enumerate(students[:20]):
        course = courses[offset % len(courses)]
        for day_offset in range(30):
            day = today - timedelta(days=day_offset)
            record = await session.scalar(
                select(Attendance).where(
                    Attendance.student_id == student.id,
                    Attendance.course_id == course.id,
                    Attendance.date == day,
                )
            )
            if record is not None:
                continue
            marker = (offset + day_offset) % 30
            if marker % 11 == 0:
                status = AttendanceStatus.ABSENT
            elif marker % 7 == 0:
                status = AttendanceStatus.LATE
            elif marker % 13 == 0:
                status = AttendanceStatus.LEAVE
            else:
                status = AttendanceStatus.PRESENT
            session.add(
                Attendance(
                    student_id=student.id,
                    course_id=course.id,
                    date=day,
                    status=status,
                )
            )
    await session.commit()


async def _next_free_bed(session: AsyncSession, dorm_id: int, capacity: int) -> int | None:
    """返回房间内可用的最小床位号，满员返回 None。"""
    taken = set(
        (
            await session.scalars(
                select(DormAssignment.bed_no).where(DormAssignment.dorm_id == dorm_id)
            )
        ).all()
    )
    for bed_no in range(1, capacity + 1):
        if bed_no not in taken:
            return bed_no
    return None


async def _seed_dorms(session: AsyncSession) -> None:
    rooms: list[Dorm] = []
    for building, genders in (("A", Gender.MALE), ("B", Gender.FEMALE)):
        for room_index in range(1, 4):
            room_no = f"{room_index:02d}1"
            room = await session.scalar(
                select(Dorm).where(Dorm.building == building, Dorm.room_no == room_no)
            )
            if room is None:
                room = Dorm(building=building, room_no=room_no, capacity=4, gender=genders)
                session.add(room)
                await session.flush()
            rooms.append(room)
    await session.commit()

    students = list(
        (
            await session.scalars(
                select(Student).where(Student.is_active.is_(True)).order_by(Student.id)
            )
        ).all()
    )
    male_rooms = [room for room in rooms if room.gender is Gender.MALE]
    female_rooms = [room for room in rooms if room.gender is Gender.FEMALE]
    for student in students:
        if await session.scalar(
            select(DormAssignment).where(DormAssignment.student_id == student.id)
        ):
            continue
        if student.gender is Gender.MALE:
            candidates = male_rooms
        elif student.gender is Gender.FEMALE:
            candidates = female_rooms
        else:
            continue
        for room in candidates:
            bed_no = await _next_free_bed(session, room.id, room.capacity)
            if bed_no is None:
                continue
            session.add(DormAssignment(student_id=student.id, dorm_id=room.id, bed_no=bed_no))
            await session.flush()
            break
    await session.commit()


async def _seed_fees(session: AsyncSession) -> None:
    students = list((await session.scalars(select(Student).order_by(Student.id))).all())
    for offset, student in enumerate(students):
        if await session.scalar(
            select(Fee).where(Fee.student_id == student.id, Fee.item == "学费")
        ):
            continue
        due_date = date.today() + timedelta(days=30 - (offset % 4) * 40)
        paid = offset % 3 == 0
        session.add(
            Fee(
                student_id=student.id,
                item="学费",
                amount=5800.0,
                due_date=due_date,
                status=FeeStatus.PAID if paid else FeeStatus.UNPAID,
                paid_at=utc_now() if paid else None,
            )
        )
    await session.commit()


async def _seed_duty_roles(session: AsyncSession) -> None:
    """给演示教师分配岗位角色（教务主任、学工处）。"""
    mapping = {"t001": "academic_director", "t002": "student_affairs"}
    for username, role_code in mapping.items():
        user = await session.scalar(select(User).where(User.username == username))
        role = await session.scalar(select(AuthRole).where(AuthRole.code == role_code))
        if user is None or role is None:
            continue
        exists = await session.scalar(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
        )
        if exists is None:
            session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()


async def _seed_notices(session: AsyncSession) -> None:
    """两条演示通知：全校一条 + 班级一条。"""
    admin = await session.scalar(select(User).where(User.username == "admin"))
    if await session.scalar(select(Notice).where(Notice.title == "欢迎使用校园管理系统")) is None:
        session.add(
            Notice(
                title="欢迎使用校园管理系统",
                content="请及时完善个人档案，关注课表与通知。",
                audience=NoticeAudience.ALL,
                publisher_id=admin.id if admin else None,
                is_pinned=True,
            )
        )
    class_entity = await session.scalar(select(SchoolClass).order_by(SchoolClass.id))
    if class_entity is not None and (
        await session.scalar(select(Notice).where(Notice.title == "本周班会通知")) is None
    ):
        session.add(
            Notice(
                title="本周班会通知",
                content="本周五下午 4 点在固定教室召开班会。",
                audience=NoticeAudience.CLASS,
                class_id=class_entity.id,
                publisher_id=admin.id if admin else None,
            )
        )
    await session.commit()


async def _seed_collab(session: AsyncSession) -> None:
    """演示群组与今日日程。"""
    admin = await session.scalar(select(User).where(User.username == "admin"))
    t002 = await session.scalar(select(User).where(User.username == "t002"))
    s001 = await session.scalar(select(User).where(User.username == "s001"))
    group = await session.scalar(select(UserGroup).where(UserGroup.code == "student_affairs"))
    if group is None:
        group = UserGroup(
            code="student_affairs",
            name="学工处工作组",
            description="演示群组：学工处审批与通知接收人",
            kind="approval",
            created_by=admin.id if admin else None,
        )
        session.add(group)
        await session.flush()
    existing_members = {
        (item.member_type, item.member_id)
        for item in (await session.scalars(select(UserGroupMember))).all()
        if item.group_id == group.id
    }
    if t002 is not None and (GroupMemberType.USER, t002.id) not in existing_members:
        session.add(
            UserGroupMember(
                group_id=group.id,
                member_type=GroupMemberType.USER,
                member_id=t002.id,
                user_id=t002.id,
                display_name="学工处教师",
            )
        )
    if s001 is not None and (GroupMemberType.USER, s001.id) not in existing_members:
        session.add(
            UserGroupMember(
                group_id=group.id,
                member_type=GroupMemberType.USER,
                member_id=s001.id,
                user_id=s001.id,
                display_name="学生会干部",
            )
        )

    event = await session.scalar(
        select(CalendarEvent).where(CalendarEvent.title == "校园安全工作会议")
    )
    if event is None and admin is not None:
        start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
        event = CalendarEvent(
            title="校园安全工作会议",
            description="讨论本周校园安全检查与整改安排。",
            location="行政楼 302 会议室",
            start_at=start,
            end_at=start + timedelta(hours=1),
            kind=CalendarEventKind.MEETING,
            visibility=CalendarVisibility.SCHOOL,
            owner_id=admin.id,
            created_by=admin.id,
            remind_minutes=15,
        )
        session.add(event)
        await session.flush()
        for user in (admin, t002, s001):
            if user is not None:
                session.add(
                    CalendarEventAttendee(
                        event_id=event.id,
                        user_id=user.id,
                        response=ParticipantResponse.ACCEPTED,
                    )
                )
    await session.commit()


async def _seed_leave_demo(session: AsyncSession) -> None:
    """一条待班主任审批的学生请假，便于演示审批队列。"""
    student = await session.scalar(select(Student).where(Student.student_no == "S001"))
    if student is None:
        return
    exists = await session.scalar(select(LeaveRequest).where(LeaveRequest.student_id == student.id))
    if exists is not None:
        return
    start = datetime.now() + timedelta(days=1)
    request = LeaveRequest(
        applicant_user_id=student.user_id,
        applicant_type=ApplicantType.STUDENT,
        student_id=student.id,
        leave_type=LeaveType.PERSONAL,
        start_at=start,
        end_at=start + timedelta(days=1),
        days=1.0,
        reason="家中有事，申请事假一天。",
        status=LeaveStatus.PENDING,
        current_step=1,
        required_steps=1,
    )
    session.add(request)
    await session.flush()
    session.add(
        LeaveApproval(
            leave_request_id=request.id,
            step_no=1,
            approver_role_code="head_teacher",
        )
    )
    await session.commit()


async def seed() -> dict[str, Any]:
    """建表并写入演示数据。"""
    settings = get_settings()
    engine = build_engine(settings.database_url)
    await create_schema(engine)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            departments, subjects = await _seed_org(session)
            await _seed_people(session, departments, subjects)
            await _seed_courses(session)
            await _seed_schedules(session)
            await _seed_academics(session)
            await _seed_course_links(session)
            await _seed_attendance(session)
            await _seed_dorms(session)
            await _seed_fees(session)
            await AuthzService(session).sync_defaults()
            await LeaveService(session).ensure_default_policies()
            await LeaveService(session).ensure_default_flows()
            await SystemSettingService(session).ensure_defaults()
            await _seed_duty_roles(session)
            await _seed_notices(session)
            await _seed_collab(session)
            await _seed_leave_demo(session)
            counts = {
                "users": len((await session.scalars(select(User))).all()),
                "students": len((await session.scalars(select(Student))).all()),
                "courses": len((await session.scalars(select(Course))).all()),
                "enrollments": len((await session.scalars(select(Enrollment))).all()),
                "scores": len((await session.scalars(select(Score))).all()),
                "schedules": len((await session.scalars(select(Schedule))).all()),
            }
    finally:
        await engine.dispose()
    logger.info("演示数据就绪：%s", counts)
    return counts


def main() -> None:
    """命令行入口。"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(seed())


if __name__ == "__main__":
    main()
