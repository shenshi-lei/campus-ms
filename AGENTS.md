# AGENTS.md — campus-ms 工程规范

本文件是 `campus-ms` 的唯一权威规范。所有人和 AI 代理在新增、修改代码前必须先读本文件；
实现与本文件冲突时，以本文件为准，并同步更新本文件与第 2 节的目录清单。

本规范是**可执行**的：目录清单由 `tests/test_agents_md.py` 校验存在性，
文中所有 `python` 代码块由同一测试通过 `ast.parse` 校验语法，风格规则由 `ruff`/`mypy` 门禁强制执行。

---

## 1. 项目概览

- 名称：`campus-ms`（校园管理系统）
- 形态：FastAPI JSON API（`/api/v1`）+ SQLite + 无构建步骤的原生 JS 静态前端
- Python：3.11+（开发基线 3.12）
- 分层：`api → services → repositories → models`，`schemas` 为横切契约层，`db`/`core` 为基础设施
- 业务范围：学生/教师/班级/课程、选课退课、成绩录入、考勤、课表、宿舍、缴费、仪表盘

---

## 2. 目录结构与机器校验清单

目录职责：

```text
campus-ms/
├── AGENTS.md                本规范
├── README.md                快速开始
├── pyproject.toml           依赖与 ruff/mypy/pytest 配置
├── alembic.ini              迁移入口
├── .env.example             配置样例（真实 .env 不入库）
├── src/campus/              应用包（src layout）
│   ├── main.py              应用工厂 create_app()
│   ├── core/                配置、安全、异常、分页、日志
│   ├── db/                  引擎、会话、建表、种子
│   ├── models/              SQLAlchemy ORM 模型
│   ├── schemas/             Pydantic v2 请求/响应契约
│   ├── repositories/        数据访问（只写查询，不含业务规则）
│   ├── services/            业务规则与权限校验
│   ├── api/                 依赖注入 + /api/v1 路由
│   └── web/                 静态前端（index.html + assets）
├── migrations/              Alembic 迁移
├── tests/                   单元测试与接口测试
├── docs/                    架构与 API 文档
└── scripts/                 开发辅助脚本
```

机器校验清单（新增/删除文件必须同步本节，否则 `pytest` 失败）：

<!-- TREE:BEGIN -->
.env.example
.gitignore
AGENTS.md
README.md
alembic.ini
docs/API.md
docs/ARCHITECTURE.md
docs/PLAN-v2.md
docs/screenshots/dashboard-admin.png
docs/screenshots/dashboard-mobile.png
docs/screenshots/dashboard-student.png
docs/screenshots/login.png
migrations/env.py
migrations/script.py.mako
migrations/versions/0001_initial_schema.py
migrations/versions/0002_authz.py
migrations/versions/0003_org_and_profiles.py
migrations/versions/0004_leave_notice_status.py
migrations/versions/0005_teaching_runtime.py
migrations/versions/0006_audit.py
migrations/versions/0007_leave_workflow.py
migrations/versions/0008_calendar.py
migrations/versions/0009_collab.py
pyproject.toml
scripts/dev.ps1
src/campus/__init__.py
src/campus/__main__.py
src/campus/api/__init__.py
src/campus/api/deps.py
src/campus/api/v1/__init__.py
src/campus/api/v1/accounts.py
src/campus/api/v1/attendance.py
src/campus/api/v1/audit.py
src/campus/api/v1/auth.py
src/campus/api/v1/authz.py
src/campus/api/v1/calendar.py
src/campus/api/v1/classes.py
src/campus/api/v1/courses.py
src/campus/api/v1/dashboard.py
src/campus/api/v1/dorms.py
src/campus/api/v1/enrollments.py
src/campus/api/v1/fees.py
src/campus/api/v1/groups.py
src/campus/api/v1/health.py
src/campus/api/v1/leaves.py
src/campus/api/v1/notices.py
src/campus/api/v1/notifications.py
src/campus/api/v1/org.py
src/campus/api/v1/reports.py
src/campus/api/v1/schedules.py
src/campus/api/v1/scores.py
src/campus/api/v1/settings.py
src/campus/api/v1/students.py
src/campus/api/v1/teachers.py
src/campus/api/v1/teaching.py
src/campus/api/v1/transfer.py
src/campus/core/__init__.py
src/campus/core/config.py
src/campus/core/exceptions.py
src/campus/core/logging.py
src/campus/core/pagination.py
src/campus/core/security.py
src/campus/db/__init__.py
src/campus/db/base.py
src/campus/db/init_db.py
src/campus/db/seed.py
src/campus/db/session.py
src/campus/main.py
src/campus/models/__init__.py
src/campus/models/attendance.py
src/campus/models/audit.py
src/campus/models/authz.py
src/campus/models/calendar.py
src/campus/models/course.py
src/campus/models/dorm.py
src/campus/models/enrollment.py
src/campus/models/enums.py
src/campus/models/fee.py
src/campus/models/group.py
src/campus/models/leave.py
src/campus/models/notice.py
src/campus/models/notification.py
src/campus/models/org.py
src/campus/models/schedule.py
src/campus/models/school_class.py
src/campus/models/score.py
src/campus/models/setting.py
src/campus/models/student.py
src/campus/models/teacher.py
src/campus/models/teaching.py
src/campus/models/user.py
src/campus/repositories/__init__.py
src/campus/repositories/academics.py
src/campus/repositories/accounts.py
src/campus/repositories/audit.py
src/campus/repositories/authz.py
src/campus/repositories/base.py
src/campus/repositories/calendar.py
src/campus/repositories/extras.py
src/campus/repositories/group.py
src/campus/repositories/leave.py
src/campus/repositories/notice.py
src/campus/repositories/notification.py
src/campus/repositories/org.py
src/campus/repositories/people.py
src/campus/repositories/report.py
src/campus/repositories/setting.py
src/campus/repositories/teaching.py
src/campus/schemas/__init__.py
src/campus/schemas/account.py
src/campus/schemas/attendance.py
src/campus/schemas/audit.py
src/campus/schemas/auth.py
src/campus/schemas/authz.py
src/campus/schemas/calendar.py
src/campus/schemas/common.py
src/campus/schemas/course.py
src/campus/schemas/dashboard.py
src/campus/schemas/dorm.py
src/campus/schemas/enrollment.py
src/campus/schemas/fee.py
src/campus/schemas/group.py
src/campus/schemas/leave.py
src/campus/schemas/notice.py
src/campus/schemas/notification.py
src/campus/schemas/org.py
src/campus/schemas/report.py
src/campus/schemas/schedule.py
src/campus/schemas/school_class.py
src/campus/schemas/score.py
src/campus/schemas/seat.py
src/campus/schemas/setting.py
src/campus/schemas/student.py
src/campus/schemas/student_status.py
src/campus/schemas/teacher.py
src/campus/schemas/teaching.py
src/campus/schemas/transfer.py
src/campus/services/__init__.py
src/campus/services/academics.py
src/campus/services/access.py
src/campus/services/accounts.py
src/campus/services/audit.py
src/campus/services/auth.py
src/campus/services/authz.py
src/campus/services/calendar.py
src/campus/services/dashboard.py
src/campus/services/extras.py
src/campus/services/group.py
src/campus/services/leave.py
src/campus/services/notice.py
src/campus/services/notification.py
src/campus/services/org.py
src/campus/services/people.py
src/campus/services/permissions.py
src/campus/services/report.py
src/campus/services/seat.py
src/campus/services/setting.py
src/campus/services/teaching.py
src/campus/services/timetable.py
src/campus/services/transfer.py
src/campus/web/assets/api.js
src/campus/web/assets/app.js
src/campus/web/assets/charts.js
src/campus/web/assets/components/flow.js
src/campus/web/assets/components/modal.js
src/campus/web/assets/components/table.js
src/campus/web/assets/components/tree-select.js
src/campus/web/assets/core/router.js
src/campus/web/assets/core/state.js
src/campus/web/assets/styles.css
src/campus/web/assets/ui.js
src/campus/web/assets/vendor/README.md
src/campus/web/assets/vendor/echarts.min.js
src/campus/web/assets/views/calendar.js
src/campus/web/assets/views/index.js
src/campus/web/assets/views/leaves.js
src/campus/web/assets/views/legacy.js
src/campus/web/assets/views/notifications.js
src/campus/web/assets/views/settings.js
src/campus/web/assets/views/timetable.js
src/campus/web/index.html
tests/api/test_admin.py
tests/api/test_auth.py
tests/api/test_auth_more.py
tests/api/test_authz.py
tests/api/test_calendar.py
tests/api/test_campus_life.py
tests/api/test_courses.py
tests/api/test_courses_more.py
tests/api/test_dashboard.py
tests/api/test_extras.py
tests/api/test_groups.py
tests/api/test_modules.py
tests/api/test_org.py
tests/api/test_people.py
tests/api/test_reports.py
tests/api/test_students.py
tests/api/test_teaching.py
tests/api/test_timetable.py
tests/api/test_transfer_export.py
tests/api/test_workflow.py
tests/conftest.py
tests/test_agents_md.py
tests/unit/test_access.py
tests/unit/test_config.py
tests/unit/test_security.py
tests/unit/test_services.py
tests/unit/test_weeks.py
<!-- TREE:END -->

---

## 3. 环境与命令

```powershell
# 创建虚拟环境并安装（含开发依赖）
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"

# 初始化数据库（建表 + 演示数据）
python -m campus.db.seed

# 启动开发服务
python -m uvicorn campus.main:app --reload --port 8000

# 质量门禁
python -m compileall -q src
ruff check .
ruff format --check .
mypy src
pytest --cov=campus --cov-fail-under=80
```

约定：

- 配置全部来自环境变量或 `.env`（`pydantic-settings`），应用代码中**禁止**硬编码密钥、端口、路径。
- 开发默认库为 `sqlite+aiosqlite:///./campus.db`；测试必须使用 `tmp_path` 下的临时库，**禁止**连真实库。
- 依赖必须写入 `pyproject.toml`；禁止在代码里 `pip install`。
- 后端不内置前端构建链；`web/` 由 `StaticFiles` 直接托管。

---

## 4. 语法、风格与类型

- PEP 8 + `ruff`（`line-length = 100`，规则集 `E,F,I,B,UP,SIM,C4,ASYNC`）。
- 每个包含函数或类定义的模块首行必须是 `from __future__ import annotations`；仅含 docstring 的 `__init__.py` 可省略。
- 导入顺序：标准库 → 第三方 → 本项目（`I` 规则）。
- 所有公开函数、方法必须标注参数与返回类型；禁止 `Any` 逃逸（确需时写明 `# noqa: ANN401` 理由）。
- 禁止裸 `except:`、`except Exception: pass`、可变默认参数、函数内 `print` 调试（用 `logging`）。
- 禁止在循环内发 N+1 查询；批量场景用单条 `select` 或 `bulk` 操作。
- 错误必须具体：抛 `AppError` 子类，禁止返回 `None` 表示失败。

正确写法：

```python
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campus.models.student import Student

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def clamp_page_size(page_size: int) -> int:
    """把分页大小限制在 1..100 之间。"""
    if page_size < 1:
        raise ValueError("page_size 必须为正数")
    return min(page_size, MAX_PAGE_SIZE)


async def find_active_students(session: AsyncSession, class_id: int) -> list[int]:
    """返回指定班级中在册学生的 ID。"""
    result = await session.scalars(
        select(Student.id).where(Student.class_id == class_id, Student.is_active.is_(True))
    )
    return list(result.all())


def summarize(birth_date: date | None) -> str:
    """示例：可选类型与格式化。"""
    return birth_date.isoformat() if birth_date else "-"
```

反例（禁止）：

```python
# ❌ 无类型、裸 except、print 调试、可变默认参数
def list_students(page, filters=[]):
    try:
        return db.query(page)
    except:
        print("failed")
```

---

## 5. 分层与依赖方向

| 层 | 允许依赖 | 禁止 |
| --- | --- | --- |
| `api/v1` | `services`、`schemas`、`api/deps` | SQL、`repositories` 直连 |
| `services` | `repositories`、`models`、`schemas`、`core` | `fastapi` 请求对象与 `HTTPException` |
| `repositories` | `models`、`db`、`sqlalchemy` | 业务规则、权限判断、事务提交 |
| `models` | `db/base` | 导入 `services`/`api` |
| `schemas` | `models/enums` | 导入 ORM 实例做动态计算 |

硬性规则：

1. 路由函数只做：解析入参 → 调用一个 service → 返回 schema，单函数不超过 30 行。
2. 事务边界在 service：写入后 `await session.commit()`；repository 只 `flush()`。
3. 权限判断集中在 `services/access.py`（权限点、数据范围、字段策略）与 `services/authz.py`（授权配置），禁止散落在路由里。
4. 跨层复用只能向下，禁止 `models` 反向导入上层。

---

## 6. 命名规范

| 对象 | 规则 | 示例 |
| --- | --- | --- |
| 模块/包 | `snake_case`，单数领域名 | `school_class.py` |
| 函数/变量 | `snake_case` | `enrolled_count` |
| 类/异常 | `PascalCase` | `EnrollmentService` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE` |
| 私有成员 | 前缀 `_` | `_set_pragmas` |
| 测试 | `test_<行为>_<条件>` | `test_enroll_course_when_full_returns_409` |
| 数据库表 | 复数 `snake_case` | `dorm_assignments` |
| 数据库字段 | `snake_case`，外键 `xxx_id` | `head_teacher_id` |
| API 资源 | 复数短横线/单词 | `/api/v1/school-classes` 不用，统一 `/classes` |

---

## 7. 数据层规范

- SQLAlchemy 2.0 声明式：`Mapped[...]` + `mapped_column(...)`，禁止旧式 `Column`。
- 所有表继承 `TimestampMixin`（`created_at`/`updated_at`，UTC，`DateTime(timezone=True)`）。
- 主键统一 `id: Mapped[int]`；业务唯一键（`student_no`/`teacher_no`/`course_code`）必须加唯一约束。
- 枚举用 `Enum(..., native_enum=False, length=20)` 存字符串，禁止魔法数字。
- 外键必须声明 `ondelete`；删除被引用数据时由 service 返回 `409 REFERENCE_EXISTS`，不得静默级联删除业务数据。
- 结构变更必须新增 Alembic 迁移；禁止修改已发布的迁移文件。基线 `0001` 以元数据建表，后续迁移写显式 DDL。
- SQLite 启用 `foreign_keys=ON`、`journal_mode=WAL`、`busy_timeout=5000`（见 `db/session.py`）。

典型模型写法：

```python
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from campus.db.base import Base, TimestampMixin


class Enrollment(TimestampMixin, Base):
    """选课记录：同一学生对同一课程只允许一条。"""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_enrollments_student_course"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
```

---

## 8. API 契约

- 前缀 `/api/v1`；资源名复数；HTTP 方法表达语义（`GET/POST/PATCH/DELETE`）。
- 列表统一分页：`?page=1&page_size=20`（`1..100`），响应体固定为 `Page[T]`：

```python
{
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20,
}
```

- 错误统一结构（由全局异常处理器产出）：

```json
{"code": "NOT_FOUND", "message": "课程不存在", "details": []}
```

- 错误码与状态码：

| code | HTTP | 场景 |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | 缺少/无效令牌 |
| `TOKEN_EXPIRED` | 401 | 令牌过期 |
| `FORBIDDEN` | 403 | 角色或归属不允许 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `DUPLICATE_KEY` | 409 | 唯一键冲突 |
| `COURSE_FULL` / `ALREADY_ENROLLED` / `SCORE_LOCKED` / `REFERENCE_EXISTS` | 409 | 教务规则冲突 |
| `VALIDATION_ERROR` | 422 | 入参校验失败（`details` 为字段级错误） |

- 鉴权：`Authorization: Bearer <JWT>`；令牌载荷含 `sub`（用户 ID）、`role`、`exp`，有效期默认 60 分钟。
- 鉴权与授权：
  - 角色与权限点存数据库（`roles`/`permissions`/`role_permissions`/`user_roles`/`user_permission_overrides`），
    管理员在“系统设置 → 角色权限”配置；有效权限 = 角色并集 + 用户级 `allow` − 用户级 `deny`。
  - 数据范围由关系推导：`admin`=全校；教师=班主任/任课班级；学生=本人。
  - 内置角色：`admin`、`teacher`、`student`、`student_affairs`、`academic_director`；一个账号可多角色。
  - 列表与详情在 service 层按 `AccessContext.scope` 过滤，字段按 `brief/detail/private` 投影。
- 密码只以 Argon2 哈希存储；响应中永不返回 `password_hash`。

路由示例：

```python
from fastapi import APIRouter, Query

from campus.api.deps import AdminUser, SessionDep
from campus.schemas.common import Page
from campus.schemas.student import StudentRead
from campus.services.people import StudentService

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=Page[StudentRead])
async def list_students(
    session: SessionDep,
    _: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[StudentRead]:
    return await StudentService(session).list_students(page=page, page_size=page_size)
```

---

## 9. 测试规范

- 框架：`pytest` + `pytest-asyncio`（`asyncio_mode = "auto"`）+ `httpx.AsyncClient`。
- 每个 service 至少 1 个单元测试覆盖核心规则；每个 router 至少覆盖：成功、401、403（如适用）、404/409/422 之一。
- 测试数据必须自建自毁：`tmp_path` 临时 SQLite + 依赖覆盖，禁止依赖开发库或执行顺序。
- 断言具体错误码（`response.json()["code"]`），不要只断言状态码。
- 覆盖率门槛 80%，新增模块不得拉低总体覆盖率。

测试示例：

```python
from httpx import AsyncClient


async def test_enroll_course_when_full_returns_409(client: AsyncClient, auth_headers) -> None:
    headers = await auth_headers("admin", "admin123")
    response = await client.post(
        "/api/v1/enrollments",
        json={"student_id": 1, "course_id": 1},
        headers=headers,
    )
    assert response.status_code in {201, 409}
```

---

## 10. 安全与配置

- `.env` 只存本地配置，已在 `.gitignore` 中；`.env.example` 只放占位值。
- `JWT_SECRET` 在生产环境必须显式设置且长度 ≥ 32；`app_env != "dev"` 时缺失即启动失败。
- 开启 CORS 白名单，禁止 `allow_origins=["*"]` 与 `allow_credentials=True` 组合。
- 日志禁止输出密码、完整令牌、身份证/手机号等敏感字段。
- 所有写接口必须校验归属（学生只能操作自己的选课/缴费）。

---

## 11. 变更流程

1. 读本文件 → 2. 改代码/结构 → 3. 同步第 2 节清单与文档 → 4. 补测试 → 5. 跑第 3 节门禁 → 6. 提交。
2. 提交信息遵循 Conventional Commits：`feat(enrollment): 支持退课`、`fix(score): 修正总评计算`。
3. 破坏性接口变更需在 `docs/API.md` 标注并升级版本号。
4. 修改数据库结构必须同时提交迁移文件与 `docs/ARCHITECTURE.md` 的数据模型更新。

---

## 12. 完成定义（DoD）

- [ ] `python -m compileall -q src` 通过
- [ ] `ruff check .` 与 `ruff format --check .` 通过
- [ ] `mypy src` 无错误
- [ ] `pytest` 全绿且覆盖率 ≥ 80%
- [ ] `AGENTS.md` 目录清单与仓库一致，代码块语法合法
- [ ] 新接口已写入 `docs/API.md`
