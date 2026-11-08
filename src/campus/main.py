"""应用工厂：中间件、异常处理、路由挂载与静态托管。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from campus import __version__
from campus.api.v1 import api_router
from campus.core.config import Settings, get_settings
from campus.core.exceptions import AppError
from campus.core.logging import configure_logging
from campus.db.init_db import init_db
from campus.db.session import engine as default_engine
from campus.models.audit import AuditLog
from campus.services.authz import AuthzService
from campus.services.leave import LeaveService
from campus.services.setting import SystemSettingService

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent / "web"


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """把领域异常转换为统一错误体。"""
    if not isinstance(exc, AppError):
        raise exc
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """把 Pydantic 校验失败转换为字段级错误。"""
    if not isinstance(exc, RequestValidationError):
        raise exc
    details: list[dict[str, Any]] = [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "请求参数校验失败", "details": details},
    )


async def integrity_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """兜底转换数据库唯一约束冲突。"""
    if not isinstance(exc, IntegrityError):
        raise exc
    return JSONResponse(
        status_code=409,
        content={
            "code": "DUPLICATE_KEY",
            "message": "数据违反唯一约束或外键约束",
            "details": [],
        },
    )


def create_app(settings: Settings | None = None, engine: AsyncEngine | None = None) -> FastAPI:
    """构建 FastAPI 应用；测试可注入临时配置与引擎。"""
    app_settings = settings or get_settings()
    app_engine = engine or default_engine

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        configure_logging(app_settings.log_level)
        await init_db(app_engine)
        async with app.state.session_factory() as session:
            await AuthzService(session).sync_defaults()
            await LeaveService(session).ensure_default_policies()
            await LeaveService(session).ensure_default_flows()
            await SystemSettingService(session).ensure_defaults()
        yield
        await app_engine.dispose()

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        description="校园管理系统 API：学生、教师、课程、选课、成绩、考勤、宿舍与缴费。",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.session_factory = async_sessionmaker(
        app_engine, class_=AsyncSession, expire_on_commit=False
    )

    @app.middleware("http")
    async def audit_writes(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """写请求统一留痕；审计失败不影响业务响应。"""
        response = await call_next(request)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.url.path.endswith(
            "/auth/login"
        ):
            factory = app.state.session_factory
            try:
                user = getattr(request.state, "current_user", None)
                async with factory() as session:
                    session.add(
                        AuditLog(
                            user_id=user.id if user is not None else None,
                            username=user.username if user is not None else "",
                            role=user.role.value if user is not None else "",
                            method=request.method,
                            path=request.url.path,
                            status_code=response.status_code,
                            ip=request.client.host if request.client else "",
                        )
                    )
                    await session.commit()
            except Exception:  # noqa: BLE001 - 审计失败不应影响主流程
                logger.exception("写入审计日志失败")
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.include_router(api_router, prefix="/api/v1")

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app


app = create_app()
