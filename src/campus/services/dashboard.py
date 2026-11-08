"""仪表盘统计服务。"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from campus.models.course import Course
from campus.models.enrollment import Enrollment
from campus.models.enums import AttendanceStatus, FeeStatus, Role
from campus.models.fee import Fee
from campus.models.score import Score
from campus.models.student import Student
from campus.models.user import User
from campus.repositories.academics import (
    CourseRepository,
    EnrollmentRepository,
    ScoreRepository,
)
from campus.repositories.extras import AttendanceRepository, FeeRepository, ScheduleRepository
from campus.repositories.org import SemesterRepository
from campus.repositories.people import (
    SchoolClassRepository,
    StudentRepository,
    TeacherRepository,
)
from campus.schemas.dashboard import (
    AlertItem,
    AttendanceTrend,
    ClassComparisonItem,
    CourseLoadItem,
    DashboardAction,
    DashboardOverview,
    DashboardSummary,
    FeeBreakdown,
    Kpi,
    PersonalScheduleItem,
    RecentItem,
    ScoreBucket,
    ScoreDistribution,
    StudentPanel,
    TeacherCourseItem,
    TeacherPanel,
    TodayEventItem,
    TrendSeries,
)
from campus.services.access import AccessContext, Permission
from campus.services.calendar import CalendarService
from campus.services.leave import LeaveService
from campus.services.permissions import current_student_id, current_teacher_id

ATTENDANCE_STATUSES = (
    AttendanceStatus.PRESENT,
    AttendanceStatus.LATE,
    AttendanceStatus.ABSENT,
    AttendanceStatus.LEAVE,
)
STATUS_LABEL = {
    AttendanceStatus.PRESENT: "出勤",
    AttendanceStatus.LATE: "迟到",
    AttendanceStatus.ABSENT: "缺勤",
    AttendanceStatus.LEAVE: "请假",
}
SCORE_BUCKETS = ("<60", "60-69", "70-79", "80-89", "90-100")
EFFECTIVE_STATUSES = {AttendanceStatus.PRESENT, AttendanceStatus.LATE}


def _rate(effective: int, total: int) -> float:
    """计算百分比，保留一位小数。"""
    if total <= 0:
        return 0.0
    return round(effective * 100.0 / total, 1)


def _grade_point(score: float) -> float:
    """把百分制总分映射为 4.0 制绩点。"""
    if score >= 90:
        return 4.0
    if score >= 85:
        return 3.7
    if score >= 82:
        return 3.3
    if score >= 78:
        return 3.0
    if score >= 75:
        return 2.7
    if score >= 72:
        return 2.3
    if score >= 68:
        return 2.0
    if score >= 64:
        return 1.5
    if score >= 60:
        return 1.0
    return 0.0


def _rate_from_counts(counts: dict[AttendanceStatus, int]) -> float:
    total = sum(counts.values())
    effective = counts.get(AttendanceStatus.PRESENT, 0) + counts.get(AttendanceStatus.LATE, 0)
    return _rate(effective, total)


def _build_trend(
    rows: list[tuple[date, AttendanceStatus, int]], days: int
) -> tuple[AttendanceTrend, list[float], dict[AttendanceStatus, int]]:
    """把考勤行转换为按天补齐的趋势数据。"""
    index: dict[date, dict[AttendanceStatus, int]] = defaultdict(dict)
    for day, status, count in rows:
        index[day][status] = count
    today = date.today()
    labels: list[str] = []
    daily: list[dict[AttendanceStatus, int]] = []
    for offset in range(days):
        day = today - timedelta(days=days - 1 - offset)
        labels.append(day.strftime("%m-%d"))
        daily.append({status: index.get(day, {}).get(status, 0) for status in ATTENDANCE_STATUSES})
    totals = {status: sum(item[status] for item in daily) for status in ATTENDANCE_STATUSES}
    series = [
        TrendSeries(name=STATUS_LABEL[status], data=[item[status] for item in daily])
        for status in ATTENDANCE_STATUSES
    ]
    sparks = [
        _rate(item[AttendanceStatus.PRESENT] + item[AttendanceStatus.LATE], sum(item.values()))
        for item in daily
    ]
    return (
        AttendanceTrend(labels=labels, series=series, rate=_rate_from_counts(totals)),
        sparks,
        totals,
    )


def _trend_delta(sparks: list[float]) -> float | None:
    """用最近 7 天与前 7 天的均值差表示变化。"""
    if len(sparks) < 14:
        return None
    recent = sum(sparks[-7:]) / 7
    previous = sum(sparks[-14:-7]) / 7
    return round(recent - previous, 1)


def _distribution(
    rows: list[tuple[str, int]], summary: tuple[float, int, int]
) -> ScoreDistribution:
    counts = dict(rows)
    average, sample, passed = summary
    return ScoreDistribution(
        buckets=[ScoreBucket(label=label, count=counts.get(label, 0)) for label in SCORE_BUCKETS],
        sample=sample,
        pass_rate=_rate(passed, sample),
        average=round(average, 2),
    )


def _fee_breakdown(
    rows: list[tuple[FeeStatus, int, float]], overdue_count: int, overdue_amount: float
) -> FeeBreakdown:
    paid_count = unpaid_count = 0
    paid_amount = unpaid_amount = refunded_amount = 0.0
    for status, count, amount in rows:
        if status is FeeStatus.PAID:
            paid_count, paid_amount = count, amount
        elif status is FeeStatus.UNPAID:
            unpaid_count, unpaid_amount = count, amount
        else:
            refunded_amount = amount
    total_amount = paid_amount + unpaid_amount + refunded_amount
    return FeeBreakdown(
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        overdue_count=overdue_count,
        paid_amount=round(paid_amount, 2),
        unpaid_amount=round(unpaid_amount, 2),
        overdue_amount=round(overdue_amount, 2),
        collection_rate=_rate(round(paid_amount), round(total_amount)),
    )


def _class_rates(rows: list[tuple[int, AttendanceStatus, int]]) -> dict[int, tuple[int, int]]:
    effective: dict[int, int] = defaultdict(int)
    totals: dict[int, int] = defaultdict(int)
    for class_id, status, count in rows:
        totals[class_id] += count
        if status in EFFECTIVE_STATUSES:
            effective[class_id] += count
    return {class_id: (effective[class_id], totals[class_id]) for class_id in totals}


def _merge_recent(
    enrollments: list[tuple[Enrollment, Student, Course]],
    scores: list[tuple[Score, Student, Course]],
    payments: list[tuple[Fee, Student]],
) -> list[RecentItem]:
    items: list[tuple[datetime, RecentItem]] = []
    for enrollment, student, course in enrollments:
        at = enrollment.created_at
        items.append(
            (at, RecentItem(kind="enrollment", text=f"{student.name} 选修了 {course.name}", at=at))
        )
    for score, student, course in scores:
        at = score.recorded_at
        items.append(
            (at, RecentItem(kind="score", text=f"{student.name} · {course.name} 成绩已录入", at=at))
        )
    for fee, student in payments:
        paid_at = fee.paid_at
        if paid_at is None:
            continue
        items.append(
            (
                paid_at,
                RecentItem(
                    kind="fee",
                    text=f"{student.name} 缴纳 {fee.item} ¥{float(fee.amount):,.2f}",
                    at=paid_at,
                ),
            )
        )
    items.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in items[:6]]


class DashboardService:
    """聚合首页指标。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summary(self) -> DashboardSummary:
        students = await StudentRepository(self.session).count_active()
        teachers = await TeacherRepository(self.session).count_active()
        courses = await CourseRepository(self.session).count_all()
        classes = await SchoolClassRepository(self.session).count_all()
        enrollments = await EnrollmentRepository(self.session).count_all()
        attendance_rate = await AttendanceRepository(self.session).attendance_rate()
        unpaid_count, unpaid_amount = await FeeRepository(self.session).unpaid_summary()
        average_score = await ScoreRepository(self.session).average_final()
        return DashboardSummary(
            students=students,
            teachers=teachers,
            courses=courses,
            classes=classes,
            enrollments=enrollments,
            attendance_rate=attendance_rate,
            unpaid_fees=unpaid_count,
            unpaid_amount=round(unpaid_amount, 2),
            average_score=round(average_score, 2),
        )

    async def overview(self, access: AccessContext, *, days: int = 30) -> DashboardOverview:
        """按角色返回仪表盘聚合数据。"""
        user = access.user
        current_semester = await SemesterRepository(self.session).get_current()
        semester = (
            current_semester.name
            if current_semester is not None
            else await CourseRepository(self.session).latest_semester() or "2024-2025-1"
        )
        if user.role is Role.TEACHER:
            overview = await self._teacher_overview(user, days=days, semester=semester)
        elif user.role is Role.STUDENT:
            overview = await self._student_overview(user, days=days, semester=semester)
        else:
            overview = await self._admin_overview(days=days, semester=semester)
        overview.today_events = await self._today_events(access)
        overview.pending_approvals = await self._pending_approvals(access)
        if overview.student is not None:
            overview.today_courses = overview.student.today
        elif overview.teacher is not None:
            overview.today_courses = overview.teacher.today
        return overview

    async def _today_events(self, access: AccessContext) -> list[TodayEventItem]:
        try:
            events = await CalendarService(self.session).today(access)
        except Exception:  # noqa: BLE001 - 日程异常不影响首页
            return []
        return [
            TodayEventItem(
                id=item.id,
                title=item.title,
                start_at=item.start_at,
                end_at=item.end_at,
                all_day=item.all_day,
                location=item.location,
                kind=item.kind.value,
                color=item.color,
            )
            for item in events
        ]

    async def _pending_approvals(self, access: AccessContext) -> int:
        if not access.can(Permission.LEAVE_APPROVE):
            return 0
        try:
            page = await LeaveService(self.session).pending(access, page=1, page_size=1)
        except Exception:  # noqa: BLE001 - 审批统计失败不影响首页
            return 0
        return page.total

    @staticmethod
    def _base(role: str, semester: str, days: int) -> DashboardOverview:
        return DashboardOverview(
            role=role,
            semester=semester,
            generated_at=datetime.now(UTC),
            days=days,
        )

    async def _admin_overview(self, *, days: int, semester: str) -> DashboardOverview:
        student_repo = StudentRepository(self.session)
        teacher_repo = TeacherRepository(self.session)
        course_repo = CourseRepository(self.session)
        enrollment_repo = EnrollmentRepository(self.session)
        score_repo = ScoreRepository(self.session)
        attendance_repo = AttendanceRepository(self.session)
        fee_repo = FeeRepository(self.session)
        class_repo = SchoolClassRepository(self.session)

        overview = self._base("admin", semester, days)
        students = await student_repo.count_active()
        teachers = await teacher_repo.count_active()
        courses = await course_repo.count_all()
        classes = await class_repo.count_all()

        trend, sparks, counts = _build_trend(await attendance_repo.daily_counts(days=days), days)
        attendance_rate = _rate_from_counts(counts)

        distribution = _distribution(await score_repo.distribution(), await score_repo.summary())

        today = date.today()
        overdue_count, overdue_amount = await fee_repo.overdue_summary(today=today)
        fees = _fee_breakdown(await fee_repo.status_breakdown(), overdue_count, overdue_amount)

        teacher_names = await teacher_repo.list_names()
        course_load = [
            CourseLoadItem(
                course_id=course.id,
                code=course.code,
                name=course.name,
                teacher_name=teacher_names.get(course.teacher_id or 0, "未指定"),
                enrolled=enrolled,
                capacity=course.capacity,
                rate=_rate(enrolled, course.capacity),
            )
            for course, enrolled in await course_repo.utilization(limit=8)
        ]

        class_counts = await student_repo.count_by_class()
        class_scores = await score_repo.average_by_class()
        class_rates = _class_rates(await attendance_repo.class_status_counts())
        comparison: list[ClassComparisonItem] = []
        for school_class in await class_repo.list_all():
            size = class_counts.get(school_class.id, 0)
            if size == 0:
                continue
            effective, total = class_rates.get(school_class.id, (0, 0))
            comparison.append(
                ClassComparisonItem(
                    class_id=school_class.id,
                    name=school_class.name,
                    students=size,
                    average_score=round(class_scores.get(school_class.id, 0.0), 1),
                    attendance_rate=_rate(effective, total),
                )
            )
        comparison.sort(key=lambda item: item.average_score, reverse=True)

        alerts: list[AlertItem] = []
        if overdue_count:
            alerts.append(
                AlertItem(
                    level="danger",
                    title=f"{overdue_count} 笔费用已逾期",
                    detail=f"¥{overdue_amount:,.2f}",
                    action=DashboardAction(view="fees", filters={"status": "unpaid"}),
                )
            )
        over_capacity = await course_repo.count_over_capacity()
        if over_capacity:
            alerts.append(
                AlertItem(
                    level="warning",
                    title=f"{over_capacity} 门课程已达容量上限",
                    detail="建议扩容或引导改选",
                    action=DashboardAction(view="courses"),
                )
            )
        unscheduled = await course_repo.count_without_schedule()
        if unscheduled:
            alerts.append(
                AlertItem(
                    level="info",
                    title=f"{unscheduled} 门课程尚未排课",
                    detail="学生课表不会显示这些课程",
                    action=DashboardAction(view="schedules"),
                )
            )
        unscored = await course_repo.count_without_scores()
        if unscored:
            alerts.append(
                AlertItem(
                    level="info",
                    title=f"{unscored} 门课程尚未录入成绩",
                    detail="可在成绩管理中批量录入",
                    action=DashboardAction(view="scores"),
                )
            )
        absent = await attendance_repo.absent_students(days=14, limit=3)
        if absent:
            names = "、".join(student.name for student, _ in absent)
            alerts.append(
                AlertItem(
                    level="warning",
                    title=f"近 14 天有 {len(absent)} 名学生多次缺勤",
                    detail=f"{names} 等",
                    action=DashboardAction(view="attendance"),
                )
            )

        recent = _merge_recent(
            await enrollment_repo.recent(limit=5),
            await score_repo.recent(limit=5),
            await fee_repo.recent_payments(limit=5),
        )

        overview.class_comparison = comparison[:6]
        overview.kpis = [
            Kpi(
                key="students",
                label="在校学生",
                value=float(students),
                unit="人",
                hint=f"教师 {teachers} 人 · 在册且启用",
                action=DashboardAction(view="students"),
            ),
            Kpi(
                key="courses",
                label="开设课程",
                value=float(courses),
                unit="门",
                hint=f"{semester} · {classes} 个班级",
                action=DashboardAction(view="courses"),
            ),
            Kpi(
                key="attendance",
                label="平均出勤率",
                value=attendance_rate,
                unit="%",
                delta=_trend_delta(sparks),
                hint=f"近 {days} 天 · 出勤+迟到",
                spark=sparks,
                action=DashboardAction(view="attendance"),
            ),
            Kpi(
                key="score",
                label="平均总分",
                value=round(distribution.average, 1),
                unit="分",
                hint=f"样本 {distribution.sample} 份 · 及格率 {distribution.pass_rate}%",
                action=DashboardAction(view="scores"),
            ),
            Kpi(
                key="fees",
                label="待缴金额",
                value=round(fees.unpaid_amount, 2),
                unit="元",
                hint=f"{fees.unpaid_count} 笔 · 逾期 {fees.overdue_count} 笔",
                action=DashboardAction(view="fees", filters={"status": "unpaid"}),
            ),
        ]
        overview.attendance_trend = trend
        overview.score_distribution = distribution
        overview.fee_breakdown = fees
        overview.course_load = course_load
        overview.alerts = alerts
        overview.recent = recent
        return overview

    async def _teacher_overview(self, user: User, *, days: int, semester: str) -> DashboardOverview:
        overview = self._base("teacher", semester, days)
        teacher_id = await current_teacher_id(self.session, user)
        if teacher_id is None:
            return overview

        course_repo = CourseRepository(self.session)
        courses = await course_repo.list_for_teacher(teacher_id)
        if not courses:
            return overview
        course_ids = [course.id for course in courses]

        enrollment_repo = EnrollmentRepository(self.session)
        enrolled = await enrollment_repo.counts_by_course(course_ids=course_ids)
        attendance_repo = AttendanceRepository(self.session)
        trend, sparks, counts = _build_trend(
            await attendance_repo.daily_counts(days=days, course_ids=course_ids), days
        )
        attendance_rate = _rate_from_counts(counts)
        score_repo = ScoreRepository(self.session)
        distribution = _distribution(
            await score_repo.distribution(course_ids=course_ids),
            await score_repo.summary(course_ids=course_ids),
        )
        scored = await score_repo.counts_by_course(course_ids)

        course_attendance: dict[int, tuple[int, int]] = {}
        for course_id, status, count in await attendance_repo.course_status_counts(
            course_ids=course_ids, days=days
        ):
            effective, total = course_attendance.get(course_id, (0, 0))
            course_attendance[course_id] = (
                effective + (count if status in EFFECTIVE_STATUSES else 0),
                total + count,
            )

        panel_courses: list[TeacherCourseItem] = []
        pending_total = 0
        for course in courses:
            students = enrolled.get(course.id, 0)
            pending = max(0, students - scored.get(course.id, 0))
            pending_total += pending
            effective, total = course_attendance.get(course.id, (0, 0))
            panel_courses.append(
                TeacherCourseItem(
                    course_id=course.id,
                    code=course.code,
                    name=course.name,
                    students=students,
                    attendance_rate=_rate(effective, total),
                    scored=scored.get(course.id, 0),
                    pending=pending,
                )
            )

        weekday = date.today().isoweekday()
        today_items = [
            PersonalScheduleItem(
                period=f"{schedule.start_period}-{schedule.end_period} 节",
                course=f"{course.code} {course.name}",
                classroom=schedule.classroom or "待定",
            )
            for schedule, course in await ScheduleRepository(self.session).for_teacher(
                teacher_id, weekday
            )
        ]

        alerts: list[AlertItem] = []
        if pending_total:
            alerts.append(
                AlertItem(
                    level="warning",
                    title=f"{pending_total} 份成绩待录入",
                    detail="已选课但尚未出分",
                    action=DashboardAction(view="scores"),
                )
            )
        over_capacity = sum(
            1 for course in courses if enrolled.get(course.id, 0) >= course.capacity
        )
        if over_capacity:
            alerts.append(
                AlertItem(
                    level="info",
                    title=f"{over_capacity} 门课程已满员",
                    detail="可联系教务扩容",
                    action=DashboardAction(view="courses"),
                )
            )
        absent = await attendance_repo.absent_students(days=14, course_ids=course_ids, limit=3)
        if absent:
            names = "、".join(student.name for student, _ in absent)
            alerts.append(
                AlertItem(
                    level="warning",
                    title="有学生在近 14 天多次缺勤",
                    detail=f"{names} 等",
                    action=DashboardAction(view="attendance"),
                )
            )

        overview.kpis = [
            Kpi(
                key="my_courses",
                label="我的课程",
                value=float(len(courses)),
                unit="门",
                hint=semester,
                action=DashboardAction(view="courses"),
            ),
            Kpi(
                key="my_students",
                label="选课人次",
                value=float(sum(enrolled.values())),
                unit="人次",
                hint="我教授课程的在选人数",
            ),
            Kpi(
                key="attendance",
                label="课程出勤率",
                value=attendance_rate,
                unit="%",
                delta=_trend_delta(sparks),
                hint=f"近 {days} 天 · 出勤+迟到",
                spark=sparks,
                action=DashboardAction(view="attendance"),
            ),
            Kpi(
                key="pending",
                label="待录成绩",
                value=float(pending_total),
                unit="份",
                hint="已选课但未出分",
                action=DashboardAction(view="scores"),
            ),
            Kpi(
                key="score",
                label="平均总分",
                value=round(distribution.average, 1),
                unit="分",
                hint=f"样本 {distribution.sample} 份 · 及格率 {distribution.pass_rate}%",
                action=DashboardAction(view="scores"),
            ),
        ]
        overview.attendance_trend = trend
        overview.score_distribution = distribution
        overview.course_load = [
            CourseLoadItem(
                course_id=course.id,
                code=course.code,
                name=course.name,
                teacher_name="我的课程",
                enrolled=enrolled.get(course.id, 0),
                capacity=course.capacity,
                rate=_rate(enrolled.get(course.id, 0), course.capacity),
            )
            for course in courses
        ]
        overview.alerts = alerts
        overview.recent = _merge_recent(
            await enrollment_repo.recent(course_ids=course_ids, limit=5),
            await score_repo.recent(course_ids=course_ids, limit=5),
            [],
        )
        overview.teacher = TeacherPanel(
            courses=panel_courses,
            pending_scores=pending_total,
            today=today_items,
        )
        return overview

    async def _student_overview(self, user: User, *, days: int, semester: str) -> DashboardOverview:
        overview = self._base("student", semester, days)
        student_id = await current_student_id(self.session, user)

        attendance_repo = AttendanceRepository(self.session)
        trend, sparks, counts = _build_trend(
            await attendance_repo.daily_counts(days=days, student_id=student_id), days
        )
        attendance_rate = _rate_from_counts(counts)

        score_repo = ScoreRepository(self.session)
        distribution = _distribution(
            await score_repo.distribution(student_id=student_id),
            await score_repo.summary(student_id=student_id),
        )
        rows = await score_repo.scores_with_credits(student_id)
        credit_sum = sum(credit for _, credit in rows)
        gpa = (
            round(sum(_grade_point(score) * credit for score, credit in rows) / credit_sum, 2)
            if credit_sum
            else 0.0
        )
        earned_credits = round(sum(credit for score, credit in rows if score >= 60), 1)
        failed = await score_repo.failed_count(student_id)

        today = date.today()
        fee_repo = FeeRepository(self.session)
        overdue_count, overdue_amount = await fee_repo.overdue_summary(
            today=today, student_id=student_id
        )
        fees = _fee_breakdown(
            await fee_repo.status_breakdown(student_id=student_id),
            overdue_count,
            overdue_amount,
        )

        weekday = today.isoweekday()
        today_items = [
            PersonalScheduleItem(
                period=f"{schedule.start_period}-{schedule.end_period} 节",
                course=f"{course.code} {course.name}",
                classroom=schedule.classroom or "待定",
            )
            for schedule, course in await ScheduleRepository(self.session).for_student(
                student_id, weekday
            )
        ]

        alerts: list[AlertItem] = []
        if overdue_count:
            alerts.append(
                AlertItem(
                    level="danger",
                    title=f"{overdue_count} 笔费用已逾期",
                    detail=f"¥{overdue_amount:,.2f}",
                    action=DashboardAction(view="fees", filters={"status": "unpaid"}),
                )
            )
        if attendance_rate and attendance_rate < 90:
            alerts.append(
                AlertItem(
                    level="warning",
                    title="出勤率低于 90%",
                    detail=f"近 {days} 天为 {attendance_rate}%",
                    action=DashboardAction(view="attendance"),
                )
            )
        if failed:
            alerts.append(
                AlertItem(
                    level="danger",
                    title=f"{failed} 门课程不及格",
                    detail="请及时关注补考安排",
                    action=DashboardAction(view="scores"),
                )
            )

        overview.kpis = [
            Kpi(
                key="gpa",
                label="我的 GPA",
                value=gpa,
                unit="",
                hint="4.0 制加权",
                action=DashboardAction(view="scores"),
            ),
            Kpi(
                key="credits",
                label="已修学分",
                value=earned_credits,
                unit="分",
                hint=f"已选 {len(rows)} 门出分课程",
                action=DashboardAction(view="courses"),
            ),
            Kpi(
                key="attendance",
                label="我的出勤率",
                value=attendance_rate,
                unit="%",
                delta=_trend_delta(sparks),
                hint=f"近 {days} 天 · 出勤+迟到",
                spark=sparks,
                action=DashboardAction(view="attendance"),
            ),
            Kpi(
                key="fees",
                label="待缴金额",
                value=round(fees.unpaid_amount, 2),
                unit="元",
                hint=f"{fees.unpaid_count} 笔 · 逾期 {fees.overdue_count} 笔",
                action=DashboardAction(view="fees", filters={"status": "unpaid"}),
            ),
            Kpi(
                key="failed",
                label="不及格课程",
                value=float(failed),
                unit="门",
                hint="总分低于 60",
                action=DashboardAction(view="scores"),
            ),
        ]
        overview.attendance_trend = trend
        overview.score_distribution = distribution
        overview.fee_breakdown = fees
        overview.alerts = alerts
        overview.recent = _merge_recent(
            await EnrollmentRepository(self.session).recent(student_id=student_id, limit=5),
            await score_repo.recent(student_id=student_id, limit=5),
            await fee_repo.recent_payments(student_id=student_id, limit=5),
        )
        overview.student = StudentPanel(
            gpa=gpa,
            credits=earned_credits,
            attendance_rate=attendance_rate,
            unpaid_amount=round(fees.unpaid_amount, 2),
            failed_courses=failed,
            today=today_items,
        )
        return overview
