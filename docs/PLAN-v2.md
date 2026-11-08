# 校园管理系统 v2 方案：权限体系与领域模型细化

> 状态：**已确认（2026-11-07）**——全量 P0–P5；权限点入库并支持后台配置；敏感字段只存脱敏值；请假两级审批。
> 影响面：后端 `api/services/repositories/models/schemas`、前端 `web/assets`、Alembic 迁移、种子数据、测试、文档
> 阅读顺序：第 1 节看现状问题 → 第 3/4 节看设计 → 第 6 节看怎么落地 → 第 10 节做选择

---

## 0. 结论先行

当前系统不是"功能少"，而是两根地基太薄：

1. **权限是"角色字符串 + 归属判断"**：后端只有 `AdminUser / StaffUser / CurrentStudent` 三种守卫，前端到处是
   `state.user.role === "admin"`。没有权限点、没有数据范围、没有字段级可见性，所以"学生到底能看什么、老师能看到哪一层"
   既表达不出来，也测不出来，只能靠 if/else 堆。
2. **领域模型是"能跑通流程的最小集合"**：教师只有职称/院系，学生只有一个 `class_id`，班级只有名称/年级/专业，
   课程只有一个教师字符串学期，请假只是考勤里的一个状态。真实校园里"学科、职务、入职、事假、班级座位、学籍异动"
   这些才是业务本身，现在全被抹平了。

v2 的主线只有一句话：**先把"谁能看什么"变成可配置、可测试的权限内核（P0），再把"人、班、课、假"补成真实模型（P1–P3），
最后补管理能力与报表（P4–P5）。**

---

## 1. 现状诊断（基于当前代码）

### 1.1 权限现状

| 位置 | 现状 | 问题 |
| --- | --- | --- |
| `services/permissions.py` | 3 个同步函数 + 2 个异步归属函数；`ensure_can_write_course` 只判断"是否本人课程" | 没有权限点、没有数据范围枚举、没有字段策略 |
| `api/deps.py` | `require_admin` / `require_staff` / `get_current_student` | 角色写死；教师与管理员共用 `StaffUser`，无法表达"班主任 vs 任课教师" |
| 各路由 | 用 `StaffUser` 或 `AdminUser` 做粗粒度守卫 | 教师能 `GET /students` 拉全校学生；`GET /students/{id}` 也不限范围 |
| 列表查询 | `StudentRepository.filtered` 只按 keyword/class_id/is_active 过滤 | 没有"按访问者身份"注入过滤条件，教师能看到任意班级学生 |
| 字段输出 | `StudentRead` / `TeacherRead` 单一模型 | 手机号、邮箱、未来要加的身份证/住址会直接发给所有能读的人 |
| 前端 | `NAV_GROUPS[].roles` + 十余处 `role === "admin"` | 菜单、按钮、列全部硬编码；新增角色/岗位必须改前端 |
| 审计 | 无 | 谁改了成绩、谁导出了学生名单，无法追溯 |

具体例子（当前真实行为）：

- 教师登录后 `GET /api/v1/students?page_size=100` 能拿到**全校**学生的手机号、邮箱、班级。
- 学生登录后能 `GET /api/v1/teachers` 拿到**全部教师**的手机号、邮箱（`teachers.py` 只要求 `CurrentUser`）。
- `GET /api/v1/schedules` 没有角色过滤，学生能看**所有班级**的课表。
- 学生 `GET /students/{id}/transcript` 已做本人校验（好），但 `GET /students/{id}` 教师无范围限制（不好）。

### 1.2 领域模型现状

| 实体 | 当前字段 | 缺失（业务上必须有） |
| --- | --- | --- |
| `teachers` | 工号、姓名、职称、院系、手机、邮箱、user_id、is_active | 学科、职务、入职日期、在职状态、编制类型、学历、办公室、周课时上限 |
| `students` | 学号、姓名、性别、生日、手机、邮箱、class_id、user_id、is_active | 入学日期、学籍状态（在读/休学/退学/毕业）、座位、身份证、家庭住址、监护人、班干部、住校/走读 |
| `school_classes` | 名称、年级(字符串)、专业(字符串)、班主任 | 院系、固定教室、容量、年级实体、班级状态 |
| `courses` | 代码、名称、学分、学时、学期(字符串)、教师、容量、简介 | 学科、课程类型（必修/选修/实践）、考核方式、学期实体、开课院系、教材、多教师 |
| `schedules` | 课程、星期、起止节、教室、周次(字符串) | 学期实体、行政班、调课/停课记录 |
| `attendance` | 学生、课程、日期、状态、备注 | 节次、关联请假单、补签 |
| `scores` | 平时、考试、总评、录入人 | 期中、成绩构成、发布状态、补考/重修 |
| `fees` | 学生、项目、金额、截止、状态 | 费用类型、学期、部分缴费、减免、支付方式 |
| `dorm_assignments` | 学生、房间、床位 | 入住/退宿日期、状态 |
| 请假 | 只有 `AttendanceStatus.LEAVE` | 申请单、类型、起止时间、事由、审批人、审批意见 |
| 通知/审计/学籍异动 | 无 | 全部缺失 |

### 1.3 前端现状

- `app.js` 1811 行，单文件；`NAV_GROUPS`、`VIEWS`、`PAGE_META` 与权限判断混在一起。
- 表格列没有"可见性"概念；详情只有列表行内编辑，没有"学生 360 / 教师档案 / 班级详情"。
- 无请假、通知、审计、账号管理、学期/学科/院系设置页面。

---

## 2. 设计原则

1. **默认拒绝**：没有显式授予的权限点，一律 403；没有命中数据范围的数据，一律不可见。
2. **最小必要**：学生只看"本人 + 本班公开信息"；教师只看"本班 + 本人课程"；管理员才看全量。
3. **权限下沉、集中判定**：权限只在 `services/` 判定，路由不写 if，仓储不判权限，前端只做"展示层过滤"，**后端永远是最终防线**。
4. **模型为业务服务，不为演示服务**：学科、职务、学期、请假、座位、学籍异动是业务实体，不用字符串糊。
5. **渐进可交付**：每个阶段独立可运行、可测试、可上线；不做"一次性大爆炸"。
6. **兼容旧数据**：所有新列有默认值/可空；旧接口路径不破坏，只增字段不删字段。

---

## 3. 权限体系设计

### 3.1 三层模型

```text
角色（Role）            →  权限点（Permission）        →  数据范围（DataScope）
admin/teacher/student      student:read / score:write      ALL / DEPARTMENT / CLASS / COURSE / SELF
                           ↓
                     字段策略（FieldPolicy）
                     brief / contact / sensitive
```

- **角色与权限点入库**：`roles`、`permissions`、`role_permissions`、`user_roles`、`user_permission_overrides` 五张表，
  管理员在"系统设置 → 角色权限"里勾选；代码里的 `Permission` 枚举只作为权限码的规范来源和首次种子数据。
- **一个用户可挂多个角色**（如"教师 + 教研组长"）；有效权限 = 所有角色权限并集 + 用户级 `allow` − 用户级 `deny`。
  默认拒绝：DB 没有授权就是没有权限。
- **数据范围仍由代码推导**（依赖班主任/任课关系），不放进权限表：角色决定"能不能做"，关系决定"对哪些数据做"。
- **字段策略**由代码按"访问者与目标的关系"选择，配置层只暴露"敏感字段可读角色"这一档。
- 权限每次请求实时计算（SQLite 规模下开销可忽略），角色调整立即生效，不依赖重新登录。

### 3.2 权限点清单（建议）

| 资源 | 权限点 | 说明 |
| --- | --- | --- |
| 仪表盘 | `dashboard:read` | 按角色返回不同聚合 |
| 学生 | `student:read` / `student:self:read` / `student:read_detail` / `student:manage` / `student:sensitive:read` | 列表 / 本人档案 / 详情 / 增改停用 / 身份证住址监护人 |
| 教师 | `teacher:read` / `teacher:read_detail` / `teacher:manage` | 简版目录 / 完整档案 / 增改停用 |
| 班级 | `class:read` / `class:manage` / `class:seat:read` / `class:seat:manage` | 班级 / 增改 / 座位查看 / 座位调整 |
| 组织 | `subject:read` / `subject:manage`、`semester:read` / `semester:manage`、`department:read` / `department:manage` | 学科、学期、院系 |
| 课程 | `course:read` / `course:manage` | 目录 / 开课维护（含多教师、面向班级） |
| 选课 | `enrollment:read` / `enrollment:manage` / `enrollment:self` | 名单 / 代选退课 / 本人选退 |
| 成绩 | `score:read` / `score:write` / `score:publish` / `score:unlock` | 查看 / 录入 / 发布 / 解锁 |
| 考勤 | `attendance:read` / `attendance:write` | 查看 / 登记 |
| 课表 | `schedule:read` / `schedule:manage` / `schedule:change` | 查看 / 排课 / 调停课 |
| 宿舍 | `dorm:read` / `dorm:manage` / `dorm:self` | 房间床位 / 分配退宿 / 本人床位 |
| 缴费 | `fee:read` / `fee:manage` / `fee:pay` | 查看 / 建单减免 / 本人支付 |
| 请假 | `leave:apply` / `leave:read` / `leave:approve` | 申请 / 查看 / 审批 |
| 通知 | `notice:read` / `notice:manage` | 阅读 / 发布 |
| 审计 | `audit:read` | 仅管理员 |
| 账号 | `account:manage` | 重置密码、启停用、绑定档案 |
| 系统 | `role:manage` / `permission:manage` | 角色与权限配置（仅管理员） |

### 3.3 数据范围（DataScope）

| 枚举 | 含义 | 典型持有者 |
| --- | --- | --- |
| `ALL` | 全校 | admin |
| `DEPARTMENT` | 本院系 | 院系管理员/教务主任（预留） |
| `HEAD_CLASS` | 本人担任班主任的班级 | 班主任 |
| `TEACHING_CLASS` | 本人任课课程覆盖的班级 | 任课教师 |
| `SELF` | 仅本人 | 学生 |

`AccessContext`（每个请求构建一次）保存：

- `role`、`user_id`、`student_id`、`teacher_id`
- `head_class_ids`（班主任班级）
- `teaching_class_ids`（任课班级，由 `course_classes` + `schedules` 推导）
- `teaching_course_ids`（任课课程）
- `permissions`（DB 中所有角色权限并集 + 用户级 allow − 用户级 deny）
- `field_level`（`admin` / `staff` / `self`）

列表查询统一由仓储接收 `scope` 条件，例如：

```python
def filtered(self, *, scope: StudentScope, keyword: str | None, class_id: int | None) -> Select:
    statement = select(Student)
    if scope.kind is ScopeKind.CLASSES:
        statement = statement.where(Student.class_id.in_(scope.class_ids))
    elif scope.kind is ScopeKind.SELF:
        statement = statement.where(Student.id == scope.student_id)
    ...
```

### 3.4 字段分级与投影

| 级别 | 字段 | 可见范围 |
| --- | --- | --- |
| `public` | 姓名、学号、性别、班级、座位、班干部、住宿类型 | 本人、同班同学、班主任、任课教师、管理员 |
| `staff` | 学籍状态、入学日期、手机、邮箱 | 本人、班主任、任课教师、管理员 |
| `sensitive` | 身份证号（脱敏）、家庭住址、监护人姓名/电话、缴费金额与流水 | 本人、班主任（身份证仅脱敏）、管理员 |
| `management` | 账号状态、审计日志、成绩录入明细（未发布） | 管理员；成绩明细另见下 |

响应模型拆三档，服务层按 `AccessContext` 选择：

- `StudentBrief`：列表/同班可见（public 字段）
- `StudentDetail`：教师/本人可见（public + staff）
- `StudentPrivate`：本人/管理员可见（+ sensitive，身份证脱敏）

同理：`TeacherBrief`（学生可见）、`TeacherDetail`（同事/本人）、`TeacherPrivate`（本人/管理员）。
**绝不用"返回全字段再置空"的方式做脱敏**，避免序列化层遗漏。

### 3.5 角色权限矩阵（功能级）

| 能力 | admin | 班主任 | 任课教师 | 学生 |
| --- | --- | --- | --- | --- |
| 仪表盘 | 全校 | 本班 + 本人 | 本人课程 | 本人 |
| 学生列表 | 全部 | 本班 | 任课班 | 仅本班同学简版 |
| 学生详情 | 全部字段 | 本班（敏感字段脱敏） | 任课班（教学字段） | 本人全部 |
| 学生增改/停用 | ✓ | ✗ | ✗ | ✗（仅联系方式可改，可选） |
| 教师列表 | 全部字段 | 简版 | 简版 | 简版（无联系方式） |
| 教师详情 | 全部 | 本人完整 / 他人简版 | 本人完整 / 他人简版 | 简版 |
| 班级 | 全部读写 | 本班详情 | 任课班概况 | 本班概况 |
| 座位表 | 读写 | 本班读写 | 本班只读 | 本班只读（高亮本人） |
| 课程 | 全部读写 | 本人课程读写 | 本人课程读写 | 目录只读 |
| 选课 | 代选/退课 | 名单只读 | 名单只读 | 本人选/退 |
| 成绩 | 全部读写 / 发布 / 解锁 | 本班只读 | 本人课程读写 / 发布 | 本人已发布只读 |
| 考勤 | 全部读写 | 本班只读 | 本人课程读写 | 本人只读 |
| 课表 | 全部读写 | 本班 + 本人读写 | 本人课程读写 | 本班 + 本人只读 |
| 调课/停课 | 审批 | 本班申请 | 本人课程申请 | ✗ |
| 宿舍 | 全部读写 | 本班只读 | ✗ | 本人只读 |
| 缴费 | 全部读写 | 本班欠费汇总 | ✗ | 本人查看/支付 |
| 请假 | 全部 | 本班审批 + 本人申请 | 本人申请 | 本人申请/撤销 |
| 通知 | 全部 | 本班发布 | 读 | 读 |
| 审计 / 账号 | ✓ | ✗ | ✗ | ✗ |

### 3.6 学生"应该给 / 不应该给"清单（明确验收口径）

**应该给到学生：**

1. 本人档案：姓名、学号、性别、班级、座位、入学日期、学籍状态、联系方式（可改需审核）。
2. 本人课表：按学期/周次，含调课与停课标记。
3. 本人成绩：**仅已发布**，含平时/期中/期末/总评与课程学分；未发布不可见。
4. 本人考勤：出勤/迟到/缺勤/请假，含关联请假单。
5. 本人选课与退课（受容量、已录成绩锁定）。
6. 本人缴费：金额、状态、截止日期，可发起支付（演示）；不可见他人金额。
7. 本人宿舍：楼栋、房间、床位。
8. 本班同学名单：仅姓名 + 座位（用于找同学/座位表），**不含联系方式**。
9. 本班座位表：本人座位高亮。
10. 任课教师简版信息：姓名、学科、职称、办公室，**不含手机邮箱**。
11. 通知公告：按 `all / student / class` 过滤。
12. 请假申请、撤销、查看审批进度。

**不应该给到学生：**

1. 其他学生的手机、邮箱、身份证、住址、监护人、缴费、成绩、考勤、宿舍明细。
2. 其他班级的成绩/考勤/课表/统计。
3. 教师手机号、邮箱、身份证等个人联系方式。
4. 成绩录入界面、未发布成绩、成绩构成录入权限。
5. 全校统计、班级横向对比原始数据（可给个人视角的排名区间，可选）。
6. 审计日志、账号管理、角色/权限配置。
7. 宿舍分配、缴费减免、退费操作。
8. 学生增删改与学籍异动操作。

### 3.7 教师"应该给 / 不应该给"清单

**应该给到教师：**

1. 本人完整档案：学科、职称、职务、入职日期、在职状态、办公室、联系方式；可维护部分字段（如办公室、联系方式）。
2. 本班学生完整档案（身份证脱敏）、座位表（读写）、班级花名册。
3. 本人任课课程：名单、成绩录入/发布、考勤登记、排课申请、调课申请。
4. 本人课表与教学任务、工作量统计。
5. 本人请假申请与审批记录；班主任审批本班学生请假。
6. 本班欠费汇总（人数/金额），**不含支付流水**。
7. 通知：阅读；班主任可发本班通知。

**不应该给到教师：**

1. 其他班级学生的隐私字段、成绩、考勤、缴费。
2. 其他教师课程的成绩/考勤写权限。
3. 全校人事档案（仅同事简版目录）。
4. 缴费减免/退费、宿舍分配、账号管理、审计日志、权限配置。
5. 学生密码重置（归管理员）。
6. 跨院系/跨班级的统计导出。

### 3.8 后端实现落点

```text
services/access.py（由 permissions.py 演进）
├── Permission(StrEnum)                    权限码规范 + 首次种子来源
├── DEFAULT_ROLE_PERMISSIONS               内置三角色的默认授权（仅供种子/重置）
├── DataScope / ScopeKind                  数据范围值对象
├── AccessContext                          请求级访问上下文（dataclass）
├── build_access_context(session, user)    读 user_roles → role_permissions → permissions + overrides，
│                                          再查 teacher/student/班主任班级/任课课程
├── require(permission)                    依赖工厂 → 403
├── scopes.py                              各资源的 scope 构造器
└── fields.py                              字段策略（brief/detail/private 选择）

repositories/authz.py                       roles / permissions / grants 查询
services/authz.py                           角色权限配置（role:manage / permission:manage）
```

`api/deps.py`：

- `Access = Annotated[AccessContext, Depends(get_access)]`
- `require(Permission.SCORE_WRITE)` 作为路由依赖，替代 `AdminUser/StaffUser`
- 保留 `AdminUser/StaffUser` 作为兼容别名，内部用权限点实现

路由示例（改造后）：

```python
@router.get("", response_model=Page[StudentBrief])
async def list_students(
    session: SessionDep,
    access: Access,
    _: None = Depends(require(Permission.STUDENT_READ)),
    keyword: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[StudentBrief]:
    return await StudentService(session).list_students(
        access=access, keyword=keyword, page=page, page_size=page_size
    )
```

### 3.9 前端权限驱动

`GET /auth/me` 扩展为：

```json
{
  "id": 3,
  "username": "t001",
  "role": "teacher",
  "display_name": "教师一",
  "permissions": ["student:read", "score:write", "..."],
  "nav": [{"group": "教务", "items": [{"id": "students", "label": "学生"}]}],
  "scope": {"teacher_id": 1, "class_ids": [1, 2], "course_ids": [1, 3], "student_id": null}
}
```

前端：

- `can("score:write")` / `canAny([...])` 替代 `role === "admin"`。
- 菜单由 `nav` 渲染（后端算好，前端不再维护角色表）。
- 表格列加 `perm` 元数据，无权限的列不渲染（如学生看教师列表时无"手机号"列）。
- 进入无权限视图时回退仪表盘并提示。
- 按钮（新增/编辑/删除/审批/发布）全部按权限点显隐。

### 3.10 审计

`audit_logs` 记录：`user_id、username 快照、role、action、resource、resource_id、method、path、status_code、ip、detail、created_at`。

- 写入时机：所有 `POST/PATCH/DELETE`（成功与 403 都记），`GET` 仅记录导出/敏感查询。
- 敏感字段（密码、身份证、token）不入库。
- 管理员页面可按人/资源/时间筛选。

### 3.11 数据库权限模型（新增 5 张表）

| 表 | 字段 | 约束 / 说明 |
| --- | --- | --- |
| `roles` | `code`、`name`、`description`、`is_system`、`is_active` | `code` 唯一；内置 `admin/teacher/student` 不可删 |
| `permissions` | `code`、`resource`、`action`、`name`、`description`、`is_active` | `code` 唯一；由 `Permission` 枚举种子同步 |
| `role_permissions` | `role_id`、`permission_id` | (`role_id`,`permission_id`) 唯一 |
| `user_roles` | `user_id`、`role_id` | (`user_id`,`role_id`) 唯一；一个用户可多角色 |
| `user_permission_overrides` | `user_id`、`permission_id`、`effect`(allow/deny) | (`user_id`,`permission_id`) 唯一 |

- 保留 `users.role` 作为**主角色**（登录展示、JWT 载荷、兼容旧逻辑）；授权一律以 `user_roles` 为准，主角色变化时同步一条 `user_roles`。
- 内置角色：`admin`、`teacher`、`student` 三个主角色，外加 `student_affairs`（学工处）、`academic_director`（教务主任）两个岗位角色；岗位角色通过 `user_roles` 叠加到教师账号，不改变 `users.role`。
- 请假策略里的 `head_teacher` 不是角色，而是"班级班主任"关系，审批时按 `class.head_teacher_id` 解析；其余值对应 `roles.code`。
- 种子：首次启动写入全部权限点与三角色默认授权；`python -m campus.db.seed` 幂等同步（按 `code` upsert，不覆盖管理员手改的授权）。
- 配置接口：`GET/PUT /roles/{id}/permissions`、`GET /permissions`、`GET/PUT /users/{id}/roles`、`GET/PUT /users/{id}/permissions`。
- 缓存：暂不做全局缓存，`build_access_context` 每请求一次联表查询；角色/权限变更即时生效。

---

## 4. 领域模型细化

### 4.1 组织与学期（新增 3 张表）

| 表 | 字段 | 约束 |
| --- | --- | --- |
| `departments` | `code`、`name`、`kind`(college/office)、`parent_id`、`is_active` | `code` 唯一、`name` 唯一 |
| `subjects` | `code`、`name`、`department_id`、`is_active` | `code` 唯一、`name` 唯一 |
| `semesters` | `name`(如 `2024-2025-1`)、`start_date`、`end_date`、`status`(planned/active/closed)、`is_current` | `name` 唯一；`is_current` 由 service 保证唯一 |

说明：年级不再用字符串，`school_classes.grade_year` 用整数（2023/2024），UI 显示"2023 级"。

### 4.2 教师域

**`teachers` 扩展字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `subject_id` | FK subjects | 学科（语文/数学/计算机…） |
| `position` | enum/字符串 | 行政职务：无/班主任/教研组长/年级主任/教务主任/学工主任 |
| `hire_date` | date | 入职日期 |
| `employment_status` | enum | 在职/外聘/退休/离职 |
| `staff_type` | enum | 编制/合同/兼职/实习 |
| `education` | enum | 本科/硕士/博士/其他 |
| `office` | string | 办公室 |
| `workload_limit` | int | 周课时上限（工作量预警用） |

**`teacher_leaves`（并入统一请假表，见 4.7）。**

**教师工作量**不单独建表：按学期聚合 `schedules` 节次 + `courses.hours`，由报表服务计算。

### 4.3 学生域

**`students` 扩展字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `enroll_date` | date | 入学日期 |
| `status` | enum | 在读/休学/退学/毕业/保留学籍 |
| `seat_no` | int | 班内座位号（展示用） |
| `seat_row` / `seat_col` | int | 座位表行列（网格渲染） |
| `id_card_masked` | string | 身份证脱敏值（如 `3301**********1234`）；是否采集见第 10 节 |
| `address` | string | 家庭住址（sensitive） |
| `guardian_name` / `guardian_phone` | string | 监护人 |
| `class_role` | enum | 班长/副班长/团支书/学习委员/生活委员/无 |
| `residence_type` | enum | 住校/走读 |

**`student_status_history`（学籍异动，P2）：**

| 字段 | 说明 |
| --- | --- |
| `student_id`、`from_status`、`to_status`、`effective_date`、`reason`、`operator_id` | 休学/复学/转班/退学/毕业留痕，学生详情页时间线展示 |

### 4.4 班级域

**`school_classes` 扩展字段：**

| 字段 | 说明 |
| --- | --- |
| `department_id` | 所属院系 |
| `grade_year` | 年级（整数） |
| `major` | 专业（保留字符串，后续可升 `majors` 表） |
| `classroom` | 固定教室 |
| `capacity` | 班级容量 |
| `status` | 在读/毕业/停用 |
| `head_teacher_id` | 班主任（已有） |

**座位表**：不建独立表，使用 `students.seat_row/seat_col/seat_no`，班级详情页按 `capacity` 网格渲染；
空位显示为空，拖动/调整由 `class:seat:manage` 权限控制，写入学生座位字段（或后续升级 `seat_assignments` 历史表）。

> 若确认要"座位调整历史"，再增加 `seat_history`；默认先不做，控制范围。

### 4.5 课程域

**`courses` 扩展字段：**

| 字段 | 说明 |
| --- | --- |
| `subject_id` | 学科 |
| `department_id` | 开课院系 |
| `semester_id` | 学期外键（替代字符串 `semester`，保留旧字段做兼容视图/回填） |
| `course_type` | 必修/选修/实践/公选 |
| `assessment_type` | 考试/考查/论文/项目 |
| `grade_scheme` | JSON：`{"usual":0.4,"midterm":0.0,"exam":0.6}`，默认 40/60 |
| `textbook` | 教材 |
| `is_active` | 是否可选 |
| `grade_year` | 开课年级 |

**`course_teachers`**（多教师）：`course_id`、`teacher_id`、`role`(primary/assistant)，唯一 (`course_id`,`teacher_id`)。
保留 `courses.teacher_id` 作为"主讲"兼容字段，迁移时回填。

**`course_classes`**（面向班级）：`course_id`、`class_id`，唯一对。用于"这门课面向哪些行政班"和教师数据范围推导。

### 4.6 教务运行

**`schedules` 扩展：** `semester_id`、`class_id`（行政班）、`status`(正常/停课)、`teacher_id`（冗余，便于查询）。

**`schedule_changes`（调课/停课/代课）：**

| 字段 | 说明 |
| --- | --- |
| `schedule_id`、`change_date`、`kind`(swap/cancel/substitute) | 针对哪一天、哪种变更 |
| `new_weekday`/`new_start_period`/`new_end_period`/`new_classroom`/`new_teacher_id` | 变更后信息 |
| `reason`、`status`(pending/approved/rejected)、`requested_by`、`approved_by` | 审批流 |

**`scores` 扩展：** `midterm_score`、`published`、`published_at`、`scheme_snapshot`(JSON)。
总评按 `course.grade_scheme` 计算，任一分项缺失且权重 > 0 时不计算；发布后学生可见，修改需 `score:unlock`。

**`attendance` 扩展：** `period_no`（节次）、`schedule_id`（可选）、`leave_request_id`（可选）。
唯一键改为 (`student_id`,`course_id`,`date`,`period_no`)；SQLite 需 `batch_alter_table` 重建表（见第 7 节）。

### 4.7 请假审批（两级，统一表）

**`leave_requests`：**

| 字段 | 说明 |
| --- | --- |
| `applicant_user_id` | 申请人账号 |
| `applicant_type` | student / teacher |
| `student_id` / `teacher_id` | 二选一（CHECK 约束） |
| `leave_type` | 事假/病假/公出/调休/婚丧/产假/其他 |
| `start_at` / `end_at` | 起止时间（datetime） |
| `days` | 折算天数（半天粒度用 0.5） |
| `reason` | 事由 |
| `status` | pending/approved/rejected/cancelled |
| `current_step` / `required_steps` | 当前审批级（1/2）、总级数（1 或 2） |
| `final_approver_id` / `decided_at` | 最终审批人/时间 |
| `attachment_path` | 可选（本地 `uploads/`，P2.5，默认不做） |

**`leave_approvals`（每级一条）：**

| 字段 | 说明 |
| --- | --- |
| `leave_request_id`、`step_no` | 所属申请与级别，唯一 (`leave_request_id`,`step_no`) |
| `approver_role_code` | 该级应审批的角色（如 `head_teacher` / `student_affairs` / `academic_director` / `admin`） |
| `approver_id`、`status`(pending/approved/rejected)、`remark`、`decided_at` | 实际审批人与结果 |

**`leave_policies`（两级规则可配置）：**

| 字段 | 说明 |
| --- | --- |
| `applicant_type`、`step_no`、`approver_role_code`、`min_days` | 例如学生：step1 班主任、step2 学工处；教师：step1 教务主任、step2 管理员 |

审批规则（两级）：

- 学生请假：第 1 级班主任 → 第 2 级学工处（`student_affairs`）。
- 教师请假：第 1 级教务主任（`academic_director`）→ 第 2 级校级管理员。
- 每一级通过后推进 `current_step`；任一级驳回 → `rejected` 并终止；两级通过 → `approved`。
- 同一级有多人持有时，任一可批；管理员可代批任意级并留痕。
- `days < min_days`（默认 3 天）只走第 1 级；`>= min_days` 走两级（由 `leave_policies` 配置）。
- 审批通过后：`attendance` 对应日期自动标记 `LEAVE`（或由任课教师确认），学生端可见。
- 撤销：仅 `pending` 且第一级未批时申请人可撤销；已通过需管理员撤销并回写考勤。

### 4.8 宿舍与缴费

**`dorm_assignments` 扩展：** `start_date`、`end_date`、`status`(在住/退宿)。

**`fees` 扩展：** `fee_type`(学费/住宿费/教材费/补考费/其他)、`semester_id`、`paid_amount`、`discount_amount`、`payment_method`、`receipt_no`。
状态扩展为：未缴/部分缴/已缴/减免/已退。

### 4.9 通知与审计

**`notices`：** `title`、`content`、`audience`(all/teacher/student/class)、`class_id`、`publisher_id`、`published_at`、`is_pinned`、`expires_at`。

**`audit_logs`：** 见 3.10。

### 4.10 新增表汇总

| 阶段 | 新增表 |
| --- | --- |
| P0 | `roles`、`permissions`、`role_permissions`、`user_roles`、`user_permission_overrides` |
| P1 | `departments`、`subjects`、`semesters` |
| P2 | `leave_requests`、`leave_approvals`、`leave_policies`、`notices`、`student_status_history` |
| P3 | `course_teachers`、`course_classes`、`schedule_changes` |
| P4 | `audit_logs` |

新增枚举（`models/enums.py`）：`StudentStatus`、`EmploymentStatus`、`StaffType`、`Education`、`ClassRole`、
`ResidenceType`、`LeaveType`、`LeaveStatus`、`NoticeAudience`、`CourseType`、`AssessmentType`、`ScheduleChangeKind`、
`DepartmentKind`、`FeeType`、`SemesterStatus`。

---

## 5. 页面与交互

| 页面 | 角色 | 关键内容 |
| --- | --- | --- |
| 学生 360 详情 | admin/班主任/本人 | 基本信息、学籍异动时间线、成绩、考勤、请假、缴费、宿舍、座位 |
| 教师档案 | admin/本人/同事 | 学科、职务、入职、在职状态、任课、工作量、请假记录 |
| 班级详情 | admin/班主任/任课/本班学生 | 花名册、座位表网格、班主任、课程表、班级统计 |
| 座位表 | admin/班主任（写），学生（读） | 行列网格，拖拽/编号调整，空位与本人高亮 |
| 请假中心 | 全体 | 我的申请、待我审批、历史；状态流转 |
| 调课中心 | admin/教师 | 申请调课/停课/代课，审批 |
| 通知中心 | 全体 | 列表、置顶、按角色/班级过滤 |
| 系统设置 | admin | 院系、学科、学期、账号管理、角色权限矩阵、审计日志 |
| 报表 | admin/班主任 | 教师工作量、学科成绩、班级对比、考勤趋势 |

前端结构调整（建议）：

```text
web/assets/
├── api.js          （已有）
├── ui.js           （已有）
├── charts.js       （已有）
├── core.js         新增：状态、权限 can()、路由、lookups
├── shell.js        新增：侧边栏/顶栏/搜索
└── views/
    ├── dashboard.js
    ├── students.js
    ├── teachers.js
    ├── classes.js
    ├── courses.js
    ├── enrollments.js
    ├── scores.js
    ├── attendance.js
    ├── schedules.js
    ├── dorms.js
    ├── fees.js
    ├── leaves.js
    ├── notices.js
    └── admin.js      （院系/学科/学期/账号/审计）
```

原生 ESM，无构建链；`index.html` 只引 `app.js` 入口，入口再 import 各视图。文件清单同步 `AGENTS.md`。

---

## 6. 分阶段实施

> 估算按 1 人开发、含测试与文档；可根据确认结果裁剪。

### P0 权限内核 + 权限配置（约 3 人日）

- 迁移 `0002_authz`：`roles`、`permissions`、`role_permissions`、`user_roles`、`user_permission_overrides` + 种子。
- `services/access.py`：Permission、AccessContext、DataScope、`require()`、字段策略；`services/authz.py` 角色权限配置。
- `api/deps.py`：`Access` 依赖；`AdminUser/StaffUser` 保留为兼容别名。
- 全部 `api/v1/*` 路由改用权限点守卫。
- 全部列表/详情 service 注入 scope；学生/教师/班级/课程/选课/成绩/考勤/课表/宿舍/缴费逐项收紧。
- `schemas` 拆分 `Brief/Detail/Private`，`/auth/me` 返回 permissions/nav/scope。
- 前端：`can()`、菜单由 `nav` 渲染、列/按钮按权限显隐。
- 系统设置：角色权限矩阵、用户角色分配、用户级 allow/deny。
- 测试：角色 × 接口 × 期望矩阵（参数化），越权 403、跨班不可见、字段脱敏。
- 验收：学生拉不到他人数据；教师只能看本班/本人课程；后台改权限即时生效。

### P1 组织与档案细化（约 3 人日）

- 迁移 `0003_org_and_profiles`：`departments`、`subjects`、`semesters` + 教师/学生/班级扩展列。
- 模型、schema、仓储、service、路由、种子数据。
- 页面：教师档案详情、学生 360 详情、班级详情（基础）、系统设置（院系/学科/学期）。
- 测试：档案字段校验、组织唯一约束、迁移后旧数据可用。

### P2 请假、座位、班级（约 3 人日）

- 迁移 `0004_leave_seat_notice`：`leave_requests`、`leave_approvals`、`leave_policies`、`notices`、`student_status_history` + 座位/学籍列。
- 请假申请/审批/撤销；考勤联动；学生端与教师端页面。
- 班级座位表网格 + 座位调整；班级花名册。
- 通知发布/阅读。
- 测试：审批流转、越权审批、座位冲突、通知受众过滤。

### P3 教学运行（约 3 人日）

- 迁移 `0005_teaching_runtime`：`course_teachers`、`course_classes`、`schedule_changes` + 课程/课表/成绩/考勤扩展。
- 多教师、面向班级、学期外键、课程类型/考核方式/教材。
- 调课/停课申请与审批；课表按学期/周次展示。
- 成绩构成（平时/期中/期末）、发布/解锁；考勤按节次。
- 测试：成绩计算、发布后锁定、调课冲突、考勤唯一键。

### P4 管理与审计（约 2 人日）

- 迁移 `0006_audit`：`audit_logs`。
- 写操作审计、管理员审计页；账号管理（重置密码、启停用、绑定档案）。
- CSV 导入导出（学生/成绩/考勤），导出受权限与审计约束。
- 测试：审计写入、敏感字段不落库、导出权限。

### P5 报表与打磨（约 2 人日）

- 教师工作量、学科成绩分析、班级对比、考勤趋势、缴费收缴率。
- 文档：`README`、`docs/API.md`、`docs/ARCHITECTURE.md`、`AGENTS.md` 清单、截图。
- 覆盖率目标：总体 ≥ 80%，新增模块 ≥ 85%。

合计约 **17 人日**。若只想先解决"权限 + 教师/学生档案 + 请假"三个痛点，做 **P0 + P1 + P2**（约 10 人日）即可明显改善。

---

## 7. 迁移与兼容

1. **Alembic 新迁移**（禁止改 `0001`），每阶段一个，均写显式 DDL。
2. SQLite 用 `op.batch_alter_table(...)` 做加列/改约束；`attendance` 唯一键变更会重建表，需先备份数据。
3. 新列一律可空或带默认值；旧行回填：`students.status='active'`、`teachers.employment_status='active'`、
   `courses.semester_id` 按名称匹配、`courses.grade_scheme` 默认 40/60。
4. 旧字段保留：`courses.semester`（字符串）在 P3 迁移后仍保留一版，读接口优先 `semester_id`，写接口双写；
   下个版本再删。
5. 种子数据 `db/seed.py` 扩展：院系、学科、学期、教师学科/职务/入职、学生座位/监护人、请假单、通知。
6. 测试库用 `Base.metadata.create_all` 自动跟随模型，不需要跑迁移；迁移本身用 `alembic upgrade head` 单独验证。

---

## 8. 测试策略

| 测试 | 内容 |
| --- | --- |
| `tests/unit/test_access.py` | 权限点展开、DataScope 计算、字段策略选择 |
| `tests/api/test_permissions_matrix.py` | 参数化：`(role, method, path, expected_status, expected_code)`，覆盖全部路由 |
| `tests/api/test_scope.py` | 教师只能看本班/本人课程；学生只能看自己；跨班/跨课程 403 或空列表 |
| `tests/api/test_field_projection.py` | 他人手机/身份证/住址不出现；学生看教师无联系方式 |
| `tests/api/test_leaves.py` | 申请、审批、撤销、越权审批、考勤联动 |
| `tests/api/test_seats.py` | 座位调整、冲突、权限 |
| `tests/api/test_notices.py` | 受众过滤、置顶排序 |
| `tests/api/test_audit.py` | 写操作留痕、敏感字段脱敏 |
| `tests/api/test_reports.py` | 工作量/成绩/考勤聚合口径 |

原则：断言具体错误码（`FORBIDDEN`/`NOT_FOUND`），不只断言状态码；每个新 service 至少 1 个单元测试。

---

## 9. 风险与取舍

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| 权限矩阵回归 | 改一处漏一处 | 参数化矩阵测试 + 路由统一用 `require()`，禁止裸角色判断 |
| SQLite 改约束 | 迁移失败/丢数据 | `batch_alter_table` + 迁移前备份 + 测试库跑一遍 |
| `app.js` 继续膨胀 | 难维护 | P0 时拆 `core.js/shell.js/views/*`，同步 AGENTS 清单 |
| scope 查询变复杂 | 性能/漏过滤 | 统一 scope 构造器 + `class_id`/`course_id` 索引 |
| 敏感字段合规 | 泄露风险 | 身份证只存脱敏值；住址/监护人仅敏感角色可见；日志脱敏 |
| 范围过大 | 交付延期 | 按 P0–P5 分期，每期可独立验收；先确认范围 |

---

## 10. 已确认决策

| # | 决策 | 结论 |
| --- | --- | --- |
| 1 | 本轮范围 | **全量 P0–P5** |
| 2 | 权限存哪里 | **数据库权限表 + 后台配置**（5 张表，见 3.11） |
| 3 | 身份证等敏感信息 | **采集但只存脱敏值**，不落明文 |
| 4 | 请假审批层级 | **两级**（学生：班主任→学工处；教师：教务主任→管理员） |
| 5 | 前端是否拆分 | 拆分 `views/*`（默认执行） |
| 6 | 旧演示库 | 迁移保留（默认执行） |

接下来按 P0 → P1 → P2 → P3 → P4 → P5 顺序实施；每阶段完成后跑门禁并汇报。

---

## 11. 实施状态（v0.8.0，2026-11-07）

| 阶段 | 状态 | 主要产出 |
| --- | --- | --- |
| P0 权限内核 | ✅ | 5 张权限表、48 权限点、数据范围、字段脱敏、`/authz/*`、前端权限驱动 |
| P1 组织与档案 | ✅ | 院系/学科/学期、教师/学生/班级扩展字段、系统设置页 |
| P2 请假/座位/通知 | ✅ | 两级审批与考勤联动、座位表、通知、学籍异动 |
| P3 教学运行 | ✅ | 多教师/面向班级、调课审批、成绩构成与发布、考勤节次 |
| P4 审计/账号/导入导出 | ✅ | `audit_logs`、账号启停用与重置密码、CSV 导入导出 |
| P5 报表与收尾 | ✅ | 工作量/学科/班级报表、文档同步、最终门禁 |

最终门禁：`ruff check`、`ruff format --check`、`mypy src`、`pytest --cov`（90 项，覆盖率 89.55%）全部通过；
Alembic 迁移 `0001`–`0006` 已在旧库副本上逐级验证。
