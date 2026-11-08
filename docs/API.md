# API 文档

- Base URL：`http://127.0.0.1:8000/api/v1`
- 交互式文档：`/docs`（Swagger UI）、`/openapi.json`
- 编码：请求与响应均为 `application/json; charset=utf-8`

## 1. 通用约定

### 鉴权

除 `POST /auth/login` 与 `GET /health` 外，所有接口都需要：

```http
Authorization: Bearer <access_token>
```

令牌有效期默认 60 分钟（`ACCESS_TOKEN_EXPIRE_MINUTES`），载荷包含 `sub`（用户 ID）、`role`、`exp`。

### 分页

列表接口统一使用：

| 参数 | 类型 | 默认 | 约束 |
| --- | --- | --- | --- |
| `page` | int | 1 | ≥ 1 |
| `page_size` | int | 20 | 1..100 |

响应：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

### 错误结构

```json
{
  "code": "NOT_FOUND",
  "message": "课程不存在",
  "details": []
}
```

| code | HTTP | 说明 |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | 缺少或无效令牌、密码错误 |
| `TOKEN_EXPIRED` | 401 | 令牌过期 |
| `FORBIDDEN` | 403 | 角色不允许、数据归属不符、账号停用 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `DUPLICATE_KEY` | 409 | 唯一键冲突（学号/工号/课程代码/班级名等） |
| `COURSE_FULL` | 409 | 课程容量已满 |
| `ALREADY_ENROLLED` | 409 | 重复选课 |
| `SCORE_LOCKED` | 409 | 已有成绩，不能退课 |
| `REFERENCE_EXISTS` | 409 | 存在关联数据（班级有学生、课程有选课、房间有人） |
| `CONFLICT` | 409 | 其它状态冲突（未选课录入成绩、床位冲突、已缴费等） |
| `VALIDATION_ERROR` | 422 | 参数校验失败，`details` 为 `{loc,msg,type}` 列表 |

## 2. 认证

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/health` | 匿名 | 存活探针 |
| POST | `/auth/login` | 匿名 | 登录换取 JWT |
| GET | `/auth/me` | 登录 | 当前用户 + 权限点 + 导航 + 数据范围 |
| POST | `/auth/change-password` | 登录 | 修改密码 |

登录请求：

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin", "password": "admin123"}
```

响应 `200`：

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {"id": 1, "username": "admin", "role": "admin", "is_active": true}
}
```

修改密码请求：

```json
{"old_password": "admin123", "new_password": "newpass456"}
```

`GET /auth/me` 响应：

```json
{
  "id": 3,
  "username": "t001",
  "role": "teacher",
  "is_active": true,
  "display_name": "教师1",
  "permissions": ["attendance:read", "attendance:write", "student:read", "score:write"],
  "nav": [
    {"label": "总览", "items": [{"id": "dashboard", "label": "仪表盘", "icon": "dashboard"}]},
    {"label": "教务", "items": [{"id": "students", "label": "学生", "icon": "students"}]}
  ],
  "scope": {"student_id": null, "teacher_id": 1, "class_ids": [1, 2], "course_ids": [1, 3]}
}
```

## 2.1 权限管理

> v2 起权限改为“权限点 + 数据范围”。下表“角色”列是历史标注，实际以 `permission:action` 为准：
> 管理类写操作需要对应 `:manage` 权限，读操作需要 `:read` 并按 `AccessContext.scope` 过滤。

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/authz/roles` | `role:manage` | 角色及其权限码 |
| PUT | `/authz/roles/{id}/permissions` | `role:manage` | 整体替换角色权限 |
| GET | `/authz/permissions` | `role:manage` | 权限点目录 |
| GET | `/authz/users/{id}/roles` | `role:manage` | 用户角色与覆盖项 |
| PUT | `/authz/users/{id}/roles` | `role:manage` | 整体替换用户角色 |
| PUT | `/authz/users/{id}/permissions` | `role:manage` | 整体替换用户级 allow/deny |

替换角色权限：

```json
{"permissions": ["student:read", "score:read", "score:write"]}
```

用户级覆盖：

```json
{"items": [{"code": "student:read", "effect": "allow"}, {"code": "fee:pay", "effect": "deny"}]}
```

权限变更**即时生效**：`/auth/me` 与每次请求都会重新解析数据库授权。

## 2.2 组织：院系 / 学科 / 学期

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/org/departments` | `department:read` | 院系/处室列表 |
| POST | `/org/departments` | `department:manage` | 新增院系 |
| PATCH | `/org/departments/{id}` | `department:manage` | 更新院系 |
| GET | `/org/subjects` | `subject:read` | 学科列表 |
| POST | `/org/subjects` | `subject:manage` | 新增学科 |
| PATCH | `/org/subjects/{id}` | `subject:manage` | 更新学科 |
| GET | `/org/semesters` | `semester:read` | 学期列表 |
| POST | `/org/semesters` | `semester:manage` | 新增学期 |
| PATCH | `/org/semesters/{id}` | `semester:manage` | 更新学期 |
| POST | `/org/semesters/{id}/activate` | `semester:manage` | 设为当前学期 |

新增院系：

```json
{"code": "CSE", "name": "计算机学院", "kind": "college"}
```

新增学期（`is_current=true` 会自动取消其他当前学期）：

```json
{
  "name": "2025-2026-1",
  "start_date": "2025-09-01",
  "end_date": "2026-01-15",
  "weeks": 20,
  "is_current": true
}
```

## 3. 学生

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/students` | admin/teacher | 分页检索；`keyword`（学号/姓名）、`class_id`、`is_active` |
| POST | `/students` | admin | 新增；`student_no` 唯一 |
| GET | `/students/{id}` | admin/teacher | 详情 |
| PATCH | `/students/{id}` | admin | 部分更新 |
| DELETE | `/students/{id}` | admin | 软停用（`is_active=false`） |
| GET | `/students/me` | student | 本人档案 |
| GET | `/students/{id}/transcript` | admin/teacher/本人 | 成绩单 |

v2 新增字段：`status`（学籍状态）、`enroll_date`、`class_role`（班干部）、`residence_type`（住校/走读）、
`seat_no`/`seat_row`/`seat_col`（座位）、`guardian_name`/`guardian_phone`、`address`、`id_card_masked`（脱敏值）。
敏感字段仅管理员、班主任、本人可见，其他教师读取时返回 `null`。

新增请求：

```json
{
  "student_no": "S031",
  "name": "张三",
  "gender": "male",
  "birth_date": "2005-03-01",
  "enroll_date": "2023-09-01",
  "status": "active",
  "phone": "13800000000",
  "class_id": 1,
  "class_role": "monitor",
  "residence_type": "boarding",
  "seat_no": 7,
  "guardian_name": "张父",
  "guardian_phone": "13900000000",
  "address": "杭州市示例路 1 号",
  "id_card_masked": "3301**********1234"
}
```

成绩单响应：

```json
[
  {"course_code": "CS101", "course_name": "程序设计基础", "credits": 4.0, "semester": "2024-2025-1", "final_score": 86.0}
]
```

## 4. 教师

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/teachers` | 登录 | 分页检索；`keyword`、`department` |
| POST | `/teachers` | admin | 新增；`teacher_no` 唯一 |
| GET | `/teachers/{id}` | 登录 | 详情 |
| PATCH | `/teachers/{id}` | admin | 部分更新 |
| DELETE | `/teachers/{id}` | admin | 软停用 |

v2 新增字段：`subject_id`（学科）、`position`（职务）、`hire_date`（入职日期）、
`employment_status`（在职状态）、`staff_type`（编制类型）、`education`（学历）、`office`（办公室）、`workload_limit`（周课时上限）。

```json
{
  "teacher_no": "T006",
  "name": "教师六",
  "title": "讲师",
  "subject_id": 1,
  "position": "教研组长",
  "hire_date": "2018-09-01",
  "employment_status": "active",
  "staff_type": "permanent",
  "education": "master",
  "office": "教学楼 302",
  "workload_limit": 16
}
```

## 5. 班级

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/classes` | 登录 | 全量列表（不分页） |
| POST | `/classes` | admin | 新增；`name` 唯一 |
| PATCH | `/classes/{id}` | admin | 部分更新 |
| DELETE | `/classes/{id}` | admin | 班级下无学生才可删除 |

v2 新增字段：`department_id`（院系）、`classroom`（固定教室）、`capacity`（容量）、`status`（班级状态）、`grade_year`（年级年份）。

## 6. 课程

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/courses` | 登录 | 分页；`keyword`、`semester`、`teacher_id` |
| POST | `/courses` | admin | 新增；`code` 唯一 |
| GET | `/courses/{id}` | 登录 | 详情 |
| PATCH | `/courses/{id}` | admin | 部分更新 |
| DELETE | `/courses/{id}` | admin | 无选课记录才可删除 |
| GET | `/courses/{id}/roster` | admin/teacher | 选课名单 |

v2 新增字段：`semester_id`、`subject_id`、`department_id`、`course_type`（required/elective/practice/public）、
`assessment_type`（exam/check/paper/project）、`grade_scheme`（权重 JSON）、`textbook`、`grade_year`、`is_active`。

课程教师与面向班级：

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/courses/{id}/teachers` | `course:read` | 课程教师（主讲/辅导） |
| PUT | `/courses/{id}/teachers` | `course:manage` | 整体替换课程教师 |
| GET | `/courses/{id}/classes` | `course:read` | 面向班级 |
| PUT | `/courses/{id}/classes` | `course:manage` | 整体替换面向班级 |
| POST | `/courses/{id}/publish-scores` | `score:publish` | 发布课程成绩 |
| POST | `/courses/{id}/unpublish-scores` | `score:unlock` | 撤回成绩（管理员） |

```json
{"items": [{"teacher_id": 1, "role": "primary"}, {"teacher_id": 2, "role": "assistant"}]}
```

## 7. 选课

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/enrollments` | 登录 | 分页；学生自动限定本人；`student_id`、`course_id` |
| POST | `/enrollments` | student/admin | 选课；学生只需 `course_id`，管理员需额外 `student_id` |
| DELETE | `/enrollments/{id}` | student（本人）/admin | 退课；有成绩则 `409 SCORE_LOCKED` |

请求：

```json
{"course_id": 3}
```

## 8. 成绩

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/scores` | 登录 | 分页；学生自动限定本人；`course_id`、`student_id`、`semester` |
| POST | `/scores` | admin/teacher | 批量录入；教师仅本人课程 |
| PATCH | `/scores/{id}` | admin/teacher | 修改单项 |

v2 新增：`midterm_score`（期中）、`published`（发布状态）。总评按课程 `grade_scheme` 权重计算；
学生只看到 `published=true` 的成绩。

批量录入：

```json
{
  "items": [
    {"student_id": 1, "course_id": 3, "usual_score": 80, "exam_score": 90}
  ]
}
```

总评规则：`round(usual * 0.4 + exam * 0.6, 2)`，任一分项缺失则为 `null`。

## 9. 考勤

考勤新增 `period_no`（节次，默认 1）；同一学生/课程/日期/节次唯一。

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/attendance` | 登录 | 分页；学生自动限定本人；`course_id`、`student_id`、`day`(YYYY-MM-DD) |
| POST | `/attendance/bulk` | admin/teacher | 批量登记；(`student_id`,`course_id`,`date`) 幂等覆盖 |

```json
{
  "items": [
    {"student_id": 1, "course_id": 3, "date": "2026-11-07", "status": "present", "remark": ""}
  ]
}
```

`status`：`present` / `late` / `absent` / `leave`。

## 10. 课表

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/schedules` | 登录 | 分页；`class_id`、`teacher_id`、`weekday` |
| POST | `/schedules` | admin/teacher | 新增；同一课程同星期同起始节次唯一 |
| DELETE | `/schedules/{id}` | admin/teacher | 删除 |

```json
{"course_id": 3, "weekday": 1, "start_period": 1, "end_period": 2, "classroom": "A101", "weeks": "1-16"}
```

| GET | `/schedules/{id}/changes` | `schedule:read` | 某排课的调课记录（使用 `/schedule-changes?schedule_id` 过滤） |
| POST | `/schedule-changes` | `schedule:change` | 发起调课/停课/代课 |
| GET | `/schedule-changes` | `schedule:read` | 调课申请列表（按课程范围） |
| POST | `/schedule-changes/{id}/approve` | `schedule:change` + 管理员 | 通过 |
| POST | `/schedule-changes/{id}/reject` | `schedule:change` + 管理员 | 驳回 |

```json
{
  "schedule_id": 1,
  "change_date": "2026-11-10",
  "kind": "cancel",
  "reason": "教师出差"
}
```

调课审批通过后：停课把排课状态置为 `cancelled`；调课更新星期/节次/教室。

## 11. 宿舍

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/dorms` | 登录 | 分页；`building`；含 `occupied` |
| POST | `/dorms` | admin | 新增房间；(`building`,`room_no`) 唯一 |
| DELETE | `/dorms/{id}` | admin | 无入住才可删除 |
| GET | `/dorms/assignments` | 登录 | 分页；`dorm_id` |
| POST | `/dorms/assignments` | admin | 分配床位 |
| DELETE | `/dorms/assignments/{id}` | admin | 退宿 |

分配规则：学生未分配、房间未满、性别匹配、床位未被占用。

## 12. 缴费

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/fees` | 登录 | 分页；学生自动限定本人；`student_id`、`status` |
| POST | `/fees` | admin | 新增费用项 |
| POST | `/fees/{id}/pay` | student（本人）/admin | 缴费；已缴返回 409 |

```json
{"student_id": 1, "item": "学费", "amount": 5800, "due_date": "2026-12-31"}
```

## 13. 请假

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/leaves` | `leave:read` | 分页；`status`、`applicant_type`、`mine` |
| GET | `/leaves/pending` | `leave:approve` | 待我审批的申请 |
| POST | `/leaves` | `leave:apply` | 提交申请 |
| GET | `/leaves/{id}` | `leave:read` | 详情（按数据范围） |
| POST | `/leaves/{id}/approve` | `leave:approve` | 通过当前级 |
| POST | `/leaves/{id}/reject` | `leave:approve` | 驳回当前级 |
| POST | `/leaves/{id}/cancel` | `leave:apply` | 撤销本人未审批申请 |

提交申请：

```json
{
  "leave_type": "sick",
  "start_at": "2026-11-10T08:00:00",
  "end_at": "2026-11-12T18:00:00",
  "reason": "住院治疗"
}
```

审批规则：学生第 1 级班主任、第 2 级学工处；教师第 1 级教务主任、第 2 级管理员。
请假天数 < 3 天只走一级，≥ 3 天走两级（由 `leave_policies` 配置）。
学生请假最终通过后，区间内的考勤自动标记为 `leave`。

## 14. 通知

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/notices` | `notice:read` | 按受众、班级与群组过滤 |
| POST | `/notices` | `notice:manage` | 发布 |
| PATCH | `/notices/{id}` | `notice:manage` | 更新 |
| DELETE | `/notices/{id}` | `notice:manage` | 删除 |

```json
{
  "title": "期末安排",
  "content": "请查看考试安排",
  "audience": "group",
  "group_id": 1,
  "is_pinned": true
}
```

受众取值为 `all` / `teacher` / `student` / `class` / `group`。教师只能发布本人担任班主任班级的通知；
群组通知仅管理员可发布，群组成员在 `/notices` 中可见。

## 15. 座位与学籍

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/classes/{id}/seats` | `class:seat:read` | 座位表网格 |
| PUT | `/classes/{id}/seats` | `class:seat:manage` | 批量调整（班主任/管理员） |
| POST | `/students/{id}/status` | `student:manage` | 变更学籍并留痕 |
| GET | `/students/{id}/status-history` | 按数据范围 | 学籍异动时间线 |

调整座位：

```json
{
  "items": [
    {"student_id": 1, "seat_no": 1, "seat_row": 1, "seat_col": 1},
    {"student_id": 2, "seat_no": 2, "seat_row": 1, "seat_col": 2}
  ]
}
```

变更学籍：

```json
{"status": "suspended", "effective_date": "2026-11-10", "reason": "病休一学期"}
```

## 16. 审计与账号

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/audit-logs` | `audit:read` | 写操作审计；`user_id`、`method`、`path` 过滤 |
| GET | `/accounts` | `account:manage` | 账号列表（含档案姓名） |
| PATCH | `/accounts/{id}` | `account:manage` | 启用/停用 |
| POST | `/accounts/{id}/reset-password` | `account:manage` | 重置密码 |

```json
{"is_active": false}
```

## 17. 导入导出

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/transfer/export/students` | `student:read` | 学生 CSV（按数据范围） |
| GET | `/transfer/export/scores` | `score:read` | 成绩 CSV（学生仅已发布） |
| GET | `/transfer/export/attendance` | `attendance:read` | 考勤 CSV（按数据范围） |
| POST | `/transfer/import/students` | `student:manage` | 学生 CSV 导入（按学号 upsert） |

导入请求：

```json
{
  "csv": "student_no,name,gender,status,class_id,phone\nS100,新同学,male,active,1,13800000000"
}
```

响应：`{"created": 1, "updated": 0, "errors": []}`。

## 18. 报表

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/reports/workload` | `dashboard:read` | 教师工作量；管理员全量，教师本人 |
| GET | `/reports/subjects` | `dashboard:read` | 学科成绩；教师限本人课程 |
| GET | `/reports/classes` | `dashboard:read` | 班级对比；教师限本人班级 |

工作量响应：

```json
[
  {
    "teacher_id": 1,
    "teacher_no": "T001",
    "teacher_name": "教师1",
    "department": "学院1",
    "subject_name": "计算机",
    "position": "教务主任",
    "course_count": 2,
    "weekly_periods": 4,
    "hours": 112,
    "student_count": 24,
    "class_count": 2
  }
]
```

## 19. 仪表盘

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/dashboard/summary` | 登录 | 兼容旧版：学生/教师/课程/班级数、选课数、出勤率、未缴笔数与金额、平均总分 |
| GET | `/dashboard/overview` | 登录 | 角色化聚合：KPI、考勤趋势、成绩分布、费用构成、课程饱和度、班级对比、预警、最近动态、个人面板；`days` 取值 7/30/90（默认 30） |

`/dashboard/overview` 会按角色裁剪数据：管理员看全校；教师只看本人所授课程；学生只看本人成绩、考勤与费用。
出勤率口径为「出勤 + 迟到」占全部登记记录的比例，并限定在 `days` 时间窗内。

```json
{
  "role": "admin",
  "semester": "2024-2025-1",
  "generated_at": "2026-11-07T11:10:00Z",
  "days": 30,
  "kpis": [
    {
      "key": "attendance",
      "label": "平均出勤率",
      "value": 92.4,
      "unit": "%",
      "delta": 1.8,
      "hint": "近 30 天 · 出勤+迟到",
      "spark": [90.1, 91.2, 93.0],
      "action": { "view": "attendance", "filters": {} }
    }
  ],
  "attendance_trend": {
    "labels": ["10-09"],
    "series": [{ "name": "出勤", "data": [12] }],
    "rate": 92.4
  },
  "score_distribution": {
    "buckets": [{ "label": "<60", "count": 3 }],
    "sample": 120,
    "pass_rate": 86.7,
    "average": 74.31
  },
  "fee_breakdown": {
    "paid_count": 20,
    "unpaid_count": 10,
    "overdue_count": 4,
    "paid_amount": 116000.0,
    "unpaid_amount": 58000.0,
    "overdue_amount": 23200.0,
    "collection_rate": 66.7
  },
  "course_load": [
    {
      "course_id": 1,
      "code": "CS101",
      "name": "程序设计基础",
      "teacher_name": "教师1",
      "enrolled": 28,
      "capacity": 60,
      "rate": 46.7
    }
  ],
  "class_comparison": [
    {
      "class_id": 1,
      "name": "计算机2301",
      "students": 15,
      "average_score": 78.2,
      "attendance_rate": 93.1
    }
  ],
  "alerts": [
    {
      "level": "danger",
      "title": "4 笔费用已逾期",
      "detail": "¥23,200.00",
      "action": { "view": "fees", "filters": { "status": "unpaid" } }
    }
  ],
  "recent": [
    { "kind": "enrollment", "text": "学生03 选修了 数据库原理", "at": "2026-11-06T09:20:00Z" }
  ],
  "student": null,
  "teacher": null
}
```

学生角色的 `student` 字段包含 GPA、已修学分、出勤率、待缴金额、不及格课程数与今日课表；
教师角色的 `teacher` 字段包含本人课程的学生数、出勤率、已录/待录成绩与今日课表。

## 20. 变更记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| 0.8.0 | 2026-11-07 | 报表：教师工作量、学科成绩分析、班级对比；前端报表页 |
| 0.7.0 | 2026-11-07 | 审计日志；账号启停用/重置密码；学生/成绩/考勤 CSV 导出与学生导入 |
| 0.6.0 | 2026-11-07 | 课程多教师/面向班级；调课审批；成绩构成与发布；考勤按节次 |
| 0.5.0 | 2026-11-07 | 请假两级审批与考勤联动；通知公告；座位表；学籍异动历史 |
| 0.4.0 | 2026-11-07 | 组织与档案：新增 `/org/departments|subjects|semesters`；教师学科/职务/入职/在职，学生学籍/座位/监护人，班级院系/教室/容量 |
| 0.3.0 | 2026-11-07 | 权限体系 2.0：权限点入库、数据范围与字段脱敏；新增 `/authz/*`；`/auth/me` 返回权限、导航与范围 |
| 0.2.0 | 2026-11-07 | 仪表盘 2.0：新增 `/dashboard/overview`（角色化 KPI、趋势、分布、预警、个人面板）；前端明亮校园风重做并引入本地 ECharts |
| 0.1.0 | 2026-11-07 | 首个版本：认证、教务、考勤、课表、宿舍、缴费、仪表盘 |

## 21. 组织人员树

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/org/tree?person_type=student|teacher&keyword=` | 院系 → 班级 → 学生 / 院系 → 教师；按数据范围过滤 |

返回节点含 `key/type/label/subtitle/count/selectable/has_children/children`，前端用于人员选择树。

## 22. 请假流程与审批

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/leaves?status=&leave_type=&applicant_type=&mine=&keyword=&date_from=&date_to=&page=&page_size=` | 请假列表 |
| GET | `/leaves/{id}` | 详情：审批节点、流转事件、可执行动作 |
| POST | `/leaves` | 提交申请，按流程快照审批节点 |
| POST | `/leaves/{id}/approve` | 通过当前级 |
| POST | `/leaves/{id}/reject` | 驳回当前级 |
| POST | `/leaves/{id}/cancel` | 申请人撤销未审批申请 |
| POST | `/leaves/{id}/revoke` | 管理员撤回已通过申请并回滚考勤 |
| GET | `/leaves/pending` | 待我审批（兼容旧接口，最多 100 条） |
| GET | `/leaves/pending/page` | 待我审批（分页） |
| GET | `/leaves/flows` | 流程列表（`workflow:manage`） |
| GET | `/leaves/flows/preview?applicant_type=&leave_type=&days=` | 条件预览命中流程 |
| POST | `/leaves/flows` | 新建流程 |
| PATCH | `/leaves/flows/{id}` | 更新流程与节点 |
| DELETE | `/leaves/flows/{id}` | 删除未被使用的流程 |

流程条件：申请人类型、请假类型、天数区间、优先级；节点审批人类型：`role` / `head_teacher` / `user` / `group`。

## 23. 日程

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/calendar/events?start=&end=` | 时间范围内的可见日程 |
| GET | `/calendar/today` | 今日日程 |
| POST | `/calendar/events` | 新建日程（参与人、可见范围、提醒） |
| GET | `/calendar/events/{id}` | 详情与参与人回复 |
| PATCH | `/calendar/events/{id}` | 更新日程/参与人 |
| DELETE | `/calendar/events/{id}` | 删除日程 |
| POST | `/calendar/events/{id}/rsvp` | 参与人接受/拒绝 |

可见范围：`personal` / `department` / `class` / `school`。仪表盘 `today_events` 同步返回今日日程。

## 24. 群组

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/groups?keyword=` | 群组列表与成员 |
| POST | `/groups` | 新建群组（成员来自组织树） |
| GET | `/groups/{id}` | 群组详情 |
| PATCH | `/groups/{id}` | 更新群组/整体替换成员 |
| DELETE | `/groups/{id}` | 删除群组 |
| GET | `/groups/{id}/expand` | 展开实际接收用户 |

成员类型：`user` / `student` / `teacher` / `department` / `class`。

## 25. 站内消息

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/notifications?unread_only=&page=&page_size=` | 我的消息 |
| GET | `/notifications/summary` | 未读/总数 |
| POST | `/notifications/{id}/read` | 标记已读 |
| POST | `/notifications/read-all` | 全部已读 |

审批进入下一级、审批结果、日程邀请时会写入消息。

## 26. 课表视图

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/schedules` | 兼容列表 |
| GET | `/schedules/grid?semester_id=&week=&class_id=&teacher_id=` | 周课表网格 |
| GET | `/schedules/day?date=&semester_id=&class_id=&teacher_id=` | 日课表 |
| GET | `/schedules/month?month=YYYY-MM&class_id=&teacher_id=` | 月课表 |
| GET | `/schedules/{id}/detail` | 课程详情、选课人数与调课记录 |
| POST | `/schedules` | 新增排课（冲突校验） |
| DELETE | `/schedules/{id}` | 删除排课 |

周次支持 `1-16`、`1,3,5`、`1-16单/双`。

## 27. 系统参数与导入导出

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/settings` | 系统参数列表 |
| GET | `/settings/periods` | 节次时间 |
| PUT | `/settings/{key}` | 更新参数 |
| GET | `/transfer/export/resource/{resource}?fmt=csv|xlsx|pdf&keyword=` | 通用导出 |
| GET | `/transfer/template/{resource}` | 下载导入模板 |
| POST | `/transfer/import/students` | 学生导入（`dry_run`、`mode=upsert|skip`） |

导出资源：`students`、`teachers`、`courses`、`classes`、`enrollments`、`scores`、`attendance`、`leaves`、`fees`、`schedules`、`audit`。

## 28. 变更记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| 0.9.0 | 2026-11-08 | 人员树；可配置请假审批流与流程图/时间线；日程与今日日程；课表周/日/月网格；群组；群组通知；消息中心；系统设置重构；CSV/Excel/PDF 导出；教师/班级/学生详情；修改密码；列表/分页/筛选/弹窗升级 |
