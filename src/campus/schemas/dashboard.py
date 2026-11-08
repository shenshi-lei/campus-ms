"""仪表盘统计契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """首页关键指标（兼容旧接口）。"""

    students: int
    teachers: int
    courses: int
    classes: int
    enrollments: int
    attendance_rate: float
    unpaid_fees: int
    unpaid_amount: float
    average_score: float


class DashboardAction(BaseModel):
    """仪表盘卡片的下钻目标。"""

    view: str
    filters: dict[str, str] = Field(default_factory=dict)


class Kpi(BaseModel):
    """单个关键指标卡。"""

    key: str
    label: str
    value: float
    unit: str = ""
    delta: float | None = None
    hint: str = ""
    spark: list[float] = Field(default_factory=list)
    action: DashboardAction | None = None


class TrendSeries(BaseModel):
    """趋势图的一条序列。"""

    name: str
    data: list[int] = Field(default_factory=list)


class AttendanceTrend(BaseModel):
    """按天聚合的考勤趋势。"""

    labels: list[str] = Field(default_factory=list)
    series: list[TrendSeries] = Field(default_factory=list)
    rate: float = 0.0


class ScoreBucket(BaseModel):
    """成绩分布的一个区间。"""

    label: str
    count: int


class ScoreDistribution(BaseModel):
    """成绩分布与及格率。"""

    buckets: list[ScoreBucket] = Field(default_factory=list)
    sample: int = 0
    pass_rate: float = 0.0
    average: float = 0.0


class FeeBreakdown(BaseModel):
    """费用收缴构成。"""

    paid_count: int = 0
    unpaid_count: int = 0
    overdue_count: int = 0
    paid_amount: float = 0.0
    unpaid_amount: float = 0.0
    overdue_amount: float = 0.0
    collection_rate: float = 0.0


class CourseLoadItem(BaseModel):
    """课程容量饱和度。"""

    course_id: int
    code: str
    name: str
    teacher_name: str = ""
    enrolled: int
    capacity: int
    rate: float


class ClassComparisonItem(BaseModel):
    """班级横向对比。"""

    class_id: int
    name: str
    students: int
    average_score: float
    attendance_rate: float


class AlertItem(BaseModel):
    """需要处理的异常或待办。"""

    level: Literal["danger", "warning", "info"]
    title: str
    detail: str
    action: DashboardAction | None = None


class RecentItem(BaseModel):
    """最近动态。"""

    kind: Literal["enrollment", "score", "fee", "attendance"]
    text: str
    at: datetime


class PersonalScheduleItem(BaseModel):
    """今日课表条目。"""

    period: str
    course: str
    classroom: str


class TodayEventItem(BaseModel):
    """首页今日日程条目。"""

    id: int
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    location: str = ""
    kind: str = ""
    color: str = ""


class StudentPanel(BaseModel):
    """学生专属面板。"""

    gpa: float
    credits: float
    attendance_rate: float
    unpaid_amount: float
    failed_courses: int = 0
    today: list[PersonalScheduleItem] = Field(default_factory=list)


class TeacherCourseItem(BaseModel):
    """教师单门课程的教学进度。"""

    course_id: int
    code: str
    name: str
    students: int
    attendance_rate: float
    scored: int
    pending: int


class TeacherPanel(BaseModel):
    """教师专属面板。"""

    courses: list[TeacherCourseItem] = Field(default_factory=list)
    pending_scores: int = 0
    today: list[PersonalScheduleItem] = Field(default_factory=list)


class DashboardOverview(BaseModel):
    """仪表盘聚合响应。"""

    role: str
    semester: str
    generated_at: datetime
    days: int
    kpis: list[Kpi] = Field(default_factory=list)
    attendance_trend: AttendanceTrend = Field(default_factory=AttendanceTrend)
    score_distribution: ScoreDistribution = Field(default_factory=ScoreDistribution)
    fee_breakdown: FeeBreakdown = Field(default_factory=FeeBreakdown)
    course_load: list[CourseLoadItem] = Field(default_factory=list)
    class_comparison: list[ClassComparisonItem] = Field(default_factory=list)
    alerts: list[AlertItem] = Field(default_factory=list)
    recent: list[RecentItem] = Field(default_factory=list)
    today_events: list[TodayEventItem] = Field(default_factory=list)
    today_courses: list[PersonalScheduleItem] = Field(default_factory=list)
    pending_approvals: int = 0
    student: StudentPanel | None = None
    teacher: TeacherPanel | None = None
