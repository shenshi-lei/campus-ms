import { api } from "../api.js";
import { el, fmt, icon, toast } from "../ui.js";
import {
  WEEKDAY_LABEL,
  classOptions,
  courseOptions,
  handleError,
  state,
  teacherOptions,
  withEmpty,
} from "../core/state.js";
import { openDrawer, openForm } from "../components/modal.js";
import { openExportDialog } from "../components/table.js";

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function dateLabel(value) {
  return new Date(value).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function isoDate(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`;
}

export async function schedulesView(container) {
  const canManage = state.permissions.has("schedule:manage");
  const canChange = state.permissions.has("schedule:change");
  let mode = "week";
  let week = null;
  let month = new Date().toISOString().slice(0, 7);
  let day = isoDate(new Date());
  let semesterId = "";
  let classId = "";
  let teacherId = "";

  const view = el("section", { class: "view-page timetable-page" });
  const head = el("div", { class: "page-head" }, [
    el("div", {}, [
      el("h2", { text: "课表" }),
      el("p", { class: "muted", text: "默认展示本周课程，可切换周/日/月并查看课程详情。" }),
    ]),
    el("div", { class: "actions" }, [
      canManage
        ? el("button", { class: "btn primary", onclick: () => openScheduleForm({ reload, weekday: "", period: "" }) }, [
            icon("plus", 16),
            "新增排课",
          ])
        : null,
      el("button", { class: "btn", onclick: () => window.print() }, [icon("download", 16), "打印"]),
      el("button", {
        class: "btn",
        onclick: () => openExportDialog({ resource: "schedules", params: {} }),
      }, [icon("download", 16), "导出"]),
    ]),
  ]);
  const modeBar = el("div", { class: "segmented", role: "group", "aria-label": "课表视图" });
  const semesterSelect = el("select", { class: "filter-select", "aria-label": "学期" });
  const classSelect = el(
    "select",
    { class: "filter-select", "aria-label": "班级" },
    [{ value: "", label: "全部班级" }, ...classOptions()].map((item) =>
      el("option", { value: String(item.value), text: item.label }),
    ),
  );
  const teacherSelect = el(
    "select",
    { class: "filter-select", "aria-label": "教师" },
    [{ value: "", label: "全部教师" }, ...teacherOptions()].map((item) =>
      el("option", { value: String(item.value), text: item.label }),
    ),
  );
  const nav = el("div", { class: "timetable-nav" });
  const label = el("div", { class: "timetable-label" });
  const content = el("div", { class: "timetable-content" });
  let reload = async () => {};

  for (const [key, text] of [["week", "周"], ["day", "日"], ["month", "月"]]) {
    const button = el("button", {
      class: key === mode ? "active" : "",
      text,
      onclick: () => {
        mode = key;
        modeBar.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
        reload();
      },
    });
    modeBar.append(button);
  }
  if (state.lookups.semesters?.length) {
    semesterSelect.append(el("option", { value: "", text: "当前学期" }));
    for (const semester of state.lookups.semesters) {
      semesterSelect.append(
        el("option", {
          value: String(semester.id),
          text: `${semester.name}${semester.is_current ? "（当前）" : ""}`,
        }),
      );
    }
  }
  for (const item of [semesterSelect, classSelect, teacherSelect]) {
    item.addEventListener("change", () => {
      semesterId = semesterSelect.value;
      classId = classSelect.value;
      teacherId = teacherSelect.value;
      reload();
    });
  }
  semesterSelect.value = "";
  classSelect.value = "";
  teacherSelect.value = "";

  const shift = (delta) => {
    if (mode === "month") {
      const [year, monthNo] = month.split("-").map(Number);
      const target = new Date(year, monthNo - 1 + delta, 1);
      month = `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, "0")}`;
    } else if (mode === "day") {
      const target = new Date(day);
      target.setDate(target.getDate() + delta);
      day = isoDate(target);
    } else if (delta !== 0) {
      if (week === null) {
        const today = new Date();
        week = Math.max(1, Math.ceil((today.getDate() + 6) / 7));
      }
      week += delta;
      if (week < 1) week = 1;
    } else {
      week = null;
    }
    reload();
  };

  const openDetail = async (entry) => {
    try {
      const detail = await api.get(`/schedules/${entry.id}/detail`);
      const body = el("div", { class: "detail-grid" }, [
        ["课程", `${detail.course_code} ${detail.course_name}`],
        ["教师", detail.teacher_name || "-"],
        ["班级", detail.class_name || "-"],
        ["教室", detail.classroom || "-"],
        ["时间", `${WEEKDAY_LABEL[detail.weekday]} 第 ${detail.start_period}-${detail.end_period} 节`],
        ["周次", detail.weeks],
        ["选课人数", `${detail.enrolled} / ${detail.capacity}`],
        ["状态", detail.status === "cancelled" ? "停课" : "正常"],
      ].map(([key, value]) =>
        el("div", { class: "detail-item" }, [
          el("span", { text: key }),
          el("strong", { text: String(value) }),
        ]),
      ));
      const bodyWrap = el("div", { class: "detail-section" }, [
        el("h4", { text: "课程信息" }),
        body,
        detail.changes?.length
          ? el("div", { class: "detail-section" }, [
              el("h4", { text: "调课记录" }),
              el("ul", { class: "muted" }, detail.changes.map((item) => el("li", { text: item }))),
            ])
          : null,
      ]);
      openDrawer({
        title: "课程详情",
        subtitle: `${detail.course_code} · ${detail.course_name}`,
        body: bodyWrap,
        width: "lg",
      });
    } catch (error) {
      handleError(error);
    }
  };

  const courseCard = (entry) => {
    const card = el("button", { class: `course-cell ${entry.status === "cancelled" ? "cancelled" : ""}`, onclick: () => openDetail(entry) }, [
      el("strong", { text: entry.course_name }),
      el("small", { text: entry.teacher_name || "教师待定" }),
      el("small", { text: `${entry.classroom || "教室待定"} · ${entry.class_name || ""}` }),
      entry.note ? el("em", { text: entry.note }) : null,
    ]);
    return card;
  };

  const renderWeek = (data) => {
    const periods = data.periods || [];
    const entries = data.entries || [];
    const maxPeriod = Math.max(periods.length, ...entries.map((item) => item.end_period), 1);
    const matrix = new Map();
    for (const entry of entries) {
      matrix.set(`${entry.weekday}-${entry.start_period}`, entry);
    }
    const covered = new Set();
    const table = el("table", { class: "timetable" });
    const headRow = el("tr", {}, [
      el("th", { class: "period-col", text: "节次" }),
      ...data.days.map((item, index) =>
        el("th", { class: isoDate(item.date) === isoDate(new Date()) ? "today" : "" }, [
          el("span", { text: WEEKDAYS[index] }),
          el("small", { text: dateLabel(item.date) }),
        ]),
      ),
    ]);
    table.append(el("thead", {}, [headRow]));
    const tbody = el("tbody");
    for (let period = 1; period <= maxPeriod; period += 1) {
      const row = el("tr", {}, [
        el("th", { class: "period-col" }, [
          el("strong", { text: `第 ${period} 节` }),
          el("small", { text: periods.find((item) => item.no === period)?.start || "" }),
        ]),
      ]);
      for (let weekday = 1; weekday <= 7; weekday += 1) {
        const key = `${weekday}-${period}`;
        if (covered.has(key)) continue;
        const entry = matrix.get(key);
        if (entry) {
          const span = Math.max(1, entry.end_period - entry.start_period + 1);
          for (let offset = 1; offset < span; offset += 1) {
            covered.add(`${weekday}-${period + offset}`);
          }
          row.append(el("td", { rowspan: span, class: "course-td" }, [courseCard(entry)]));
        } else {
          row.append(
            el("td", {
              class: "empty-td",
              onclick: () => {
                if (!canManage) return;
                openScheduleForm({ reload, weekday, period });
              },
            }),
          );
        }
      }
      tbody.append(row);
    }
    table.append(tbody);
    return table;
  };

  const renderDay = (data) => {
    const wrap = el("div", { class: "day-schedule" });
    if (!data.entries?.length) {
      wrap.append(el("div", { class: "empty", text: "当天没有排课" }));
      return wrap;
    }
    for (const entry of data.entries) {
      wrap.append(
        el("article", { class: "day-course" }, [
          el("div", { class: "day-period", text: `${entry.start_period}-${entry.end_period} 节` }),
          el("div", { class: "day-course-main" }, [
            el("strong", { text: `${entry.course_code} ${entry.course_name}` }),
            el("p", { class: "muted", text: `${entry.teacher_name || ""} · ${entry.classroom || ""} · ${entry.class_name || ""}` }),
          ]),
          el("button", { class: "btn small", text: "详情", onclick: () => openDetail(entry) }),
        ]),
      );
    }
    return wrap;
  };

  const renderMonth = (data) => {
    const [year, monthNo] = data.month.split("-").map(Number);
    const first = new Date(year, monthNo - 1, 1);
    const startOffset = (first.getDay() + 6) % 7;
    const daysInMonth = new Date(year, monthNo, 0).getDate();
    const byDate = new Map((data.days || []).map((item) => [item.date, item]));
    const grid = el("div", { class: "month-grid" });
    for (const name of WEEKDAYS) grid.append(el("div", { class: "month-weekday", text: name }));
    for (let index = 0; index < startOffset; index += 1) {
      grid.append(el("div", { class: "month-cell muted" }));
    }
    for (let dateNo = 1; dateNo <= daysInMonth; dateNo += 1) {
      const date = `${year}-${String(monthNo).padStart(2, "0")}-${String(dateNo).padStart(2, "0")}`;
      const item = byDate.get(date);
      const cell = el("div", {
        class: `month-cell ${isoDate(new Date()) === date ? "today" : ""}`,
        onclick: () => {
          mode = "day";
          day = date;
          modeBar.querySelectorAll("button").forEach((button) => button.classList.toggle("active", button.textContent === "日"));
          reload();
        },
      }, [
        el("span", { class: "month-date", text: String(dateNo) }),
        ...(item?.entries || []).slice(0, 2).map((entry) =>
          el("span", { class: "month-event", text: `${entry.start_period} ${entry.course_name}` }),
        ),
        item?.count > 2 ? el("small", { class: "muted", text: `+${item.count - 2} 更多` }) : null,
      ]);
      grid.append(cell);
    }
    return grid;
  };

  reload = async () => {
    nav.innerHTML = "";
    label.textContent = "";
    content.innerHTML = "";
    content.append(el("div", { class: "empty", text: "加载课表…" }));
    try {
      let data;
      if (mode === "week") {
        const query = new URLSearchParams();
        if (week !== null) query.set("week", String(week));
        if (semesterId) query.set("semester_id", semesterId);
        if (classId) query.set("class_id", classId);
        if (teacherId) query.set("teacher_id", teacherId);
        data = await api.get(`/schedules/grid?${query.toString()}`);
        week = data.week;
        label.textContent = `${data.semester_name} · 第 ${data.week} 周 · ${data.week_start} ~ ${data.week_end}`;
      } else if (mode === "day") {
        const query = new URLSearchParams({ date: day });
        if (semesterId) query.set("semester_id", semesterId);
        if (classId) query.set("class_id", classId);
        if (teacherId) query.set("teacher_id", teacherId);
        data = await api.get(`/schedules/day?${query.toString()}`);
        label.textContent = `${data.date} ${data.label}`;
      } else {
        const query = new URLSearchParams({ month });
        if (classId) query.set("class_id", classId);
        if (teacherId) query.set("teacher_id", teacherId);
        data = await api.get(`/schedules/month?${query.toString()}`);
        label.textContent = data.month;
      }
      nav.append(
        el("button", { class: "btn small", text: "‹", title: "上一周期", onclick: () => shift(-1) }),
        el("button", { class: "btn small", text: mode === "week" ? "本周" : mode === "day" ? "今天" : "本月", onclick: () => shift(0) }),
        el("button", { class: "btn small", text: "›", title: "下一周期", onclick: () => shift(1) }),
      );
      content.innerHTML = "";
      if (mode === "week") content.append(renderWeek(data));
      else if (mode === "day") content.append(renderDay(data));
      else content.append(renderMonth(data));
    } catch (error) {
      content.innerHTML = "";
      content.append(
        el("div", { class: "panel error-panel" }, [
          el("h3", { text: "课表加载失败" }),
          el("p", { class: "muted", text: error?.message || "未知错误" }),
          el("button", { class: "btn primary", text: "重试", onclick: () => reload() }),
        ]),
      );
      handleError(error);
    }
  };

  const toolbar = el("div", { class: "list-toolbar" }, [
    semesterSelect,
    classSelect,
    teacherSelect,
    modeBar,
    el("span", { class: "spacer" }),
    nav,
    label,
  ]);
  view.append(head, toolbar, content);
  container.append(view);
  await reload();
}

function openScheduleForm({ reload, weekday, period }) {
  openForm({
    title: "新增排课",
    size: "lg",
    fields: [
      {
        name: "course_id",
        label: "课程",
        type: "select",
        options: withEmpty(courseOptions(), "请选择课程"),
        as: "int",
        required: true,
      },
      {
        name: "class_id",
        label: "行政班",
        type: "select",
        options: withEmpty(classOptions(), "暂不指定"),
        as: "int",
      },
      { name: "weekday", label: "星期", type: "select", value: weekday || 1, options: WEEKDAY_LABEL.slice(1).map((label, index) => ({ value: index + 1, label })), as: "int" },
      { name: "start_period", label: "起始节次", type: "number", value: period || 1, as: "int" },
      { name: "end_period", label: "结束节次", type: "number", value: period || 2, as: "int" },
      { name: "classroom", label: "教室", value: "A101" },
      { name: "weeks", label: "周次", value: "1-16" },
    ],
    submitLabel: "保存排课",
    onSubmit: async (values) => {
      await api.post("/schedules", values);
      toast("排课成功");
      await reload();
    },
  });
}
