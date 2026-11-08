import { api } from "../api.js";
import { el, fmt, icon, toast } from "../ui.js";
import { handleError, state } from "../core/state.js";
import { confirmDialog, openDrawer, openForm } from "../components/modal.js";

const KIND_LABEL = {
  meeting: "会议",
  activity: "活动",
  exam: "考试",
  holiday: "假期",
  personal: "个人",
  other: "其他",
};
const VISIBILITY_LABEL = {
  personal: "仅本人",
  department: "院系",
  class: "班级",
  school: "全校",
};
const RESPONSE_LABEL = { pending: "待回复", accepted: "已接受", declined: "已拒绝" };
const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

function pad(value) {
  return String(value).padStart(2, "0");
}
function iso(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}
function startOfWeek(date) {
  const copy = new Date(date);
  const offset = (copy.getDay() + 6) % 7;
  copy.setDate(copy.getDate() - offset);
  copy.setHours(0, 0, 0, 0);
  return copy;
}
function addDays(date, days) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}
function localInput(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export async function calendarView(container) {
  const canManage = state.permissions.has("calendar:manage");
  let mode = "month";
  let cursor = new Date();
  let kind = "";
  const view = el("section", { class: "view-page calendar-page" });
  const head = el("div", { class: "page-head" }, [
    el("div", {}, [
      el("h2", { text: "日程" }),
      el("p", { class: "muted", text: "会议、活动、考试与个人事项，一目了然。" }),
    ]),
    el("div", { class: "actions" }, [
      canManage
        ? el("button", { class: "btn primary", onclick: () => openEventForm({ reload, date: cursor }) }, [
            icon("plus", 16),
            "新建日程",
          ])
        : null,
    ]),
  ]);
  const modeBar = el("div", { class: "segmented" });
  const kindSelect = el(
    "select",
    { class: "filter-select" },
    [
      { value: "", label: "全部类型" },
      ...Object.entries(KIND_LABEL).map(([value, label]) => ({ value, label })),
    ].map((item) => el("option", { value: item.value, text: item.label })),
  );
  const nav = el("div", { class: "timetable-nav" });
  const title = el("div", { class: "calendar-title" });
  const content = el("div", { class: "calendar-content" });
  let reload = async () => {};

  for (const [key, label] of [["month", "月"], ["week", "周"], ["day", "日"]]) {
    const button = el("button", {
      class: key === mode ? "active" : "",
      text: label,
      onclick: () => {
        mode = key;
        modeBar.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
        reload();
      },
    });
    modeBar.append(button);
  }
  kindSelect.addEventListener("change", () => {
    kind = kindSelect.value;
    reload();
  });

  const move = (delta) => {
    if (mode === "month") cursor = new Date(cursor.getFullYear(), cursor.getMonth() + delta, 1);
    else if (mode === "week") cursor = addDays(startOfWeek(cursor), delta * 7);
    else cursor = addDays(cursor, delta);
    reload();
  };

  const openDetail = async (eventId) => {
    let detail;
    try {
      detail = await api.get(`/calendar/events/${eventId}`);
    } catch (error) {
      handleError(error);
      return;
    }
    const info = el("div", { class: "detail-grid" }, [
      ["时间", detail.all_day ? "全天" : `${fmt.dateTime(detail.start_at)} ~ ${fmt.dateTime(detail.end_at)}`],
      ["地点", detail.location || "-"],
      ["类型", KIND_LABEL[detail.kind] || detail.kind],
      ["可见范围", VISIBILITY_LABEL[detail.visibility] || detail.visibility],
      ["发起人", detail.owner_name || "-"],
      ["提醒", detail.remind_minutes ? `提前 ${detail.remind_minutes} 分钟` : "不提醒"],
    ].map(([key, value]) =>
      el("div", { class: "detail-item" }, [
        el("span", { text: key }),
        el("strong", { text: String(value) }),
      ]),
    ));
    const participants = el("div", { class: "participant-list" });
    for (const participant of detail.participants || []) {
      participants.append(
        el("span", { class: "person-chip" }, [
          el("span", { text: participant.display_name }),
          el("small", { text: RESPONSE_LABEL[participant.response] || participant.response }),
        ]),
      );
    }
    if (!detail.participants?.length) participants.append(el("span", { class: "muted", text: "未指定参与人" }));
    const body = el("div", {}, [
      el("p", { class: "detail-text", text: detail.description || "无描述" }),
      el("section", { class: "detail-section" }, [el("h4", { text: "基本信息" }), info]),
      el("section", { class: "detail-section" }, [el("h4", { text: "参与人" }), participants]),
    ]);
    const footer = el("div", { class: "modal-actions" });
    if (detail.can_edit) {
      footer.append(
        el("button", { class: "btn", text: "编辑", onclick: () => { drawer.close(); openEventForm({ reload, event: detail }); } }),
        el("button", {
          class: "btn danger",
          text: "删除",
          onclick: async () => {
            if (!(await confirmDialog({ title: "删除日程", message: "确定删除该日程吗？", danger: true }))) return;
            try {
              await api.del(`/calendar/events/${detail.id}`);
              toast("已删除");
              drawer.close();
              await reload();
            } catch (error) {
              handleError(error);
            }
          },
        }),
      );
    }
    const mine = (detail.participants || []).find((item) => item.user_id === state.user.id);
    if (mine) {
      footer.append(
        el("button", {
          class: "btn",
          text: "接受",
          onclick: () => rsvp(detail.id, "accepted"),
        }),
        el("button", {
          class: "btn danger",
          text: "拒绝",
          onclick: () => rsvp(detail.id, "declined"),
        }),
      );
    }
    footer.append(el("button", { class: "btn", text: "关闭", onclick: () => drawer.close() }));
    const rsvp = async (id, response) => {
      try {
        await api.post(`/calendar/events/${id}/rsvp`, { response });
        toast("已回复");
        drawer.close();
        await reload();
      } catch (error) {
        handleError(error);
      }
    };
    const drawer = openDrawer({
      title: detail.title,
      subtitle: `${KIND_LABEL[detail.kind] || detail.kind} · ${VISIBILITY_LABEL[detail.visibility] || ""}`,
      body,
      footer,
      width: "lg",
    });
  };

  const eventChip = (event, showTime = true) =>
    el("button", {
      class: `calendar-event ${event.kind}`,
      onclick: (clickEvent) => {
        clickEvent.stopPropagation();
        openDetail(event.id);
      },
    }, [
      showTime && !event.all_day
        ? el("span", { class: "event-time", text: fmt.time(event.start_at) })
        : null,
      el("span", { class: "event-title", text: event.title }),
    ]);

  const renderMonth = (data, start) => {
    const grid = el("div", { class: "calendar-month" });
    for (const weekday of WEEKDAYS) grid.append(el("div", { class: "calendar-weekday", text: `周${weekday}` }));
    const byDate = new Map();
    for (const event of data) {
      const key = iso(new Date(event.start_at));
      if (!byDate.has(key)) byDate.set(key, []);
      byDate.get(key).push(event);
    }
    for (let index = 0; index < 42; index += 1) {
      const date = addDays(start, index);
      const key = iso(date);
      const events = byDate.get(key) || [];
      const cell = el("div", {
        class: `calendar-day ${date.getMonth() !== cursor.getMonth() ? "outside" : ""} ${key === iso(new Date()) ? "today" : ""}`,
        onclick: () => {
          cursor = date;
          mode = "day";
          modeBar.querySelectorAll("button").forEach((button) => button.classList.toggle("active", button.textContent === "日"));
          reload();
        },
      }, [
        el("span", { class: "calendar-date", text: String(date.getDate()) }),
        ...events.slice(0, 3).map((event) => eventChip(event)),
        events.length > 3 ? el("small", { class: "muted", text: `+${events.length - 3} 更多` }) : null,
      ]);
      grid.append(cell);
    }
    return grid;
  };

  const renderWeek = (data, start) => {
    const grid = el("div", { class: "calendar-week" });
    for (let index = 0; index < 7; index += 1) {
      const date = addDays(start, index);
      const key = iso(date);
      const events = data.filter((event) => iso(new Date(event.start_at)) === key);
      grid.append(
        el("div", { class: `calendar-week-col ${key === iso(new Date()) ? "today" : ""}` }, [
          el("div", { class: "calendar-week-head" }, [
            el("span", { text: `周${WEEKDAYS[index]}` }),
            el("strong", { text: `${date.getMonth() + 1}/${date.getDate()}` }),
          ]),
          ...events.map((event) => eventChip(event)),
          events.length ? null : el("span", { class: "muted small", text: "无日程" }),
        ]),
      );
    }
    return grid;
  };

  const renderDay = (data) => {
    const list = el("div", { class: "calendar-day-list" });
    if (!data.length) {
      list.append(el("div", { class: "empty", text: "当天没有日程" }));
      return list;
    }
    for (const event of data.sort((a, b) => new Date(a.start_at) - new Date(b.start_at))) {
      list.append(
        el("article", { class: "calendar-day-item", onclick: () => openDetail(event.id) }, [
          el("div", { class: "event-time-block", text: event.all_day ? "全天" : fmt.time(event.start_at) }),
          el("div", {}, [
            el("strong", { text: event.title }),
            el("p", { class: "muted", text: `${KIND_LABEL[event.kind] || event.kind} · ${event.location || "地点待定"}` }),
          ]),
        ]),
      );
    }
    return list;
  };

  reload = async () => {
    content.innerHTML = "";
    content.append(el("div", { class: "empty", text: "加载日程…" }));
    try {
      let start;
      let end;
      if (mode === "month") {
        start = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
        start = addDays(start, -((start.getDay() + 6) % 7));
        end = addDays(start, 42);
        title.textContent = `${cursor.getFullYear()} 年 ${cursor.getMonth() + 1} 月`;
      } else if (mode === "week") {
        start = startOfWeek(cursor);
        end = addDays(start, 7);
        title.textContent = `${start.getFullYear()} 年 ${start.getMonth() + 1} 月 ${start.getDate()} 日当周`;
      } else {
        start = new Date(cursor);
        start.setHours(0, 0, 0, 0);
        end = addDays(start, 1);
        title.textContent = `${cursor.getFullYear()} 年 ${cursor.getMonth() + 1} 月 ${cursor.getDate()} 日`;
      }
      const query = new URLSearchParams({ start: start.toISOString(), end: end.toISOString() });
      if (kind) query.set("kind", kind);
      const data = (await api.get(`/calendar/events?${query.toString()}`)).filter(
        (event) => !kind || event.kind === kind,
      );
      nav.innerHTML = "";
      nav.append(
        el("button", { class: "btn small", text: "‹", onclick: () => move(-1) }),
        el("button", { class: "btn small", text: "今天", onclick: () => { cursor = new Date(); reload(); } }),
        el("button", { class: "btn small", text: "›", onclick: () => move(1) }),
      );
      content.innerHTML = "";
      if (mode === "month") content.append(renderMonth(data, start));
      else if (mode === "week") content.append(renderWeek(data, start));
      else content.append(renderDay(data));
    } catch (error) {
      content.innerHTML = "";
      content.append(
        el("div", { class: "panel error-panel" }, [
          el("h3", { text: "日程加载失败" }),
          el("p", { class: "muted", text: error?.message || "未知错误" }),
          el("button", { class: "btn primary", text: "重试", onclick: () => reload() }),
        ]),
      );
      handleError(error);
    }
  };

  const toolbar = el("div", { class: "list-toolbar" }, [
    modeBar,
    kindSelect,
    el("span", { class: "spacer" }),
    nav,
    title,
  ]);
  view.append(head, toolbar, content);
  container.append(view);
  await reload();
}

function openEventForm({ reload, event = null, date = new Date() }) {
  const start = event ? new Date(event.start_at) : new Date(date);
  if (!event) start.setHours(9, 0, 0, 0);
  const end = event ? new Date(event.end_at) : new Date(start);
  if (!event) end.setHours(10, 0, 0, 0);
  openForm({
    title: event ? "编辑日程" : "新建日程",
    size: "lg",
    fields: [
      { name: "title", label: "标题", required: true, value: event?.title },
      {
        name: "kind",
        label: "类型",
        type: "select",
        value: event?.kind || "meeting",
        options: Object.entries(KIND_LABEL).map(([value, label]) => ({ value, label })),
      },
      {
        name: "visibility",
        label: "可见范围",
        type: "select",
        value: event?.visibility || "personal",
        options: Object.entries(VISIBILITY_LABEL).map(([value, label]) => ({ value, label })),
      },
      { name: "start_at", label: "开始时间", type: "datetime-local", required: true, value: localInput(start) },
      { name: "end_at", label: "结束时间", type: "datetime-local", required: true, value: localInput(end) },
      { name: "location", label: "地点", value: event?.location },
      { name: "remind_minutes", label: "提前提醒(分钟)", type: "number", value: event?.remind_minutes ?? 0, as: "int" },
      {
        name: "participant_ids",
        label: "参与人",
        type: "person-multi",
        personType: "teacher",
        value: (event?.participants || []).map((item) => ({ id: item.user_id, label: item.display_name })),
        span: "full",
      },
      { name: "description", label: "描述", type: "textarea", value: event?.description, span: "full" },
    ],
    submitLabel: event ? "保存" : "创建",
    onSubmit: async (values) => {
      values.all_day = false;
      if (event) {
        await api.patch(`/calendar/events/${event.id}`, values);
        toast("日程已更新");
      } else {
        await api.post("/calendar/events", values);
        toast("日程已创建");
      }
      await reload();
    },
  });
}
