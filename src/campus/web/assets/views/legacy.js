import { api } from "../api.js";
import { charts } from "../charts.js";
import { el, emptyBlock, fmt, icon, initials, sparkline, toast } from "../ui.js";
import {
  ATTENDANCE_LABEL,
  ASSESSMENT_LABEL,
  AUDIENCE_LABEL,
  CLASS_ROLE_LABEL,
  COURSE_TYPE_LABEL,
  EDUCATION_LABEL,
  EMPLOYMENT_LABEL,
  FEE_LABEL,
  GENDER_LABEL,
  LEAVE_STATUS_LABEL,
  LEAVE_TYPE_LABEL,
  RESIDENCE_LABEL,
  ROLE_LABEL,
  SCHEDULE_STATUS_LABEL,
  SEMESTER_STATUS_LABEL,
  STAFF_TYPE_LABEL,
  STUDENT_STATUS_LABEL,
  WEEKDAY_LABEL,
  classOptions,
  courseOptions,
  departmentOptions,
  ensureLookups,
  groupOptions,
  handleError,
  loadLookups,
  mapName,
  semesterOptions,
  state,
  studentOptions,
  subjectOptions,
  teacherOptions,
  withEmpty,
  can,
  option,
} from "../core/state.js";
import { gotoView, refreshView } from "../core/router.js";
import { confirmDialog, openDrawer, openForm, openModal, promptDialog } from "../components/modal.js";
import { crudView, renderPager, renderTable } from "../components/table.js";

const KPI_ICONS = {
  students: "students",
  courses: "courses",
  attendance: "attendance",
  score: "scores",
  fees: "fees",
  my_courses: "courses",
  my_students: "students",
  pending: "enrollments",
  gpa: "scores",
  credits: "book",
  failed: "alert",
};

function greeting() {
  const hour = new Date().getHours();
  if (hour < 6) return "夜深了";
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function deltaPill(delta) {
  if (delta === null || delta === undefined) return null;
  const up = delta >= 0;
  return el("span", { class: `delta ${up ? "up" : "down"}` }, [
    icon(up ? "arrowUp" : "arrowDown", 12),
    `${Math.abs(delta)}%`,
  ]);
}

function kpiCard(kpi) {
  const digits = kpi.key === "gpa" ? 2 : kpi.unit === "元" ? 2 : 0;
  const display =
    kpi.unit === "元"
      ? fmt.money(kpi.value)
      : kpi.unit === "%"
        ? fmt.pct(kpi.value)
        : fmt.num(kpi.value, digits);
  const unit = ["元", "%", ""].includes(kpi.unit) ? "" : kpi.unit;
  const card = el("article", { class: "kpi" }, [
    el("div", { class: "kpi-head" }, [
      el("span", { class: "kpi-icon" }, [icon(KPI_ICONS[kpi.key] || "spark", 18)]),
      el("span", { class: "kpi-label", text: kpi.label }),
      deltaPill(kpi.delta),
    ]),
    el("div", { class: "kpi-value" }, [
      el("strong", { text: display }),
      unit ? el("span", { class: "kpi-unit", text: unit }) : null,
    ]),
    el("div", { class: "kpi-hint", text: kpi.hint }),
  ]);
  if (Array.isArray(kpi.spark) && kpi.spark.some((value) => value > 0)) {
    const spark = el("div", { class: "kpi-spark" });
    spark.innerHTML = sparkline(kpi.spark);
    card.append(spark);
  }
  if (kpi.action) {
    card.classList.add("clickable");
    card.addEventListener("click", () => gotoView(kpi.action.view));
  }
  return card;
}

function panel(title, subtitle, body, extra = null) {
  return el("section", { class: "panel" }, [
    el("header", { class: "panel-head" }, [
      el("div", {}, [
        el("h3", { text: title }),
        subtitle ? el("p", { text: subtitle }) : null,
      ]),
      extra,
    ]),
    body,
  ]);
}

function hasSignal(trend) {
  return (trend?.series || []).some((series) =>
    (series.data || []).some((value) => value > 0),
  );
}

function alertItem(alert) {
  const label = { danger: "紧急", warning: "关注", info: "提示" }[alert.level] || "提示";
  return el("li", { class: `alert-item ${alert.level}` }, [
    el("span", { class: "alert-icon" }, [icon("alert", 16)]),
    el("div", { class: "alert-copy" }, [
      el("div", { class: "alert-title" }, [
        el("span", { text: alert.title }),
        el("em", { text: label }),
      ]),
      el("p", { text: alert.detail }),
    ]),
    alert.action
      ? el("button", {
          class: "btn tiny",
          text: "去处理",
          onclick: () => gotoView(alert.action.view),
        })
      : null,
  ]);
}

function recentItem(item) {
  const iconName =
    { enrollment: "enrollments", score: "scores", fee: "fees" }[item.kind] || "clock";
  return el("li", { class: "timeline-item" }, [
    el("span", { class: "timeline-dot" }, [icon(iconName, 14)]),
    el("div", { class: "timeline-copy" }, [
      el("p", { text: item.text }),
      el("time", { text: fmt.dateTime(item.at) }),
    ]),
  ]);
}

function scheduleList(items, emptyText = "今天没有排课") {
  if (!items?.length) return emptyBlock(emptyText);
  return el(
    "ul",
    { class: "today-list" },
    items.map((item) =>
      el("li", {}, [
        el("span", { class: "period", text: item.period }),
        el("span", { class: "course", text: item.course }),
        el("span", { class: "room", text: item.classroom }),
      ]),
    ),
  );
}

function studentPanel(panelData) {
  const metrics = [
    ["GPA", fmt.num(panelData.gpa, 2)],
    ["已修学分", `${fmt.num(panelData.credits, 1)} 分`],
    ["我的出勤率", fmt.pct(panelData.attendance_rate)],
    ["待缴金额", fmt.money(panelData.unpaid_amount)],
  ];
  return panel(
    "我的学业",
    "个人成绩、出勤与费用概览",
    el("div", { class: "personal" }, [
      el(
        "div",
        { class: "personal-metrics" },
        metrics.map(([label, value]) =>
          el("div", { class: "personal-metric" }, [
            el("span", { text: label }),
            el("strong", { text: value }),
          ]),
        ),
      ),
      el("div", { class: "personal-today" }, [
        el("h4", { text: "今日课表" }),
        scheduleList(panelData.today),
      ]),
    ]),
  );
}

function teacherPanel(panelData) {
  const rows = panelData.courses || [];
  const body = rows.length
    ? el("div", { class: "table-wrap" }, [
        el("table", { class: "table compact" }, [
          el("thead", {}, [
            el(
              "tr",
              {},
              ["课程", "学生", "出勤率", "成绩进度"].map((label) => el("th", { text: label })),
            ),
          ]),
          el(
            "tbody",
            {},
            rows.map((row) => {
              const ratio = row.students ? Math.round((row.scored / row.students) * 100) : 0;
              return el("tr", {}, [
                el("td", {}, [
                  el("strong", { text: row.name }),
                  el("div", { class: "muted small", text: row.code }),
                ]),
                el("td", { text: `${row.students} 人` }),
                el("td", { text: fmt.pct(row.attendance_rate) }),
                el("td", {}, [
                  el("div", { class: "progress" }, [el("span", { style: `width:${ratio}%` })]),
                  el("div", {
                    class: "muted small",
                    text: `${row.scored}/${row.students} 已录 · 待录 ${row.pending}`,
                  }),
                ]),
              ]);
            }),
          ),
        ]),
      ])
    : emptyBlock("还没有任教课程");
  return panel("我的课程进度", "成绩录入与出勤情况", body);
}

function todayEventItem(event) {
  return el("li", { class: "today-event" }, [
    el("span", { class: "event-time", text: event.all_day ? "全天" : fmt.time(event.start_at) }),
    el("div", { class: "today-event-copy" }, [
      el("strong", { text: event.title }),
      el("small", { text: event.location || "地点待定" }),
    ]),
  ]);
}

function renderDashboard(container, data) {
  const body = el("div", { class: "dash-body" });

  body.append(
    el("div", { class: "dash-meta" }, [
      el("span", { text: `学期 ${data.semester}` }),
      el("span", { text: `数据更新于 ${fmt.time(data.generated_at)}` }),
      el("span", { text: `统计窗口 近 ${data.days} 天` }),
    ]),
    el("div", { class: "kpi-grid" }, data.kpis.map(kpiCard)),
  );

  const chartPanels = [];
  if (hasSignal(data.attendance_trend)) {
    const dom = el("div", { class: "chart" });
    chartPanels.push({
      panel: panel("出勤趋势", `近 ${data.days} 天 · 出勤 + 迟到计为有效出勤`, dom),
      render: () => charts.attendance(dom, data.attendance_trend),
    });
  }
  if ((data.score_distribution?.sample || 0) > 0) {
    const dom = el("div", { class: "chart" });
    chartPanels.push({
      panel: panel(
        "成绩分布",
        `样本 ${data.score_distribution.sample} 份 · 平均 ${fmt.num(data.score_distribution.average, 1)} 分 · 及格率 ${data.score_distribution.pass_rate}%`,
        dom,
      ),
      render: () => charts.scores(dom, data.score_distribution),
    });
  }
  if ((data.fee_breakdown?.paid_count || 0) + (data.fee_breakdown?.unpaid_count || 0) > 0) {
    const dom = el("div", { class: "chart" });
    const fees = data.fee_breakdown;
    chartPanels.push({
      panel: panel(
        "费用收缴",
        `已缴 ${fmt.money(fees.paid_amount)} · 待缴 ${fmt.money(fees.unpaid_amount)} · 逾期 ${fees.overdue_count} 笔`,
        dom,
      ),
      render: () => charts.fees(dom, fees),
    });
  }
  if ((data.course_load || []).length) {
    const dom = el("div", { class: "chart" });
    chartPanels.push({
      panel: panel("课程饱和度", "在选人数 / 容量，越高越接近满员", dom),
      render: () => charts.courseLoad(dom, data.course_load),
    });
  }
  if ((data.class_comparison || []).length) {
    const dom = el("div", { class: "chart" });
    chartPanels.push({
      panel: panel("班级对比", "平均总分与出勤率", dom, el("span", { class: "pill", text: "按平均分排序" })),
      render: () => charts.classComparison(dom, data.class_comparison),
    });
  }
  if (chartPanels.length) {
    if (chartPanels.length % 2 === 1) {
      chartPanels[chartPanels.length - 1].panel.classList.add("wide");
    }
    body.append(el("div", { class: "charts-grid" }, chartPanels.map((item) => item.panel)));
  }

  const alerts = data.alerts || [];
  const recent = data.recent || [];
  const todayEvents = data.today_events || [];
  const quickPanels = [
    panel(
      "今日日程",
      todayEvents.length ? `共 ${todayEvents.length} 项` : "今天没有日程",
      todayEvents.length
        ? el("ul", { class: "today-events" }, todayEvents.map(todayEventItem))
        : emptyBlock("今天没有日程安排"),
      el("button", { class: "btn tiny", text: "查看日程", onclick: () => gotoView("calendar") }),
    ),
  ];
  if (data.pending_approvals) {
    quickPanels.push(
      panel(
        "待我审批",
        `有 ${data.pending_approvals} 条请假申请等待处理`,
        el("button", { class: "btn primary", text: "去审批", onclick: () => gotoView("leaves") }),
      ),
    );
  }
  body.append(el("div", { class: "dash-lower" }, quickPanels));
  body.append(
    el("div", { class: "dash-lower" }, [
      panel(
        "待办与预警",
        alerts.length ? `共 ${alerts.length} 项需要关注` : "暂无待办",
        alerts.length
          ? el("ul", { class: "alert-list" }, alerts.map(alertItem))
          : emptyBlock("一切正常，没有需要处理的异常"),
      ),
      panel(
        "最近动态",
        "选课、成绩与缴费的最新记录",
        recent.length
          ? el("ul", { class: "timeline" }, recent.map(recentItem))
          : emptyBlock("还没有动态"),
      ),
    ]),
  );

  if (data.student) body.append(studentPanel(data.student));
  if (data.teacher) body.append(teacherPanel(data.teacher));

  container.append(body);
  requestAnimationFrame(() => {
    for (const item of chartPanels) item.render();
  });
}

async function dashboardView(container) {
  charts.dispose();
  const body = el("div", { class: "dash-body" });
  const skeleton = el(
    "div",
    { class: "kpi-grid" },
    Array.from({ length: 5 }, () =>
      el("article", { class: "kpi skeleton" }, [
        el("div", { class: "sk sk-line short" }),
        el("div", { class: "sk sk-value" }),
        el("div", { class: "sk sk-line" }),
      ]),
    ),
  );

  let current = 0;
  const load = async () => {
    current += 1;
    const token = current;
    charts.dispose();
    body.innerHTML = "";
    body.append(skeleton);
    try {
      const data = await api.get(`/dashboard/overview?days=${state.days}`);
      if (token !== current) return;
      body.innerHTML = "";
      renderDashboard(body, data);
    } catch (error) {
      if (token !== current) return;
      body.innerHTML = "";
      body.append(
        el("div", { class: "panel error-panel" }, [
          el("h3", { text: "仪表盘加载失败" }),
          el("p", { class: "muted", text: error?.message || "未知错误" }),
          el("button", { class: "btn primary", text: "重试", onclick: load }),
        ]),
      );
      handleError(error);
    }
  };

  container.append(
    el("section", { class: "dash-hero" }, [
      el("div", { class: "dash-hero-copy" }, [
        el("span", { class: "eyebrow", text: "校园驾驶舱" }),
        el("h2", { text: `${greeting()}，${state.user.username}` }),
        el("p", { text: "关键指标、风险预警和个人待办都汇总在这里。" }),
      ]),
      el(
        "div",
        { class: "dash-hero-actions" },
        [
          el(
            "div",
            { class: "segmented", role: "group", "aria-label": "统计窗口" },
            [7, 30, 90].map((days) =>
              el("button", {
                class: state.days === days ? "active" : "",
                text: `${days} 天`,
                onclick: () => {
                  if (state.days === days) return;
                  state.days = days;
                  container.querySelectorAll(".segmented button").forEach((button) => {
                    button.classList.toggle("active", button.textContent === `${days} 天`);
                  });
                  load();
                },
              }),
            ),
          ),
          el("button", { class: "btn ghost", onclick: load }, [icon("refresh", 16), "刷新"]),
        ],
      ),
    ]),
    body,
  );
  await load();
}

function studentForm(row, reload) {
  const fields = [
    ...(row
      ? []
      : [{ name: "student_no", label: "学号", required: true, placeholder: "S031" }]),
    { name: "name", label: "姓名", required: true, value: row?.name },
    {
      name: "gender",
      label: "性别",
      type: "select",
      value: row?.gender || "unknown",
      options: Object.entries(GENDER_LABEL).map(([value, label]) => ({ value, label })),
    },
    {
      name: "class_id",
      label: "班级",
      type: "select",
      value: row?.class_id ?? "",
      options: withEmpty(classOptions(), "未分班"),
    },
    {
      name: "status",
      label: "学籍状态",
      type: "select",
      value: row?.status || "active",
      options: Object.entries(STUDENT_STATUS_LABEL).map(([value, label]) => ({ value, label })),
    },
    { name: "enroll_date", label: "入学日期", type: "date", value: row?.enroll_date },
    {
      name: "class_role",
      label: "班干部",
      type: "select",
      value: row?.class_role || "none",
      options: Object.entries(CLASS_ROLE_LABEL).map(([value, label]) => ({ value, label })),
    },
    {
      name: "residence_type",
      label: "住宿类型",
      type: "select",
      value: row?.residence_type || "boarding",
      options: Object.entries(RESIDENCE_LABEL).map(([value, label]) => ({ value, label })),
    },
    { name: "seat_no", label: "座位号", type: "number", value: row?.seat_no ?? "", as: "int" },
    { name: "seat_row", label: "座位行", type: "number", value: row?.seat_row ?? "", as: "int" },
    { name: "seat_col", label: "座位列", type: "number", value: row?.seat_col ?? "", as: "int" },
    { name: "guardian_name", label: "监护人", value: row?.guardian_name },
    { name: "guardian_phone", label: "监护人电话", value: row?.guardian_phone },
    { name: "address", label: "家庭住址", value: row?.address },
    { name: "id_card_masked", label: "身份证（脱敏）", value: row?.id_card_masked },
    { name: "phone", label: "手机号", value: row?.phone },
    { name: "birth_date", label: "出生日期", type: "date", value: row?.birth_date },
  ];
  openForm({
    title: row ? "编辑学生" : "新增学生",
    fields,
    onSubmit: async (values) => {
      values.class_id = values.class_id === null ? null : Number(values.class_id);
      if (row) {
        delete values.student_no;
        await api.patch(`/students/${row.id}`, values);
      } else {
        await api.post("/students", values);
      }
      toast("学生已保存");
      await reload();
      await loadLookups();
    },
  });
}

async function showStudentDetail(row) {
  try {
    const [detail, transcript, history] = await Promise.all([
      api.get(`/students/${row.id}`),
      api.get(`/students/${row.id}/transcript`),
      api.get(`/students/${row.id}/status-history`),
    ]);
    const profile = el("div", { class: "detail-grid" }, [
      ["姓名", detail.name],
      ["学号", detail.student_no],
      ["性别", GENDER_LABEL[detail.gender] || detail.gender],
      ["班级", detail.class_id ? mapName("class", detail.class_id) : "-"],
      ["学籍状态", STUDENT_STATUS_LABEL[detail.status] || detail.status],
      ["住宿", RESIDENCE_LABEL[detail.residence_type] || detail.residence_type],
      ["座位", detail.seat_no || "-"],
      ["班干部", CLASS_ROLE_LABEL[detail.class_role] || detail.class_role],
      ["手机", detail.phone || "-"],
      ["邮箱", detail.email || "-"],
      ["监护人", detail.guardian_name || "-"],
      ["监护人电话", detail.guardian_phone || "-"],
      ["入学日期", detail.enroll_date || "-"],
      ["身份证（脱敏）", detail.id_card_masked || "-"],
    ].map(([label, value]) =>
      el("div", { class: "detail-item" }, [
        el("span", { text: label }),
        el("strong", { text: String(value) }),
      ]),
    ));
    const transcriptTable = el("table", { class: "table compact" });
    transcriptTable.append(
      el("thead", {}, [
        el("tr", {}, [
          el("th", { text: "课程代码" }),
          el("th", { text: "课程" }),
          el("th", { text: "学分" }),
          el("th", { text: "学期" }),
          el("th", { text: "总评" }),
        ]),
      ]),
      el(
        "tbody",
        {},
        transcript.length
          ? transcript.map((item) =>
              el("tr", {}, [
                el("td", { text: item.course_code }),
                el("td", { text: item.course_name }),
                el("td", { text: String(item.credits) }),
                el("td", { text: item.semester }),
                el("td", { text: item.final_score ?? "-" }),
              ]),
            )
          : [el("tr", {}, [el("td", { colspan: 5, class: "muted", text: "暂无成绩" })])],
      ),
    );
    const statusList = el(
      "ul",
      { class: "timeline" },
      history.length
        ? history.map((item) =>
            el("li", { class: "timeline-item" }, [
              el("span", { class: "timeline-dot" }, [icon("clock", 14)]),
              el("div", { class: "timeline-copy" }, [
                el("p", {
                  text: `${STUDENT_STATUS_LABEL[item.from_status] || "-"} → ${
                    STUDENT_STATUS_LABEL[item.to_status] || item.to_status
                  }${item.reason ? " · " + item.reason : ""}`,
                }),
                el("time", { text: item.effective_date }),
              ]),
            ]),
          )
        : [el("li", { class: "muted", text: "暂无学籍异动" })],
    );
    const body = el("div", {}, [
      el("section", { class: "detail-section" }, [el("h4", { text: "基本信息" }), profile]),
      el("section", { class: "detail-section" }, [
        el("h4", { text: "成绩单" }),
        transcript.length ? el("div", { class: "table-wrap" }, [transcriptTable]) : emptyBlock("暂无成绩"),
      ]),
      el("section", { class: "detail-section" }, [el("h4", { text: "学籍异动" }), statusList]),
    ]);
    openDrawer({
      title: `学生详情 · ${detail.name}`,
      subtitle: `${detail.student_no} · ${detail.class_id ? mapName("class", detail.class_id) : "未分班"}`,
      body,
      width: "xl",
    });
  } catch (error) {
    handleError(error);
  }
}

async function studentsView(container) {
  await crudView(container, {
    title: "学生管理",
    search: "按学号或姓名搜索",
    exportResource: "students",
    import: { resource: "students", templatePath: "/transfer/template/students" },
    filters: [
      { name: "class_id", label: "班级", type: "select", options: classOptions() },
      {
        name: "is_active",
        label: "状态",
        type: "select",
        options: [
          { value: "true", label: "在册" },
          { value: "false", label: "停用" },
        ],
      },
    ],
    list: (p) => {
      const query = new URLSearchParams({ page: p.page, page_size: p.page_size });
      if (p.keyword) query.set("keyword", p.keyword);
      if (p.class_id) query.set("class_id", p.class_id);
      if (p.is_active) query.set("is_active", p.is_active);
      return api.get(`/students?${query.toString()}`);
    },
    columns: [
      { label: "学号", value: (row) => row.student_no },
      { label: "姓名", value: (row) => row.name },
      { label: "性别", value: (row) => GENDER_LABEL[row.gender] },
      { label: "班级", value: (row) => (row.class_id ? mapName("class", row.class_id) : "-") },
      { label: "学籍", value: (row) => STUDENT_STATUS_LABEL[row.status] || row.status },
      { label: "座位", value: (row) => row.seat_no || "-" },
      { label: "手机号", value: (row) => row.phone || "-" },
      { label: "状态", value: (row) => (row.is_active ? "在册" : "停用") },
    ],
    actions: (reload) => {
      const actions = [];
      if (can("student:manage")) {
        actions.push(
          el("button", {
            class: "btn primary",
            text: "新增学生",
            onclick: () => studentForm(null, reload),
          }),
        );
      }
      return actions;
    },
    rowActions: (row, reload) => {
      const actions = [
        { label: "详情", onClick: () => showStudentDetail(row) },
        { label: "异动", onClick: () => showStatusHistory(row) },
      ];
      if (can("student:manage")) {
        actions.push({ label: "编辑", onClick: () => studentForm(row, reload) });
        actions.push({
          label: "停用",
          danger: true,
          onClick: async () => {
            if (!window.confirm(`确定停用 ${row.name} 吗？`)) return;
            try {
              await api.del(`/students/${row.id}`);
              toast("已停用");
              await reload();
            } catch (error) {
              handleError(error);
            }
          },
        });
      }
      return actions;
    },
  });
}

function teacherForm(row, reload) {
  const fields = [
    ...(row ? [] : [{ name: "teacher_no", label: "工号", required: true, placeholder: "T006" }]),
    { name: "name", label: "姓名", required: true, value: row?.name },
    { name: "title", label: "职称", value: row?.title || "讲师" },
    { name: "department", label: "院系", value: row?.department },
    {
      name: "subject_id",
      label: "学科",
      type: "select",
      value: row?.subject_id ?? "",
      options: withEmpty(subjectOptions(), "暂不指定"),
      as: "int",
    },
    { name: "position", label: "职务", value: row?.position },
    { name: "hire_date", label: "入职日期", type: "date", value: row?.hire_date },
    {
      name: "employment_status",
      label: "在职状态",
      type: "select",
      value: row?.employment_status || "active",
      options: Object.entries(EMPLOYMENT_LABEL).map(([value, label]) => ({ value, label })),
    },
    {
      name: "staff_type",
      label: "编制类型",
      type: "select",
      value: row?.staff_type || "permanent",
      options: Object.entries(STAFF_TYPE_LABEL).map(([value, label]) => ({ value, label })),
    },
    {
      name: "education",
      label: "学历",
      type: "select",
      value: row?.education || "other",
      options: Object.entries(EDUCATION_LABEL).map(([value, label]) => ({ value, label })),
    },
    { name: "office", label: "办公室", value: row?.office },
    {
      name: "workload_limit",
      label: "周课时上限",
      type: "number",
      value: row?.workload_limit ?? 16,
      as: "int",
    },
    { name: "phone", label: "手机号", value: row?.phone },
  ];
  openForm({
    title: row ? "编辑教师" : "新增教师",
    fields,
    onSubmit: async (values) => {
      if (row) {
        delete values.teacher_no;
        await api.patch(`/teachers/${row.id}`, values);
      } else {
        await api.post("/teachers", values);
      }
      toast("教师已保存");
      await reload();
      await loadLookups();
    },
  });
}

async function teachersView(container) {
  await crudView(container, {
    title: "教师管理",
    search: "按工号或姓名搜索",
    exportResource: "teachers",
    list: (p) =>
      api.get(
        `/teachers?page=${p.page}&page_size=${p.page_size}&keyword=${encodeURIComponent(p.keyword)}`,
      ),
    columns: [
      { label: "工号", value: (row) => row.teacher_no },
      { label: "姓名", value: (row) => row.name },
      { label: "职称", value: (row) => row.title },
      { label: "学科", value: (row) => (row.subject_id ? mapName("subject", row.subject_id) : "-") },
      { label: "职务", value: (row) => row.position || "-" },
      { label: "院系", value: (row) => row.department || "-" },
      { label: "在职", value: (row) => EMPLOYMENT_LABEL[row.employment_status] || "-" },
      { label: "状态", value: (row) => (row.is_active ? "在职" : "停用") },
    ],
    actions: (reload) =>
      can("teacher:manage")
        ? [el("button", { class: "btn primary", text: "新增教师", onclick: () => teacherForm(null, reload) })]
        : [],
    rowActions: (row, reload) => {
      const actions = [{ label: "详情", onClick: () => showTeacherDetail(row) }];
      if (can("teacher:manage")) {
        actions.push({ label: "编辑", onClick: () => teacherForm(row, reload) });
        actions.push({
          label: "停用",
          danger: true,
          onClick: async () => {
            if (!window.confirm(`确定停用 ${row.name} 吗？`)) return;
            try {
              await api.del(`/teachers/${row.id}`);
              toast("已停用");
              await reload();
            } catch (error) {
              handleError(error);
            }
          },
        });
      }
      return actions;
    },
  });
}

async function showTeacherDetail(row) {
  try {
    const detail = await api.get(`/teachers/${row.id}`);
    const body = el("div", { class: "detail-grid" }, [
      ["工号", detail.teacher_no],
      ["姓名", detail.name],
      ["职称", detail.title || "-"],
      ["学科", detail.subject_id ? mapName("subject", detail.subject_id) : "-"],
      ["院系", detail.department || "-"],
      ["职务", detail.position || "-"],
      ["入职日期", detail.hire_date || "-"],
      ["在职状态", EMPLOYMENT_LABEL[detail.employment_status] || detail.employment_status],
      ["编制", STAFF_TYPE_LABEL[detail.staff_type] || detail.staff_type],
      ["学历", EDUCATION_LABEL[detail.education] || detail.education],
      ["办公室", detail.office || "-"],
      ["周课时上限", `${detail.workload_limit} 节`],
      ["手机", detail.phone || "-"],
      ["邮箱", detail.email || "-"],
    ].map(([label, value]) =>
      el("div", { class: "detail-item" }, [
        el("span", { text: label }),
        el("strong", { text: String(value) }),
      ]),
    ));
    openDrawer({
      title: `教师详情 · ${detail.name}`,
      subtitle: `${detail.teacher_no} · ${detail.department || "未分配院系"}`,
      body,
      width: "lg",
    });
  } catch (error) {
    handleError(error);
  }
}

function classForm(row, reload) {
  openForm({
    title: row ? "编辑班级" : "新增班级",
    fields: [
      { name: "name", label: "班级名称", required: true, value: row?.name },
      { name: "grade", label: "年级", value: row?.grade || "2024" },
      {
        name: "grade_year",
        label: "年级年份",
        type: "number",
        value: row?.grade_year ?? "",
        as: "int",
      },
      {
        name: "department_id",
        label: "所属院系",
        type: "select",
        value: row?.department_id ?? "",
        options: withEmpty(departmentOptions(), "暂不指定"),
        as: "int",
      },
      { name: "major", label: "专业", value: row?.major },
      { name: "classroom", label: "固定教室", value: row?.classroom },
      {
        name: "capacity",
        label: "班级容量",
        type: "number",
        value: row?.capacity ?? 50,
        as: "int",
      },
      {
        name: "status",
        label: "班级状态",
        type: "select",
        value: row?.status || "active",
        options: [
          { value: "active", label: "在读" },
          { value: "graduated", label: "毕业" },
          { value: "inactive", label: "停用" },
        ],
      },
      {
        name: "head_teacher_id",
        label: "班主任",
        type: "select",
        value: row?.head_teacher_id ?? "",
        options: withEmpty(teacherOptions(), "暂不指定"),
        as: "int",
      },
    ],
    onSubmit: async (values) => {
      if (row) {
        await api.patch(`/classes/${row.id}`, values);
      } else {
        await api.post("/classes", values);
      }
      toast("班级已保存");
      await reload();
      await loadLookups(true);
    },
  });
}

async function showClassDetail(row) {
  try {
    const students = await api.get(`/students?class_id=${row.id}&page_size=100`);
    const info = el("div", { class: "detail-grid" }, [
      ["班级", row.name],
      ["年级", row.grade || "-"],
      ["院系", row.department_id ? mapName("department", row.department_id) : "-"],
      ["专业", row.major || "-"],
      ["固定教室", row.classroom || "-"],
      ["容量", row.capacity],
      ["班主任", row.head_teacher_id ? mapName("teacher", row.head_teacher_id) : "-"],
      ["学生数", students.total],
    ].map(([label, value]) =>
      el("div", { class: "detail-item" }, [
        el("span", { text: label }),
        el("strong", { text: String(value) }),
      ]),
    ));
    const table = el("table", { class: "table compact" });
    table.append(
      el("thead", {}, [
        el("tr", {}, ["学号", "姓名", "性别", "状态", "座位"].map((label) => el("th", { text: label }))),
      ]),
      el(
        "tbody",
        {},
        students.items.length
          ? students.items.map((student) =>
              el("tr", {}, [
                el("td", { text: student.student_no }),
                el("td", { text: student.name }),
                el("td", { text: GENDER_LABEL[student.gender] || student.gender }),
                el("td", { text: STUDENT_STATUS_LABEL[student.status] || student.status }),
                el("td", { text: student.seat_no || "-" }),
              ]),
            )
          : [el("tr", {}, [el("td", { colspan: 5, class: "muted", text: "暂无学生" })])],
      ),
    );
    const body = el("div", {}, [
      el("section", { class: "detail-section" }, [el("h4", { text: "班级信息" }), info]),
      el("section", { class: "detail-section" }, [
        el("h4", { text: "班级花名册" }),
        students.items.length ? el("div", { class: "table-wrap" }, [table]) : emptyBlock("暂无学生"),
      ]),
    ]);
    openDrawer({
      title: `班级详情 · ${row.name}`,
      subtitle: `${students.total} 名学生 · ${row.major || "未设置专业"}`,
      body,
      width: "lg",
    });
  } catch (error) {
    handleError(error);
  }
}

async function classesView(container) {
  const rows = await api.get("/classes");
  const head = el("div", { class: "page-head" }, [el("h2", { text: "班级管理" })]);
  const reload = () => refreshView();
  if (can("class:manage")) {
    head.append(
      el("div", { class: "actions" }, [
        el("button", {
          class: "btn primary",
          text: "新增班级",
          onclick: () => classForm(null, reload),
        }),
      ]),
    );
  }
  const card = el("div", { class: "card" });
  renderTable(
    card,
    [
      { label: "班级", value: (row) => row.name },
      { label: "年级", value: (row) => row.grade },
      {
        label: "院系",
        value: (row) => (row.department_id ? mapName("department", row.department_id) : "-"),
      },
      { label: "专业", value: (row) => row.major || "-" },
      { label: "教室", value: (row) => row.classroom || "-" },
      { label: "容量", value: (row) => row.capacity },
      {
        label: "班主任",
        value: (row) => (row.head_teacher_id ? mapName("teacher", row.head_teacher_id) : "-"),
      },
    ],
    rows,
    (row) => {
      const actions = [{ label: "详情", onClick: () => showClassDetail(row) }];
      if (can("class:seat:read")) {
        actions.push({ label: "座位", onClick: () => showSeats(row) });
      }
      if (can("class:manage")) {
        actions.push({ label: "编辑", onClick: () => classForm(row, reload) });
        actions.push({
          label: "删除",
          danger: true,
          onClick: async () => {
            if (!window.confirm(`确定删除 ${row.name} 吗？`)) return;
            try {
              await api.del(`/classes/${row.id}`);
              toast("已删除");
              await refreshView();
            } catch (error) {
              handleError(error);
            }
          },
        });
      }
      return actions.length ? actions : null;
    },
  );
  container.append(head, card);
}

function courseForm(row, reload) {
  const scheme = row?.grade_scheme || { usual: 0.4, midterm: 0.0, exam: 0.6 };
  const fields = [
    ...(row ? [] : [{ name: "code", label: "课程代码", required: true, placeholder: "CS401" }]),
    { name: "name", label: "课程名称", required: true, value: row?.name },
    { name: "credits", label: "学分", type: "number", step: "0.5", value: row?.credits ?? 3, as: "number" },
    { name: "hours", label: "学时", type: "number", value: row?.hours ?? 48, as: "int" },
    {
      name: "subject_id",
      label: "学科",
      type: "select",
      value: row?.subject_id ?? "",
      options: withEmpty(subjectOptions(), "暂不指定"),
      as: "int",
    },
    {
      name: "department_id",
      label: "开课院系",
      type: "select",
      value: row?.department_id ?? "",
      options: withEmpty(departmentOptions(), "暂不指定"),
      as: "int",
    },
    {
      name: "semester_id",
      label: "学期",
      type: "select",
      value: row?.semester_id ?? "",
      options: withEmpty(semesterOptions(), "暂不指定"),
      as: "int",
    },
    {
      name: "course_type",
      label: "课程类型",
      type: "select",
      value: row?.course_type || "required",
      options: Object.entries(COURSE_TYPE_LABEL).map(([value, label]) => ({ value, label })),
    },
    {
      name: "assessment_type",
      label: "考核方式",
      type: "select",
      value: row?.assessment_type || "exam",
      options: Object.entries(ASSESSMENT_LABEL).map(([value, label]) => ({ value, label })),
    },
    {
      name: "teacher_id",
      label: "主讲教师",
      type: "select",
      value: row?.teacher_id ?? "",
      options: withEmpty(teacherOptions(), "暂不指定"),
      as: "int",
    },
    { name: "capacity", label: "容量", type: "number", value: row?.capacity ?? 50, as: "int" },
    { name: "grade_year", label: "开课年级", type: "number", value: row?.grade_year ?? "", as: "int" },
    { name: "textbook", label: "教材", value: row?.textbook },
    {
      name: "usual_weight",
      label: "平时权重（%）",
      type: "number",
      value: Math.round((scheme.usual || 0) * 100),
      as: "number",
    },
    {
      name: "midterm_weight",
      label: "期中权重（%）",
      type: "number",
      value: Math.round((scheme.midterm || 0) * 100),
      as: "number",
    },
    {
      name: "exam_weight",
      label: "期末权重（%）",
      type: "number",
      value: Math.round((scheme.exam || 0) * 100),
      as: "number",
    },
    { name: "description", label: "简介", value: row?.description },
  ];
  openForm({
    title: row ? "编辑课程" : "新增课程",
    fields,
    onSubmit: async (values) => {
      values.grade_scheme = {
        usual: (values.usual_weight || 0) / 100,
        midterm: (values.midterm_weight || 0) / 100,
        exam: (values.exam_weight || 0) / 100,
      };
      delete values.usual_weight;
      delete values.midterm_weight;
      delete values.exam_weight;
      if (row) {
        delete values.code;
        await api.patch(`/courses/${row.id}`, values);
      } else {
        await api.post("/courses", values);
      }
      toast("课程已保存");
      await reload();
      await loadLookups();
    },
  });
}

async function showRoster(course) {
  const rows = await api.get(`/courses/${course.id}/roster`);
  const overlay = el("div", { class: "overlay" });
  const modal = el("div", { class: "modal" }, [el("h3", { text: `选课名单 · ${course.name}` })]);
  const body = el("div");
  renderTable(
    body,
    [
      { label: "学号", value: (row) => row.student_no },
      { label: "姓名", value: (row) => row.student_name },
      { label: "状态", value: (row) => (row.status === "enrolled" ? "已选" : "已退") },
    ],
    rows,
    null,
  );
  modal.append(body);
  modal.append(
    el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "关闭", onclick: () => overlay.remove() }),
    ]),
  );
  overlay.append(modal);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) overlay.remove();
  });
  document.body.append(overlay);
}

async function coursesView(container) {
  await crudView(container, {
    title: "课程管理",
    search: "按课程代码或名称搜索",
    exportResource: "courses",
    filters: [
      {
        name: "semester",
        label: "学期",
        type: "select",
        options: state.lookups.semesters.map((item) => ({ value: item.name, label: item.name })),
      },
      { name: "teacher_id", label: "教师", type: "select", options: teacherOptions() },
    ],
    list: (p) => {
      const query = new URLSearchParams({ page: p.page, page_size: p.page_size });
      if (p.keyword) query.set("keyword", p.keyword);
      if (p.semester) query.set("semester", p.semester);
      if (p.teacher_id) query.set("teacher_id", p.teacher_id);
      return api.get(`/courses?${query.toString()}`);
    },
    columns: [
      { label: "代码", value: (row) => row.code },
      { label: "课程", value: (row) => row.name },
      {
        label: "学科",
        value: (row) => (row.subject_id ? mapName("subject", row.subject_id) : "-"),
      },
      { label: "类型", value: (row) => COURSE_TYPE_LABEL[row.course_type] || row.course_type },
      { label: "学分", value: (row) => row.credits },
      { label: "学时", value: (row) => row.hours },
      { label: "学期", value: (row) => row.semester },
      {
        label: "任课教师",
        value: (row) => (row.teacher_id ? mapName("teacher", row.teacher_id) : "-"),
      },
      { label: "容量", value: (row) => row.capacity },
    ],
    actions: (reload) => {
      if (!can("course:manage")) return [];
      return [
        el("button", {
          class: "btn primary",
          text: "新增课程",
          onclick: () => courseForm(null, reload),
        }),
      ];
    },
    rowActions: (row, reload) => {
      const actions = [];
      if (can("score:write") || can("course:manage")) {
        actions.push({ label: "名单", onClick: () => showRoster(row) });
      }
      if (can("score:publish")) {
        actions.push({
          label: "发布成绩",
          onClick: async () => {
            if (!window.confirm(`确定发布《${row.name}》的成绩吗？`)) return;
            try {
              const result = await api.post(`/courses/${row.id}/publish-scores`);
              toast(result.message || "成绩已发布");
            } catch (error) {
              handleError(error);
            }
          },
        });
      }
      if (can("course:manage")) {
        actions.push({ label: "编辑", onClick: () => courseForm(row, reload) });
        actions.push({
          label: "删除",
          danger: true,
          onClick: async () => {
            if (!window.confirm(`确定删除课程 ${row.name} 吗？`)) return;
            try {
              await api.del(`/courses/${row.id}`);
              toast("已删除");
              await reload();
              await loadLookups();
            } catch (error) {
              handleError(error);
            }
          },
        });
      }
      return actions.length ? actions : null;
    },
  });
}

function enrollForm(reload) {
  const fields = [
    {
      name: "course_id",
      label: "课程",
      type: "select",
      required: true,
      options: withEmpty(courseOptions(), "请选择课程"),
      as: "int",
    },
  ];
  if (can("enrollment:manage")) {
    fields.unshift({
      name: "student_id",
      label: "学生",
      type: "select",
      options: withEmpty(studentOptions(), "请选择学生"),
      as: "int",
    });
  }
  openForm({
    title: "选课",
    fields,
    submitLabel: "确认选课",
    onSubmit: async (values) => {
      if (can("enrollment:manage")) {
        await api.post("/enrollments", values);
      } else {
        await api.post("/enrollments", { course_id: values.course_id });
      }
      toast("选课成功");
      await reload();
    },
  });
}

async function enrollmentsView(container) {
  await crudView(container, {
    title: "选课管理",
    exportResource: "enrollments",
    list: (p) => api.get(`/enrollments?page=${p.page}&page_size=${p.page_size}`),
    columns: [
      { label: "学号", value: (row) => row.student_no },
      { label: "学生", value: (row) => row.student_name },
      { label: "课程", value: (row) => `${row.course_code} ${row.course_name}` },
      { label: "状态", value: (row) => (row.status === "enrolled" ? "已选" : "已退") },
      { label: "选课时间", value: (row) => new Date(row.created_at).toLocaleString() },
    ],
    actions: (reload) => [
      el("button", { class: "btn primary", text: "选课", onclick: () => enrollForm(reload) }),
    ],
    rowActions: (row, reload) => [
      {
        label: "退课",
        danger: true,
        onClick: async () => {
          if (!window.confirm("确定退选该课程吗？")) return;
          try {
            await api.del(`/enrollments/${row.id}`);
            toast("退课成功");
            await reload();
          } catch (error) {
            handleError(error);
          }
        },
      },
    ],
  });
}

function scoreForm(row, reload) {
  if (row) {
    openForm({
      title: `成绩 · ${row.student_name} · ${row.course_name}`,
      fields: [
        { name: "usual_score", label: "平时分", type: "number", step: "0.5", value: row.usual_score ?? "", as: "number" },
        { name: "midterm_score", label: "期中分", type: "number", step: "0.5", value: row.midterm_score ?? "", as: "number" },
        { name: "exam_score", label: "考试分", type: "number", step: "0.5", value: row.exam_score ?? "", as: "number" },
      ],
      onSubmit: async (values) => {
        await api.patch(`/scores/${row.id}`, values);
        toast("成绩已更新");
        await reload();
      },
    });
    return;
  }
  openForm({
    title: "录入成绩",
    fields: [
      {
        name: "student_id",
        label: "学生",
        type: "select",
        options: withEmpty(studentOptions(), "请选择学生"),
        as: "int",
      },
      {
        name: "course_id",
        label: "课程",
        type: "select",
        options: withEmpty(courseOptions(), "请选择课程"),
        as: "int",
      },
      { name: "usual_score", label: "平时分", type: "number", step: "0.5", as: "number" },
      { name: "midterm_score", label: "期中分", type: "number", step: "0.5", as: "number" },
      { name: "exam_score", label: "考试分", type: "number", step: "0.5", as: "number" },
    ],
    submitLabel: "保存成绩",
    onSubmit: async (values) => {
      await api.post("/scores", { items: [values] });
      toast("成绩已保存");
      await reload();
    },
  });
}

async function scoresView(container) {
  const staff = can("score:write");
  await crudView(container, {
    title: "成绩管理",
    exportResource: "scores",
    filters: [
      { name: "course_id", label: "课程", type: "select", options: courseOptions() },
    ],
    list: (p) => {
      const query = new URLSearchParams({ page: p.page, page_size: p.page_size });
      if (p.course_id) query.set("course_id", p.course_id);
      return api.get(`/scores?${query.toString()}`);
    },
    columns: [
      { label: "学号", value: (row) => row.student_no },
      { label: "学生", value: (row) => row.student_name },
      { label: "课程", value: (row) => `${row.course_code} ${row.course_name}` },
      { label: "平时分", value: (row) => row.usual_score ?? "-" },
      { label: "期中分", value: (row) => row.midterm_score ?? "-" },
      { label: "考试分", value: (row) => row.exam_score ?? "-" },
      { label: "总评", value: (row) => row.final_score ?? "-" },
    ],
    actions: (reload) => {
      return staff
        ? [el("button", { class: "btn primary", text: "录入成绩", onclick: () => scoreForm(null, reload) })]
        : [];
    },
    rowActions: (row, reload) =>
      staff ? [{ label: "修改", onClick: () => scoreForm(row, reload) }] : null,
  });
}

function attendanceForm(reload) {
  const today = new Date().toISOString().slice(0, 10);
  openForm({
    title: "登记考勤",
    fields: [
      {
        name: "course_id",
        label: "课程",
        type: "select",
        options: withEmpty(courseOptions(), "请选择课程"),
        as: "int",
      },
      {
        name: "student_id",
        label: "学生",
        type: "select",
        options: withEmpty(studentOptions(), "请选择学生"),
        as: "int",
      },
      { name: "date", label: "日期", type: "date", value: today },
      { name: "period_no", label: "节次", type: "number", value: 1, as: "int" },
      {
        name: "status",
        label: "状态",
        type: "select",
        value: "present",
        options: Object.entries(ATTENDANCE_LABEL).map(([value, label]) => ({ value, label })),
      },
      { name: "remark", label: "备注" },
    ],
    submitLabel: "提交",
    onSubmit: async (values) => {
      await api.post("/attendance/bulk", { items: [values] });
      toast("考勤已登记");
      await reload();
    },
  });
}

async function attendanceView(container) {
  const staff = can("attendance:write");
  await crudView(container, {
    title: "考勤管理",
    exportResource: "attendance",
    filters: [
      { name: "course_id", label: "课程", type: "select", options: courseOptions() },
      { name: "day", label: "日期", type: "date" },
    ],
    list: (p) => {
      const query = new URLSearchParams({ page: p.page, page_size: p.page_size });
      if (p.course_id) query.set("course_id", p.course_id);
      if (p.day) query.set("day", p.day);
      return api.get(`/attendance?${query.toString()}`);
    },
    columns: [
      { label: "日期", value: (row) => row.date },
      { label: "节次", value: (row) => row.period_no },
      { label: "学号", value: (row) => row.student_no },
      { label: "学生", value: (row) => row.student_name },
      { label: "课程", value: (row) => row.course_name },
      { label: "状态", value: (row) => ATTENDANCE_LABEL[row.status] },
      { label: "备注", value: (row) => row.remark || "-" },
    ],
    actions: (reload) => {
      const actions = staff
        ? [
            el("button", {
              class: "btn primary",
              text: "登记考勤",
              onclick: () => attendanceForm(reload),
            }),
          ]
        : [];
      return actions;
    },
  });
}

function scheduleForm(reload) {
  openForm({
    title: "新增排课",
    fields: [
      {
        name: "course_id",
        label: "课程",
        type: "select",
        options: withEmpty(courseOptions(), "请选择课程"),
        as: "int",
      },
      {
        name: "class_id",
        label: "行政班",
        type: "select",
        options: withEmpty(classOptions(), "暂不指定"),
        as: "int",
      },
      { name: "weekday", label: "星期(1-7)", type: "number", value: 1, as: "int" },
      { name: "start_period", label: "起始节次", type: "number", value: 1, as: "int" },
      { name: "end_period", label: "结束节次", type: "number", value: 2, as: "int" },
      { name: "classroom", label: "教室", value: "A101" },
      { name: "weeks", label: "周次", value: "1-16" },
    ],
    onSubmit: async (values) => {
      await api.post("/schedules", values);
      toast("排课成功");
      await reload();
    },
  });
}

async function showScheduleChanges() {
  const rows = await api.get("/schedule-changes?status=pending&page_size=100");
  const overlay = el("div", { class: "overlay" });
  const modal = el("div", { class: "modal" }, [el("h3", { text: "待审批调课" })]);
  const body = el("div");
  renderTable(
    body,
    [
      { label: "课程", value: (row) => row.course_name },
      { label: "类型", value: (row) => (row.kind === "cancel" ? "停课" : "调课") },
      { label: "日期", value: (row) => row.change_date },
      { label: "原因", value: (row) => row.reason || "-" },
    ],
    rows.items,
    (row) => [
      {
        label: "通过",
        onClick: async () => {
          try {
            await api.post(`/schedule-changes/${row.id}/approve`, { remark: "同意" });
            toast("已通过");
            overlay.remove();
            await showScheduleChanges();
          } catch (error) {
            handleError(error);
          }
        },
      },
      {
        label: "驳回",
        danger: true,
        onClick: async () => {
          try {
            await api.post(`/schedule-changes/${row.id}/reject`, { remark: "" });
            toast("已驳回");
            overlay.remove();
            await showScheduleChanges();
          } catch (error) {
            handleError(error);
          }
        },
      },
    ],
  );
  modal.append(body);
  modal.append(
    el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "关闭", onclick: () => overlay.remove() }),
    ]),
  );
  overlay.append(modal);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) overlay.remove();
  });
  document.body.append(overlay);
}

async function schedulesView(container) {
  const staff = can("schedule:manage");
  await crudView(container, {
    title: "课表",
    list: (p) => api.get(`/schedules?page=${p.page}&page_size=${p.page_size}`),
    columns: [
      { label: "星期", value: (row) => WEEKDAY_LABEL[row.weekday] || row.weekday },
      { label: "节次", value: (row) => `${row.start_period}-${row.end_period}` },
      { label: "课程", value: (row) => `${row.course_code} ${row.course_name}` },
      {
        label: "班级",
        value: (row) => (row.class_id ? mapName("class", row.class_id) : "-"),
      },
      { label: "教室", value: (row) => row.classroom || "-" },
      { label: "状态", value: (row) => SCHEDULE_STATUS_LABEL[row.status] || row.status },
    ],
    actions: (reload) => {
      const actions = [];
      if (staff) {
        actions.push(
          el("button", {
            class: "btn primary",
            text: "新增排课",
            onclick: () => scheduleForm(reload),
          }),
        );
      }
      if (can("schedule:change") && state.user.role === "admin") {
        actions.push(
          el("button", { class: "btn", text: "调课审批", onclick: showScheduleChanges }),
        );
      }
      return actions;
    },
    rowActions: (row, reload) => {
      const actions = [];
      if (can("schedule:change") && row.status !== "cancelled") {
        actions.push({
          label: "停课",
          danger: true,
          onClick: async () => {
            const reason = window.prompt("停课原因", "");
            if (reason === null) return;
            try {
              await api.post("/schedule-changes", {
                schedule_id: row.id,
                change_date: new Date().toISOString().slice(0, 10),
                kind: "cancel",
                reason,
              });
              toast("已提交停课申请");
            } catch (error) {
              handleError(error);
            }
          },
        });
      }
      if (staff) {
        actions.push({
          label: "删除",
          danger: true,
          onClick: async () => {
            if (!window.confirm("确定删除该排课吗？")) return;
            try {
              await api.del(`/schedules/${row.id}`);
              toast("已删除");
              await reload();
            } catch (error) {
              handleError(error);
            }
          },
        });
      }
      return actions.length ? actions : null;
    },
  });
}

async function dormsView(container) {
  const admin = can("dorm:manage");
  await crudView(container, {
    title: "宿舍管理",
    list: (p) => api.get(`/dorms?page=${p.page}&page_size=${p.page_size}`),
    columns: [
      { label: "楼栋", value: (row) => row.building },
      { label: "房间", value: (row) => row.room_no },
      { label: "性别", value: (row) => GENDER_LABEL[row.gender] },
      { label: "容量", value: (row) => row.capacity },
      { label: "已住", value: (row) => row.occupied },
    ],
    actions: (reload) =>
      admin
        ? [
            el("button", {
              class: "btn primary",
              text: "新增房间",
              onclick: () =>
                openForm({
                  title: "新增宿舍",
                  fields: [
                    { name: "building", label: "楼栋", required: true, value: "C" },
                    { name: "room_no", label: "房间号", required: true, value: "101" },
                    { name: "capacity", label: "容量", type: "number", value: 4, as: "int" },
                    {
                      name: "gender",
                      label: "性别",
                      type: "select",
                      value: "unknown",
                      options: Object.entries(GENDER_LABEL).map(([value, label]) => ({ value, label })),
                    },
                  ],
                  onSubmit: async (values) => {
                    await api.post("/dorms", values);
                    toast("房间已创建");
                    await reload();
                  },
                }),
            }),
            el("button", {
              class: "btn",
              text: "分配床位",
              onclick: () => assignForm(reload),
            }),
          ]
        : [],
    rowActions: (row, reload) =>
      admin
        ? [
            { label: "床位", onClick: () => showAssignments(row) },
            {
              label: "删除",
              danger: true,
              onClick: async () => {
                if (!window.confirm(`确定删除 ${row.building}-${row.room_no} 吗？`)) return;
                try {
                  await api.del(`/dorms/${row.id}`);
                  toast("已删除");
                  await reload();
                } catch (error) {
                  handleError(error);
                }
              },
            },
          ]
        : [{ label: "床位", onClick: () => showAssignments(row) }],
  });
}

async function assignForm(reload) {
  const dorms = await api.get("/dorms?page_size=100");
  openForm({
    title: "分配床位",
    fields: [
      {
        name: "student_id",
        label: "学生",
        type: "select",
        options: withEmpty(studentOptions(), "请选择学生"),
        as: "int",
      },
      {
        name: "dorm_id",
        label: "宿舍",
        type: "select",
        options: withEmpty(
          dorms.items.map((dorm) => ({
            value: dorm.id,
            label: `${dorm.building}-${dorm.room_no}（${dorm.occupied}/${dorm.capacity}）`,
          })),
          "请选择宿舍",
        ),
        as: "int",
      },
      { name: "bed_no", label: "床位号", type: "number", value: 1, as: "int" },
    ],
    onSubmit: async (values) => {
      await api.post("/dorms/assignments", values);
      toast("分配成功");
      await reload();
    },
  });
}

async function showAssignments(dorm) {
  const data = await api.get(`/dorms/assignments?dorm_id=${dorm.id}&page_size=100`);
  const overlay = el("div", { class: "overlay" });
  const modal = el("div", { class: "modal" }, [
    el("h3", { text: `${dorm.building}-${dorm.room_no} 床位` }),
  ]);
  const body = el("div");
  renderTable(
    body,
    [
      { label: "床位", value: (row) => row.bed_no },
      { label: "学号", value: (row) => row.student_no },
      { label: "姓名", value: (row) => row.student_name },
    ],
    data.items,
    null,
  );
  modal.append(body);
  modal.append(
    el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "关闭", onclick: () => overlay.remove() }),
    ]),
  );
  overlay.append(modal);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) overlay.remove();
  });
  document.body.append(overlay);
}

async function feesView(container) {
  const admin = can("fee:manage");
  await crudView(container, {
    title: "缴费管理",
    exportResource: "fees",
    filters: [
      {
        name: "status",
        label: "缴费状态",
        type: "select",
        options: Object.entries(FEE_LABEL).map(([value, label]) => ({ value, label })),
      },
    ],
    list: (p) => {
      const query = new URLSearchParams({ page: p.page, page_size: p.page_size });
      if (p.status) query.set("status", p.status);
      return api.get(`/fees?${query.toString()}`);
    },
    columns: [
      { label: "学号", value: (row) => row.student_no },
      { label: "学生", value: (row) => row.student_name },
      { label: "项目", value: (row) => row.item },
      { label: "金额", value: (row) => `¥${row.amount}` },
      { label: "截止", value: (row) => row.due_date },
      { label: "状态", value: (row) => FEE_LABEL[row.status] },
    ],
    actions: (reload) =>
      admin
        ? [
            el("button", {
              class: "btn primary",
              text: "新增费用",
              onclick: () =>
                openForm({
                  title: "新增费用",
                  fields: [
                    {
                      name: "student_id",
                      label: "学生",
                      type: "select",
                      options: withEmpty(studentOptions(), "请选择学生"),
                      as: "int",
                    },
                    { name: "item", label: "项目", required: true, value: "住宿费" },
                    { name: "amount", label: "金额", type: "number", required: true, value: 1200, as: "number" },
                    { name: "due_date", label: "截止日期", type: "date", required: true },
                  ],
                  onSubmit: async (values) => {
                    await api.post("/fees", values);
                    toast("费用已创建");
                    await reload();
                  },
                }),
            }),
          ]
        : [],
    rowActions: (row, reload) => {
      if (row.status !== "unpaid" || !can("fee:pay")) return [];
      return [
        {
          label: "缴费",
          onClick: async () => {
            if (!window.confirm(`确认支付 ${row.item} ¥${row.amount} 吗？`)) return;
            try {
              await api.post(`/fees/${row.id}/pay`);
              toast("缴费成功");
              await reload();
            } catch (error) {
              handleError(error);
            }
          },
        },
      ];
    },
  });
}

function leaveForm(reload) {
  const today = new Date().toISOString().slice(0, 10);
  openForm({
    title: "申请请假",
    fields: [
      {
        name: "leave_type",
        label: "类型",
        type: "select",
        value: "personal",
        options: Object.entries(LEAVE_TYPE_LABEL).map(([value, label]) => ({ value, label })),
      },
      {
        name: "start_at",
        label: "开始时间",
        type: "datetime-local",
        required: true,
        value: `${today}T08:00`,
      },
      {
        name: "end_at",
        label: "结束时间",
        type: "datetime-local",
        required: true,
        value: `${today}T18:00`,
      },
      { name: "reason", label: "事由", required: true },
    ],
    submitLabel: "提交申请",
    onSubmit: async (values) => {
      await api.post("/leaves", values);
      toast("请假已提交");
      await reload();
    },
  });
}

async function leavesView(container) {
  const canApprove = can("leave:approve");
  const head = el("div", { class: "page-head" }, [
    el("div", {}, [
      el("h2", { text: "请假" }),
      el("p", {
        class: "muted",
        text: "学生请假：班主任 → 学工处；教师请假：教务主任 → 管理员。",
      }),
    ]),
  ]);
  if (can("leave:apply")) {
    head.append(
      el("div", { class: "actions" }, [
        el("button", {
          class: "btn primary",
          text: "申请请假",
          onclick: () => leaveForm(() => refreshView()),
        }),
      ]),
    );
  }
  const tabs = [["mine", "我的申请"]];
  if (canApprove) tabs.push(["pending", "待我审批"]);
  let mode = "mine";
  const bar = el("div", { class: "segmented" });
  const body = el("div");
  const buttons = [];
  const render = async () => {
    body.innerHTML = "";
    const card = el("div", { class: "card" });
    let rows = [];
    if (mode === "pending") {
      rows = await api.get("/leaves/pending");
    } else {
      const data = await api.get("/leaves?mine=true&page_size=100");
      rows = data.items;
    }
    renderTable(
      card,
      [
        { label: "申请人", value: (row) => row.student_name || row.teacher_name || "-" },
        { label: "类型", value: (row) => LEAVE_TYPE_LABEL[row.leave_type] || row.leave_type },
        {
          label: "起止",
          value: (row) => `${fmt.dateTime(row.start_at)} ~ ${fmt.dateTime(row.end_at)}`,
        },
        { label: "天数", value: (row) => row.days },
        { label: "状态", value: (row) => LEAVE_STATUS_LABEL[row.status] || row.status },
        { label: "审批级", value: (row) => `${row.current_step}/${row.required_steps}` },
      ],
      rows,
      (row) => {
        if (mode === "pending") {
          return [
            {
              label: "通过",
              onClick: async () => {
                const remark = window.prompt("审批意见", "同意");
                if (remark === null) return;
                try {
                  await api.post(`/leaves/${row.id}/approve`, { remark });
                  toast("已通过");
                  await render();
                } catch (error) {
                  handleError(error);
                }
              },
            },
            {
              label: "驳回",
              danger: true,
              onClick: async () => {
                const remark = window.prompt("驳回原因", "");
                if (remark === null) return;
                try {
                  await api.post(`/leaves/${row.id}/reject`, { remark });
                  toast("已驳回");
                  await render();
                } catch (error) {
                  handleError(error);
                }
              },
            },
          ];
        }
        if (row.status !== "pending") return null;
        return [
          {
            label: "撤销",
            danger: true,
            onClick: async () => {
              if (!window.confirm("确定撤销该请假申请吗？")) return;
              try {
                await api.post(`/leaves/${row.id}/cancel`);
                toast("已撤销");
                await render();
              } catch (error) {
                handleError(error);
              }
            },
          },
        ];
      },
    );
    body.append(card);
  };
  for (const [key, label] of tabs) {
    const button = el("button", { class: key === mode ? "active" : "", text: label });
    button.addEventListener("click", async () => {
      mode = key;
      for (const item of buttons) item.classList.toggle("active", item === button);
      await render();
    });
    buttons.push(button);
    bar.append(button);
  }
  container.append(head, bar, body);
  await render();
}

function noticeForm(row, reload) {
  openForm({
    title: row ? "编辑通知" : "发布通知",
    fields: [
      { name: "title", label: "标题", required: true, value: row?.title },
      { name: "content", label: "内容", value: row?.content },
      {
        name: "audience",
        label: "受众",
        type: "select",
        value: row?.audience || "all",
        options: Object.entries(AUDIENCE_LABEL).map(([value, label]) => ({ value, label })),
      },
      {
        name: "class_id",
        label: "班级（仅班级通知）",
        type: "select",
        value: row?.class_id ?? "",
        options: withEmpty(classOptions(), "不指定"),
        as: "int",
      },
      {
        name: "group_id",
        label: "群组（仅群组通知）",
        type: "select",
        value: row?.group_id ?? "",
        options: withEmpty(groupOptions(), "不指定"),
        as: "int",
      },
    ],
    submitLabel: row ? "保存" : "发布",
    onSubmit: async (values) => {
      if (values.audience !== "class") values.class_id = null;
      if (values.audience !== "group") values.group_id = null;
      if (row) {
        await api.patch(`/notices/${row.id}`, values);
      } else {
        await api.post("/notices", values);
      }
      toast("通知已保存");
      await reload();
    },
  });
}

async function noticesView(container) {
  await crudView(container, {
    title: "通知",
    subtitle: "全校、班级与个人通知。",
    list: (p) => api.get(`/notices?page=${p.page}&page_size=${p.page_size}`),
    columns: [
      { label: "标题", value: (row) => row.title },
      { label: "受众", value: (row) => AUDIENCE_LABEL[row.audience] || row.audience },
      { label: "班级", value: (row) => (row.class_id ? mapName("class", row.class_id) : "-") },
      { label: "群组", value: (row) => (row.group_id ? mapName("group", row.group_id) : "-") },
      { label: "发布时间", value: (row) => fmt.dateTime(row.published_at) },
      { label: "置顶", value: (row) => (row.is_pinned ? "是" : "-") },
    ],
    actions: (reload) =>
      can("notice:manage")
        ? [
            el("button", {
              class: "btn primary",
              text: "发布通知",
              onclick: () => noticeForm(null, reload),
            }),
          ]
        : [],
    rowActions: (row, reload) =>
      can("notice:manage")
        ? [
            { label: "编辑", onClick: () => noticeForm(row, reload) },
            {
              label: "删除",
              danger: true,
              onClick: async () => {
                if (!window.confirm(`确定删除通知「${row.title}」吗？`)) return;
                try {
                  await api.del(`/notices/${row.id}`);
                  toast("已删除");
                  await reload();
                } catch (error) {
                  handleError(error);
                }
              },
            },
          ]
        : null,
  });
}

async function showSeats(schoolClass) {
  const map = await api.get(`/classes/${schoolClass.id}/seats`);
  const overlay = el("div", { class: "overlay" });
  const modal = el("div", { class: "modal seat-modal" }, [
    el("h3", { text: `座位表 · ${map.class_name}` }),
  ]);
  const grid = el("div", { class: "seat-grid" });
  grid.style.gridTemplateColumns = `repeat(${map.cols}, 64px)`;
  const byPosition = new Map(map.seats.map((seat) => [`${seat.seat_row}-${seat.seat_col}`, seat]));
  for (let row = 1; row <= map.rows; row += 1) {
    for (let col = 1; col <= map.cols; col += 1) {
      const seat = byPosition.get(`${row}-${col}`);
      grid.append(
        el(
          "div",
          {
            class: `seat${seat ? " occupied" : ""}`,
            title: seat ? `${seat.student_no} ${seat.student_name}` : "空位",
          },
          [
            el("span", { text: seat ? seat.student_name.slice(-2) : "" }),
            el("small", { text: seat ? String(seat.seat_no) : "" }),
          ],
        ),
      );
    }
  }
  modal.append(grid);
  if (can("class:seat:manage")) {
    modal.append(
      el("div", { class: "toolbar" }, [
        el("button", {
          class: "btn primary",
          text: "按顺序排座",
          onclick: async () => {
            try {
              const students = await api.get(
                `/students?class_id=${schoolClass.id}&page_size=100`,
              );
              const items = students.items.map((student, index) => ({
                student_id: student.id,
                seat_no: index + 1,
                seat_row: Math.floor(index / 8) + 1,
                seat_col: (index % 8) + 1,
              }));
              await api.put(`/classes/${schoolClass.id}/seats`, { items });
              toast("座位已调整");
              overlay.remove();
              await showSeats(schoolClass);
            } catch (error) {
              handleError(error);
            }
          },
        }),
      ]),
    );
  }
  modal.append(
    el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "关闭", onclick: () => overlay.remove() }),
    ]),
  );
  overlay.append(modal);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) overlay.remove();
  });
  document.body.append(overlay);
}

function statusForm(student) {
  openForm({
    title: `变更学籍 · ${student.name}`,
    fields: [
      {
        name: "status",
        label: "学籍状态",
        type: "select",
        value: student.status,
        options: Object.entries(STUDENT_STATUS_LABEL).map(([value, label]) => ({ value, label })),
      },
      {
        name: "effective_date",
        label: "生效日期",
        type: "date",
        required: true,
        value: new Date().toISOString().slice(0, 10),
      },
      { name: "reason", label: "原因" },
    ],
    submitLabel: "确认变更",
    onSubmit: async (values) => {
      await api.post(`/students/${student.id}/status`, values);
      toast("学籍状态已更新");
      await refreshView();
    },
  });
}

async function showStatusHistory(student) {
  const rows = await api.get(`/students/${student.id}/status-history`);
  const overlay = el("div", { class: "overlay" });
  const modal = el("div", { class: "modal" }, [el("h3", { text: `学籍异动 · ${student.name}` })]);
  const body = el("div");
  renderTable(
    body,
    [
      { label: "生效日期", value: (row) => row.effective_date },
      {
        label: "变更",
        value: (row) =>
          `${STUDENT_STATUS_LABEL[row.from_status] || "-"} → ${STUDENT_STATUS_LABEL[row.to_status]}`,
      },
      { label: "原因", value: (row) => row.reason || "-" },
    ],
    rows,
    null,
  );
  modal.append(body);
  const actions = [];
  if (can("student:manage")) {
    actions.push(
      el("button", {
        class: "btn primary",
        text: "变更学籍",
        onclick: () => {
          overlay.remove();
          statusForm(student);
        },
      }),
    );
  }
  actions.push(el("button", { class: "btn", text: "关闭", onclick: () => overlay.remove() }));
  modal.append(el("div", { class: "modal-actions" }, actions));
  overlay.append(modal);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) overlay.remove();
  });
  document.body.append(overlay);
}

async function rolePermissionPanel(container) {
  const [roles, permissions] = await Promise.all([
    api.get("/authz/roles"),
    api.get("/authz/permissions"),
  ]);
  const roleSelect = el("select", { class: "input", "aria-label": "选择角色" });
  for (const role of roles) {
    roleSelect.append(option(role.code, `${role.name}（${role.code}）`));
  }
  const panel = el("div", { class: "card perm-card" });
  const save = el("button", { class: "btn primary", text: "保存授权" });
  const groups = new Map();
  for (const permission of permissions) {
    const list = groups.get(permission.resource) || [];
    list.push(permission);
    groups.set(permission.resource, list);
  }

  const render = () => {
    const role = roles.find((item) => item.code === roleSelect.value) || roles[0];
    panel.innerHTML = "";
    const inputs = [];
    for (const [resource, items] of groups) {
      const holder = el("div", { class: "perm-items" });
      for (const permission of items) {
        const box = el("input", { type: "checkbox" });
        box.checked = role.permissions.includes(permission.code);
        box.dataset.code = permission.code;
        inputs.push(box);
        holder.append(
          el("label", { class: "perm-item" }, [
            box,
            el("span", { text: permission.name }),
            el("code", { text: permission.code }),
          ]),
        );
      }
      panel.append(
        el("section", { class: "perm-section" }, [el("h4", { text: resource }), holder]),
      );
    }
    save.onclick = async () => {
      try {
        const codes = inputs.filter((box) => box.checked).map((box) => box.dataset.code);
        const updated = await api.request("PUT", `/authz/roles/${role.id}/permissions`, {
          permissions: codes,
        });
        role.permissions = updated.permissions;
        toast("角色权限已更新");
      } catch (error) {
        handleError(error);
      }
    };
  };

  roleSelect.addEventListener("change", render);
  render();
  container.append(el("div", { class: "toolbar" }, [roleSelect, save]), panel);
}

function departmentForm(row, reload) {
  openForm({
    title: row ? "编辑院系" : "新增院系",
    fields: [
      ...(row ? [] : [{ name: "code", label: "编码", required: true, placeholder: "CSE" }]),
      { name: "name", label: "名称", required: true, value: row?.name },
      {
        name: "kind",
        label: "类型",
        type: "select",
        value: row?.kind || "college",
        options: [
          { value: "college", label: "学院" },
          { value: "office", label: "处室" },
        ],
      },
    ],
    onSubmit: async (values) => {
      if (row) {
        delete values.code;
        await api.patch(`/org/departments/${row.id}`, values);
      } else {
        await api.post("/org/departments", values);
      }
      toast("院系已保存");
      await reload();
      await loadLookups(true);
    },
  });
}

async function departmentPanel(container) {
  const rows = await api.get("/org/departments");
  const card = el("div", { class: "card" });
  const reload = () => departmentPanel(container);
  renderTable(
    card,
    [
      { label: "编码", value: (row) => row.code },
      { label: "名称", value: (row) => row.name },
      { label: "类型", value: (row) => (row.kind === "office" ? "处室" : "学院") },
    ],
    rows,
    can("department:manage") ? (row) => [{ label: "编辑", onClick: () => departmentForm(row, reload) }] : null,
  );
  container.append(card);
  if (can("department:manage")) {
    container.prepend(
      el("div", { class: "toolbar" }, [
        el("button", { class: "btn primary", text: "新增院系", onclick: () => departmentForm(null, reload) }),
      ]),
    );
  }
}

function subjectForm(row, reload) {
  openForm({
    title: row ? "编辑学科" : "新增学科",
    fields: [
      ...(row ? [] : [{ name: "code", label: "编码", required: true, placeholder: "CS" }]),
      { name: "name", label: "名称", required: true, value: row?.name },
      {
        name: "department_id",
        label: "所属院系",
        type: "select",
        value: row?.department_id ?? "",
        options: withEmpty(departmentOptions(), "暂不指定"),
        as: "int",
      },
    ],
    onSubmit: async (values) => {
      if (row) {
        delete values.code;
        await api.patch(`/org/subjects/${row.id}`, values);
      } else {
        await api.post("/org/subjects", values);
      }
      toast("学科已保存");
      await reload();
      await loadLookups(true);
    },
  });
}

async function subjectPanel(container) {
  const rows = await api.get("/org/subjects");
  const card = el("div", { class: "card" });
  const reload = () => subjectPanel(container);
  renderTable(
    card,
    [
      { label: "编码", value: (row) => row.code },
      { label: "名称", value: (row) => row.name },
      {
        label: "所属院系",
        value: (row) => (row.department_id ? mapName("department", row.department_id) : "-"),
      },
    ],
    rows,
    can("subject:manage") ? (row) => [{ label: "编辑", onClick: () => subjectForm(row, reload) }] : null,
  );
  container.append(card);
  if (can("subject:manage")) {
    container.prepend(
      el("div", { class: "toolbar" }, [
        el("button", { class: "btn primary", text: "新增学科", onclick: () => subjectForm(null, reload) }),
      ]),
    );
  }
}

function semesterForm(row, reload) {
  openForm({
    title: row ? "编辑学期" : "新增学期",
    fields: [
      ...(row ? [] : [{ name: "name", label: "学期名称", required: true, placeholder: "2025-2026-1" }]),
      { name: "start_date", label: "开始日期", type: "date", required: true, value: row?.start_date },
      { name: "end_date", label: "结束日期", type: "date", required: true, value: row?.end_date },
      { name: "weeks", label: "周数", type: "number", value: row?.weeks ?? 20, as: "int" },
      {
        name: "status",
        label: "状态",
        type: "select",
        value: row?.status || "planned",
        options: Object.entries(SEMESTER_STATUS_LABEL).map(([value, label]) => ({ value, label })),
      },
    ],
    onSubmit: async (values) => {
      if (row) {
        delete values.name;
        await api.patch(`/org/semesters/${row.id}`, values);
      } else {
        await api.post("/org/semesters", values);
      }
      toast("学期已保存");
      await reload();
    },
  });
}

async function semesterPanel(container) {
  const rows = await api.get("/org/semesters");
  const card = el("div", { class: "card" });
  const reload = () => semesterPanel(container);
  const manage = can("semester:manage");
  renderTable(
    card,
    [
      { label: "学期", value: (row) => row.name },
      { label: "开始", value: (row) => row.start_date },
      { label: "结束", value: (row) => row.end_date },
      { label: "周数", value: (row) => row.weeks },
      { label: "状态", value: (row) => SEMESTER_STATUS_LABEL[row.status] || row.status },
      { label: "当前", value: (row) => (row.is_current ? "是" : "-") },
    ],
    rows,
    manage
      ? (row) => [
          ...(row.is_current
            ? []
            : [
                {
                  label: "设为当前",
                  onClick: async () => {
                    try {
                      await api.post(`/org/semesters/${row.id}/activate`);
                      toast("已切换当前学期");
                      await reload();
                    } catch (error) {
                      handleError(error);
                    }
                  },
                },
              ]),
          { label: "编辑", onClick: () => semesterForm(row, reload) },
        ]
      : null,
  );
  container.append(card);
  if (manage) {
    container.prepend(
      el("div", { class: "toolbar" }, [
        el("button", { class: "btn primary", text: "新增学期", onclick: () => semesterForm(null, reload) }),
      ]),
    );
  }
}

async function reportsView(container) {
  const tabs = [
    ["workload", "教师工作量"],
    ["subjects", "学科分析"],
    ["classes", "班级对比"],
  ];
  let mode = "workload";
  const bar = el("div", { class: "segmented", role: "group", "aria-label": "报表分类" });
  const body = el("div", { class: "view-page" });
  const buttons = [];
  const columns = {
    workload: [
      { label: "工号", value: (row) => row.teacher_no },
      { label: "教师", value: (row) => row.teacher_name },
      { label: "院系", value: (row) => row.department || "-" },
      { label: "学科", value: (row) => row.subject_name || "-" },
      { label: "职务", value: (row) => row.position || "-" },
      { label: "课程数", value: (row) => row.course_count },
      { label: "周课时", value: (row) => row.weekly_periods },
      { label: "总学时", value: (row) => row.hours },
      { label: "学生数", value: (row) => row.student_count },
      { label: "班级数", value: (row) => row.class_count },
    ],
    subjects: [
      { label: "学科", value: (row) => row.subject_name },
      { label: "课程数", value: (row) => row.course_count },
      { label: "学生数", value: (row) => row.student_count },
      { label: "平均分", value: (row) => row.average_score ?? "-" },
      { label: "及格率", value: (row) => fmt.pct(row.pass_rate) },
    ],
    classes: [
      { label: "班级", value: (row) => row.class_name },
      { label: "人数", value: (row) => row.student_count },
      { label: "平均分", value: (row) => row.average_score ?? "-" },
      { label: "出勤率", value: (row) => fmt.pct(row.attendance_rate) },
      { label: "收缴率", value: (row) => fmt.pct(row.collection_rate) },
    ],
  };
  const endpoints = {
    workload: "/reports/workload",
    subjects: "/reports/subjects",
    classes: "/reports/classes",
  };
  const render = async () => {
    body.innerHTML = "";
    const rows = await api.get(endpoints[mode]);
    const card = el("div", { class: "card list-card" });
    renderTable(card, columns[mode], rows, null);
    body.append(card);
  };
  for (const [key, label] of tabs) {
    const button = el("button", { class: key === mode ? "active" : "", text: label });
    button.addEventListener("click", async () => {
      mode = key;
      for (const item of buttons) item.classList.toggle("active", item === button);
      await render();
    });
    buttons.push(button);
    bar.append(button);
  }
  const view = el("section", { class: "view-page" });
  view.append(
    el("div", { class: "page-head" }, [
      el("div", {}, [
        el("h2", { text: "报表" }),
        el("p", { class: "muted", text: "教师工作量、学科成绩与班级运行对比。" }),
      ]),
    ]),
    bar,
    body,
  );
  container.append(view);
  await render();
}

async function auditView(container) {
  await crudView(container, {
    title: "审计日志",
    subtitle: "写操作与导出记录，最新在前。",
    exportResource: "audit",
    filters: [
      {
        name: "method",
        label: "方法",
        type: "select",
        options: ["POST", "PATCH", "PUT", "DELETE", "GET"].map((value) => ({
          value,
          label: value,
        })),
      },
      { name: "path", label: "路径", type: "text", placeholder: "按路径筛选" },
    ],
    list: (p) => {
      const query = new URLSearchParams({ page: p.page, page_size: p.page_size });
      if (p.method) query.set("method", p.method);
      if (p.path) query.set("path", p.path);
      return api.get(`/audit-logs?${query.toString()}`);
    },
    columns: [
      { label: "时间", value: (row) => fmt.dateTime(row.created_at) },
      { label: "用户", value: (row) => row.username || "-" },
      { label: "角色", value: (row) => ROLE_LABEL[row.role] || row.role || "-" },
      { label: "方法", value: (row) => row.method },
      { label: "路径", value: (row) => row.path },
      { label: "状态", value: (row) => row.status_code },
      { label: "详情", value: (row) => row.detail || "-" },
    ],
  });
}

async function accountPanel(container) {
  await crudView(container, {
    title: "账号管理",
    subtitle: "账号启停用、重置密码与分页检索。",
    search: "按账号或姓名搜索",
    pageSize: 20,
    list: (p) => {
      const query = new URLSearchParams({ page: p.page, page_size: p.page_size });
      if (p.keyword) query.set("keyword", p.keyword);
      return api.get(`/accounts?${query.toString()}`);
    },
    columns: [
      { label: "账号", value: (row) => row.username },
      { label: "姓名", value: (row) => row.display_name },
      { label: "角色", value: (row) => ROLE_LABEL[row.role] || row.role },
      { label: "状态", value: (row) => (row.is_active ? "正常" : "停用") },
    ],
    rowActions: (row, reload) => [
      {
        label: "重置密码",
        onClick: async () => {
          const password = await promptDialog({
            title: "重置密码",
            label: `为 ${row.username} 设置新密码（至少 8 位）`,
            confirmLabel: "重置",
          });
          if (!password) return;
          try {
            await api.post(`/accounts/${row.id}/reset-password`, { new_password: password });
            toast("密码已重置");
          } catch (error) {
            handleError(error);
          }
        },
      },
      {
        label: row.is_active ? "停用" : "启用",
        danger: row.is_active,
        onClick: async () => {
          try {
            await api.patch(`/accounts/${row.id}`, { is_active: !row.is_active });
            toast("账号状态已更新");
            await reload();
          } catch (error) {
            handleError(error);
          }
        },
      },
    ],
  });
}

function importStudentsForm(reload) {
  const overlay = el("div", { class: "overlay" });
  const modal = el("div", { class: "modal" }, [el("h3", { text: "导入学生 CSV" })]);
  const file = el("input", { type: "file", accept: ".csv,text/csv" });
  const textarea = el("textarea", {
    class: "input import-textarea",
    rows: "10",
    placeholder: "student_no,name,gender,status,class_id,phone",
  });
  file.addEventListener("change", async () => {
    const selected = file.files?.[0];
    if (selected) textarea.value = await selected.text();
  });
  modal.append(
    el("p", { class: "muted", text: "表头至少包含 student_no 与 name；可选 class_id、gender、status。" }),
    file,
    textarea,
  );
  const submit = el("button", {
    class: "btn primary",
    text: "开始导入",
    onclick: async () => {
      try {
        const result = await api.post("/transfer/import/students", { csv: textarea.value });
        toast(`导入完成：新增 ${result.created}，更新 ${result.updated}`);
        if (result.errors.length) window.alert(result.errors.join("\n"));
        overlay.remove();
        await reload();
      } catch (error) {
        handleError(error);
      }
    },
  });
  modal.append(
    el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "取消", onclick: () => overlay.remove() }),
      submit,
    ]),
  );
  overlay.append(modal);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) overlay.remove();
  });
  document.body.append(overlay);
}

async function settingsView(container) {
  const tabs = [
    ["roles", "角色权限", rolePermissionPanel],
    ["accounts", "账号", accountPanel],
    ["departments", "院系", departmentPanel],
    ["subjects", "学科", subjectPanel],
    ["semesters", "学期", semesterPanel],
  ];
  const bar = el("div", {
    class: "segmented",
    role: "group",
    "aria-label": "系统设置分类",
  });
  const body = el("div");
  const buttons = [];
  for (const [key, label, panel] of tabs) {
    const button = el("button", { class: key === "roles" ? "active" : "", text: label });
    button.addEventListener("click", async () => {
      for (const item of buttons) item.classList.toggle("active", item === button);
      body.innerHTML = "";
      await panel(body);
    });
    buttons.push(button);
    bar.append(button);
  }
  container.append(
    el("div", { class: "page-head" }, [
      el("div", {}, [
        el("h2", { text: "系统设置" }),
        el("p", { class: "muted", text: "组织架构、学期与角色权限。" }),
      ]),
    ]),
    bar,
    body,
  );
  await rolePermissionPanel(body);
}
export {
  dashboardView,
  reportsView,
  studentsView,
  teachersView,
  classesView,
  coursesView,
  enrollmentsView,
  scoresView,
  attendanceView,
  schedulesView,
  dormsView,
  feesView,
  leavesView,
  noticesView,
  settingsView,
  auditView,
  rolePermissionPanel,
  accountPanel,
  departmentPanel,
  subjectPanel,
  semesterPanel,
  importStudentsForm,
  showSeats,
};
