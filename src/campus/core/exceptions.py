"""领域异常：统一错误码与 HTTP 状态码映射。"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """所有业务异常的基类。"""

    status_code: int = 400
    code: str = "BAD_REQUEST"
    message: str = "请求无法处理"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.message = message or type(self).message
        self.details: list[dict[str, Any]] = details or []
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        """转换为统一错误响应体。"""
        return {"code": self.code, "message": self.message, "details": self.details}


class UnauthenticatedError(AppError):
    """未登录或令牌无效。"""

    status_code = 401
    code = "UNAUTHENTICATED"
    message = "请先登录"


class TokenExpiredError(UnauthenticatedError):
    """令牌已过期。"""

    code = "TOKEN_EXPIRED"
    message = "登录已过期，请重新登录"


class PermissionDeniedError(AppError):
    """角色或数据归属不允许。"""

    status_code = 403
    code = "FORBIDDEN"
    message = "没有权限执行该操作"


class NotFoundError(AppError):
    """资源不存在。"""

    status_code = 404
    code = "NOT_FOUND"
    message = "资源不存在"


class ConflictError(AppError):
    """与现有状态冲突。"""

    status_code = 409
    code = "CONFLICT"
    message = "操作与当前状态冲突"


class DuplicateKeyError(ConflictError):
    """唯一键冲突。"""

    code = "DUPLICATE_KEY"
    message = "该记录已存在"


class CourseFullError(ConflictError):
    """课程容量已满。"""

    code = "COURSE_FULL"
    message = "课程容量已满"


class AlreadyEnrolledError(ConflictError):
    """重复选课。"""

    code = "ALREADY_ENROLLED"
    message = "已经选过该课程"


class ScoreLockedError(ConflictError):
    """已有成绩，禁止退课。"""

    code = "SCORE_LOCKED"
    message = "该课程已录入成绩，不能退课"


class ReferenceExistsError(ConflictError):
    """存在关联数据，禁止操作。"""

    code = "REFERENCE_EXISTS"
    message = "存在关联数据，无法执行该操作"
