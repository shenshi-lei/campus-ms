# 架构说明

## 1. 目标与边界

`campus-ms` 是一个教学与演示导向的校园管理系统：单体 FastAPI 服务 + SQLite + 原生 JS 前端。
目标是"结构清晰、规则集中、可测试"，而不是生产级高并发集群。

非目标：分布式事务、消息队列、多租户、前后端构建链、对象存储。

## 2. 运行时形态

```text
浏览器（web/ 静态页）
        │  fetch + Bearer JWT
        ▼
FastAPI（/api/v1）
        │  依赖注入：AsyncSession / 当前用户
        ▼
Service（业务规则、权限、事务）
        ▼
Repository（SQLAlchemy 查询）
        ▼
SQLite（aiosqlite，WAL）
```

静态页面由同一个 FastAPI 进程通过 `StaticFiles` 托管（挂载在 `/`），
因此开发期只需一个端口，不需要额外的静态服务器；生产环境可把 `web/` 交给 Nginx。

## 3. 分层职责

| 层 | 位置 | 职责 | 不负责 |
| --- | --- | --- | --- |
| API | `api/v1/` | 解析查询参数/请求体、调用 service、返回 schema | 业务规则、SQL |
| 依赖 | `api/deps.py` | Bearer 解析、当前用户、角色守卫、会话注入 | 业务查询 |
| 契约 | `schemas/` | Pydantic v2 输入校验与输出序列化 | 持久化 |
| 服务 | `services/` | 业务规则、权限判定、事务提交、错误码 | HTTP 细节 |
| 仓储 | `repositories/` | 查询构造、分页计数、联表投影 | 业务判断、commit |
| 模型 | `models/` | 表结构、约束、枚举 | 查询逻辑 |
| 基础设施 | `core/` `db/` | 配置、JWT、异常、日志、引擎、建表 | 业务 |

依赖方向严格单向：`api → services → repositories → models`；`schemas` 只被外层引用。

## 4. 数据模型

共 29 张表（21 张业务表 + 5 张权限表 + 3 张组织表），统一使用 `id` 自增主键与 `created_at/updated_at`（UTC）。

| 表 | 关键字段 | 约束 |
| --- | --- | --- |
| `users` | `username`, `password_hash`, `role`, `is_active` | `username` 唯一 |
| `students` | `student_no`, `name`, `gender`, `status`, `class_id`, `seat_no`, `class_role`, `residence_type`, `user_id` | `student_no` 唯一、`user_id` 唯一 |
| `teachers` | `teacher_no`, `name`, `title`, `subject_id`, `position`, `hire_date`, `employment_status`, `staff_type`, `user_id` | `teacher_no` 唯一、`user_id` 唯一 |
| `school_classes` | `name`, `grade`, `grade_year`, `major`, `department_id`, `classroom`, `capacity`, `status`, `head_teacher_id` | `name` 唯一 |
| `courses` | `code`, `name`, `credits`, `hours`, `semester`, `semester_id`, `subject_id`, `course_type`, `assessment_type`, `grade_scheme`, `teacher_id`, `capacity` | `code` 唯一 |
| `enrollments` | `student_id`, `course_id`, `status` | (`student_id`,`course_id`) 唯一 |
| `scores` | `enrollment_id`, `usual_score`, `midterm_score`, `exam_score`, `final_score`, `published` | `enrollment_id` 唯一 |
| `attendance` | `student_id`, `course_id`, `date`, `period_no`, `schedule_id`, `status` | (`student_id`,`course_id`,`date`,`period_no`) 唯一 |
| `schedules` | `course_id`, `semester_id`, `class_id`, `weekday`, `start_period`, `end_period`, `classroom`, `status` | (`course_id`,`weekday`,`start_period`) 唯一 |
| `dorms` | `building`, `room_no`, `capacity`, `gender` | (`building`,`room_no`) 唯一 |
| `dorm_assignments` | `student_id`, `dorm_id`, `bed_no` | `student_id` 唯一、(dorm,bed) 唯一 |
| `fees` | `student_id`, `item`, `amount`, `due_date`, `status` | 无业务唯一键 |
| `roles` | `code`, `name`, `description`, `is_system`, `is_active` | `code` 唯一 |
| `permissions` | `code`, `resource`, `action`, `name`, `is_active` | `code` 唯一 |
| `role_permissions` | `role_id`, `permission_id` | (`role_id`,`permission_id`) 唯一 |
| `user_roles` | `user_id`, `role_id` | (`user_id`,`role_id`) 唯一 |
| `user_permission_overrides` | `user_id`, `permission_id`, `effect` | (`user_id`,`permission_id`) 唯一 |
| `departments` | `code`, `name`, `kind`, `parent_id` | `code`/`name` 唯一 |
| `subjects` | `code`, `name`, `department_id` | `code`/`name` 唯一 |
| `semesters` | `name`, `start_date`, `end_date`, `status`, `is_current`, `weeks` | `name` 唯一；`is_current` 由 service 保证唯一 |
| `leave_requests` | `applicant_type`, `student_id`, `teacher_id`, `leave_type`, `start_at`, `end_at`, `days`, `status`, `current_step`, `required_steps` | `student_id`/`teacher_id` 二选一（CHECK） |
| `leave_approvals` | `leave_request_id`, `step_no`, `approver_role_code`, `approver_id`, `status`, `remark` | (`leave_request_id`,`step_no`) 唯一 |
| `leave_policies` | `applicant_type`, `step_no`, `approver_role_code`, `min_days` | (`applicant_type`,`step_no`) 唯一 |
| `notices` | `title`, `content`, `audience`, `class_id`, `publisher_id`, `is_pinned`, `expires_at` | 无业务唯一键 |
| `student_status_history` | `student_id`, `from_status`, `to_status`, `effective_date`, `reason`, `operator_id` | 无业务唯一键 |
| `course_teachers` | `course_id`, `teacher_id`, `role` | (`course_id`,`teacher_id`) 唯一 |
| `course_classes` | `course_id`, `class_id` | (`course_id`,`class_id`) 唯一 |
| `schedule_changes` | `schedule_id`, `change_date`, `kind`, `new_*`, `status`, `requested_by`, `approved_by` | 无业务唯一键 |
| `audit_logs` | `user_id`, `username`, `role`, `method`, `path`, `status_code`, `ip`, `detail` | 无业务唯一键 |

关系：

- `students.class_id → school_classes.id`（SET NULL）
- `students.user_id` / `teachers.user_id → users.id`（SET NULL）
- `school_classes.head_teacher_id → teachers.id`（SET NULL）
- `courses.teacher_id → teachers.id`（SET NULL）
- `enrollments.student_id → students.id`、`enrollments.course_id → courses.id`（CASCADE）
- `scores.enrollment_id → enrollments.id`（CASCADE）
- `attendance.student_id/course_id`（CASCADE）
- `schedules.course_id`（CASCADE）
- `dorm_assignments.student_id/dorm_id`（CASCADE）
- `fees.student_id`（CASCADE）
- `role_permissions.role_id → roles.id`、`role_permissions.permission_id → permissions.id`（CASCADE）
- `user_roles.user_id → users.id`、`user_roles.role_id → roles.id`（CASCADE）
- `user_permission_overrides.user_id → users.id`、`.permission_id → permissions.id`（CASCADE）
- `school_classes.department_id → departments.id`、`teachers.subject_id → subjects.id`（SET NULL）
- `subjects.department_id → departments.id`、`departments.parent_id → departments.id`（SET NULL）
- `leave_requests.student_id → students.id`、`.teacher_id → teachers.id`（CASCADE）
- `leave_approvals.leave_request_id → leave_requests.id`（CASCADE）
- `notices.class_id → school_classes.id`、`notices.publisher_id → users.id`（SET NULL）
- `student_status_history.student_id → students.id`（CASCADE）

### 4.8 v3 新增实体（迁移 0007–0009）

| 表 | 作用 | 关键字段 |
| --- | --- | --- |
| `leave_flows` | 可配置请假流程 | `code`、`applicant_type`、`leave_type`、`min_days`、`max_days`、`priority`、`is_active` |
| `leave_flow_steps` | 流程审批节点 | `flow_id`、`step_no`、`name`、`approver_type`、`role_code`、`user_id`、`group_id` |
| `leave_events` | 请假流转时间线 | `leave_request_id`、`action`、`actor_id`、`actor_name`、`detail` |
| `calendar_events` | 日程事件 | `title`、`start_at`、`end_at`、`kind`、`visibility`、`owner_id`、`department_id`、`class_id` |
| `calendar_event_attendees` | 日程参与人 | `event_id`、`user_id`、`response`、`is_required` |
| `user_groups` | 群组 | `code`、`name`、`kind`、`is_active` |
| `user_group_members` | 群组成员 | `group_id`、`member_type`、`member_id`、`user_id`、`display_name` |
| `notifications` | 站内消息 | `user_id`、`kind`、`title`、`body`、`link`、`is_read` |
| `system_settings` | 系统参数 | `key`、`value`（JSON 字符串）、`description` |

同时扩展：`leave_requests.flow_id/flow_name`、`leave_approvals.step_name/approver_type/approver_user_id/approver_group_id/assigned_at`、
`attendance.leave_request_id`、`teachers.department_id`、`notices.group_id`。

### 4.9 关系补充

- `leave_requests.flow_id → leave_flows.id`（SET NULL）；旧数据保留 `leave_policies` 作为兼容回退。
- `leave_flow_steps.flow_id → leave_flows.id`（CASCADE）；`user_id → users.id`、`group_id → user_groups.id`（SET NULL）。
- `calendar_events.owner_id/created_by → users.id`；`department_id → departments.id`；`class_id → school_classes.id`。
- `calendar_event_attendees.event_id → calendar_events.id`（CASCADE）；`user_id → users.id`（CASCADE）。
- `user_group_members.group_id → user_groups.id`（CASCADE）；`user_id → users.id`（SET NULL）。
- `notifications.user_id → users.id`（CASCADE）。

## 5. 关键业务流程

### 5.1 登录

1. `POST /auth/login` 按用户名取 `users`，`pwdlib`(Argon2) 校验密码。
2. 通过后签发 HS256 JWT：`sub=user.id`、`role`、`iat`、`exp`。
3. 前端把 token 存 `localStorage`，后续请求带 `Authorization: Bearer`。
4. 服务端依赖解析 token → 加载 `User` → 校验 `is_active`；失败抛 401/403。

### 5.2 选课

1. 学生角色：由 `user_id` 反查 `students`，忽略请求体中的 `student_id`；管理员必须显式指定学生。
2. 校验学生存在且 `is_active`、课程存在。
3. 已存在选课记录 → `409 ALREADY_ENROLLED`。
4. 已选人数 ≥ `course.capacity` → `409 COURSE_FULL`。
5. 插入 `enrollments`，提交事务。

退课：只允许学生本人或管理员；存在成绩记录 → `409 SCORE_LOCKED`；否则删除记录（允许重新选课）。

### 5.3 成绩

- 批量接口按 (`student_id`,`course_id`) 定位选课记录，未选课 → `409`。
- 教师只能操作 `course.teacher_id == 自己` 的课程；管理员不限。
- 总评 = `round(usual * 0.4 + exam * 0.6, 2)`；任一分项缺失则不计算。
- 每次写入更新 `recorded_by` 与 `recorded_at`。

### 5.4 考勤

- 以 (`student_id`,`course_id`,`date`) 幂等 upsert。
- 权限同成绩：教师仅本人课程。

### 5.5 宿舍

分配床位依次校验：学生存在且在册 → 房间存在 → 学生无床位 → 未超容量 → 性别匹配 → 床位未被占用。
删除房间前必须没有分配记录，否则 `409 REFERENCE_EXISTS`。

### 5.6 缴费

- 管理员创建费用项；学生（本人）或管理员支付。
- 已支付再次支付 → `409`；支付时写入 `paid_at` 并置 `paid`。

### 5.7 请假审批

1. 学生/教师提交申请，按 `leave_policies` 与请假天数计算 `required_steps`（默认 3 天以上两级）。
2. 学生第 1 级为班主任（按 `school_classes.head_teacher_id` 解析）、第 2 级为学工处；
   教师第 1 级为教务主任、第 2 级为管理员。
3. 每级通过后推进 `current_step`；任一级驳回即终止；管理员可代批任意级。
4. 学生请假最终通过后，按选课课程与日期把考勤写为 `leave`；超过 31 天不自动写考勤。
5. 通知按 `audience` + 班级过滤；教师只能发布本人班主任班级的通知。

### 5.8 课程与调课

- 课程可挂多名教师（`course_teachers`，主讲/辅导）与多个行政班（`course_classes`）；
  教师数据范围同时包含“主讲课程”和“辅导课程”。
- 总评按课程 `grade_scheme` 计算：默认平时 40% + 期末 60%；支持平时/期中/期末任意权重，归一化后计算。
- 成绩默认未发布，学生只能看到已发布成绩；教师发布本人课程，撤回仅管理员。
- 考勤按 (`学生`,`课程`,`日期`,`节次`) 唯一登记；请假通过后按选课写 `leave`。
- 调课/停课/代课进入 `schedule_changes`，教师发起、管理员审批；停课通过后排课状态置为 `cancelled`。

### 5.9 审计、账号与导入导出

- 写请求（POST/PUT/PATCH/DELETE）由应用中间件统一写 `audit_logs`，记录用户、角色、方法、路径、状态码与 IP；
  登录接口不记录。导出等 GET 敏感操作由 service 手工留痕。
- 审计写入失败只记录日志，不影响业务响应。
- 管理员可启停用账号、重置密码；禁止停用当前登录账号。
- CSV 导出按数据范围过滤：管理员全量、教师本班/本人课程、学生本人（成绩仅已发布）。
- 学生 CSV 导入以 `student_no` 为业务键 upsert，逐行收集错误，管理员专用。

### 5.10 报表

- 教师工作量：课程数、周课时（按排课节次）、总学时、学生数与班级数；
  教师只看本人，管理员看全量。
- 学科分析：课程数、学生数、平均总分、及格率；教师限本人课程。
- 班级对比：人数、平均总分、出勤率、缴费收缴率；教师限本人班主任/任课班级。
- 统计在仓储层用聚合查询一次取数，service 组装，避免逐实体 N+1。

## 6. 事务与并发

- 每个请求一个 `AsyncSession`，service 在写操作末尾 `commit()`。
- Repository 只 `flush()`，不提交，保证一个业务动作一个事务。
- SQLite 连接启用 `foreign_keys=ON`、`WAL`、`busy_timeout=5000`；
  写并发仍受 SQLite 单写者限制，适用于中小规模；高并发应迁移到 PostgreSQL（模型与仓储无需改动）。
- 唯一约束是最后一道防线；全局 `IntegrityError` 处理器兜底转换为 `409 DUPLICATE_KEY`。

## 7. 权限模型

采用“权限点 + 数据范围 + 字段策略”三层：

- **权限点**：`资源:动作`（如 `score:write`），存 `permissions`；角色授权存 `role_permissions`。
- **用户**：可多角色（`user_roles`），并可对单个权限点做 `allow/deny` 覆盖（`user_permission_overrides`）。
- **有效权限** = 角色并集 + allow − deny；每次请求重新计算，后台改权限即时生效。
- **数据范围**（`AccessContext.scope`）：
  - `admin` → `ALL`（全校）；
  - 教师 → 班主任班级 ∪ 任课课程覆盖的班级（`CLASSES`），课程写权限仅本人课程；
  - 学生 → `SELF`（本人）。
- **字段策略**：`brief/detail/private` 三档；学生看教师或同学时联系方式置空，身份证明细仅本人/班主任/管理员可见。
- 列表过滤在 service 层完成，仓储接收 scope 条件；路由只做权限点守卫。

内置角色：`admin`、`teacher`、`student`、`student_affairs`（学工处）、`academic_director`（教务主任）。

### 7.1 权限解析流程

1. `get_access` → `build_access_context`：读 `user_roles` / `role_permissions` / `permissions` + 用户级覆盖。
2. 首次启动由 `AuthzService.sync_defaults()` 写入权限点、内置角色与默认授权；
   权限表为空时回退内置默认值（仅用于测试或首次启动）。
3. 计算 `student_id` / `teacher_id`、班主任班级、任课课程与班级，得到 `DataScope`。
4. 路由用 `require(Permission.X)` 校验权限点；service 用 `ensure_student` / `ensure_course_write` 等校验数据范围。

## 8. 配置与部署

- 配置来自环境变量/`.env`（`pydantic-settings`），见 `.env.example`。
- `APP_ENV != dev/test` 时强制校验 `JWT_SECRET` 长度与非默认值。
- 数据库迁移：`alembic upgrade head`；基线 `0001` 由元数据建表，后续版本写显式 DDL。
- 静态资源：`src/campus/web`，FastAPI 直接挂载；也可由反向代理托管。
- 日志：标准输出，级别由 `LOG_LEVEL` 控制。

## 9. 扩展指引

- 新增业务实体：`models → schemas → repositories → services → api/v1 → 前端视图 → tests`，并同步 `AGENTS.md` 目录清单。
- 新增字段：模型 + Pydantic 契约 + 迁移 + `docs/ARCHITECTURE.md` 数据模型表 + 测试。
- 新增规则：写入 service，不要在路由或仓储里判断；错误使用 `core/exceptions.py` 中已有或新增的 `AppError` 子类。
