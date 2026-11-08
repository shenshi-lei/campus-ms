"""v1 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from campus.api.v1 import (
    accounts,
    attendance,
    audit,
    auth,
    authz,
    calendar,
    classes,
    courses,
    dashboard,
    dorms,
    enrollments,
    fees,
    groups,
    health,
    leaves,
    notices,
    notifications,
    org,
    reports,
    schedules,
    scores,
    settings,
    students,
    teachers,
    teaching,
    transfer,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(authz.router)
api_router.include_router(org.router)
api_router.include_router(leaves.router)
api_router.include_router(calendar.router)
api_router.include_router(groups.router)
api_router.include_router(notifications.router)
api_router.include_router(settings.router)
api_router.include_router(notices.router)
api_router.include_router(teaching.router)
api_router.include_router(accounts.router)
api_router.include_router(audit.router)
api_router.include_router(transfer.router)
api_router.include_router(reports.router)
api_router.include_router(students.router)
api_router.include_router(teachers.router)
api_router.include_router(classes.router)
api_router.include_router(courses.router)
api_router.include_router(enrollments.router)
api_router.include_router(scores.router)
api_router.include_router(attendance.router)
api_router.include_router(schedules.router)
api_router.include_router(dorms.router)
api_router.include_router(fees.router)
api_router.include_router(dashboard.router)
