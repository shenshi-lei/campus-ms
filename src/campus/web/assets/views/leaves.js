import { api } from "../api.js";
import { el, fmt, icon, toast } from "../ui.js";
import {
  LEAVE_STATUS_LABEL,
  LEAVE_TYPE_LABEL,
  handleError,
  state,
  withEmpty,
} from "../core/state.js";
import { confirmDialog, openDrawer, openModal, promptDialog } from "../components/modal.js";
import { renderFlowChart, renderTimeline } from "../components/flow.js";
import { renderPager, renderTable } from "../components/table.js";
import { openExportDialog } from "../components/table.js";

const STATUS_CLASS = {
  pending: "warning",
  approved: "success",
  rejected: "danger",
  cancelled: "muted",
};

function tag(text, kind = "") {
  return el("span", { class: `tag ${kind}`, text });
}

function localInput(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function defaultRange() {
  const start = new Date();
  start.setDate(start.getDate() + 1);
  start.setHours(8, 0, 0, 0);
  const end = new Date(start);
  end.setHours(18, 0, 0, 0);
  return { start: localInput(start), end: localInput(end) };
}

function progressText(row) {
  const current = (row.approvals || []).find((item) => item.step_no === row.current_step);
  const name = current?.step_name || `第 ${row.current_step} 级`;
  if (row.status === "approved") return "已完成";
  if (row.status === "rejected") return "已驳回";
  if (row.status === "cancelled") return "已撤销";
  return `${name} · ${row.current_step}/${row.required_steps}`;
}

export async function leavesView(container) {
  const canApprove = state.permissions.has("leave:approve");
  const canApply = state.permissions.has("leave:apply");
  const modeOptions = [["mine", "我的申请"]];
  if (canApprove) modeOptions.push(["pending", "待我审批"]);
  if (state.permissions.has("leave:read")) modeOptions.push(["all", "全部申请"]);
  let mode = "mine";
  const params = { page: 1, page_size: 20, keyword: "", status: "", leave_type: "" };

  const view = el("section", { class: "view-page" });
  const tabs = el("div", { class: "segmented", role: "group", "aria-label": "请假分类" });
  const tabButtons = [];
  const tableHost = el("div", { class: "table-scroll" });
  const pager = el("div", { class: "pager" });
  const card = el("div", { class: "card list-card" }, [
    tableHost,
    el("div", { class: "list-footer" }, [pager]),
  ]);
  const statusFilter = el(
    "select",
    { class: "filter-select" },
    [{ value: "", label: "全部状态" }, ...Object.entries(LEAVE_STATUS_LABEL).map(([value, label]) => ({ value, label }))].map(
      (item) => el("option", { value: item.value, text: item.label }),
    ),
  );
  const typeFilter = el(
    "select",
    { class: "filter-select" },
    [{ value: "", label: "全部类型" }, ...Object.entries(LEAVE_TYPE_LABEL).map(([value, label]) => ({ value, label }))].map(
      (item) => el("option", { value: item.value, text: item.label }),
    ),
  );
  const keyword = el("input", { class: "search", type: "search", placeholder: "搜索申请人或事由" });

  let reload = async () => {};

  const head = el("div", { class: "page-head" }, [
    el("div", {}, [
      el("h2", { text: "请假中心" }),
      el("p", { class: "muted", text: "提交申请、查看审批流程与流转记录。" }),
    ]),
    el("div", { class: "actions" }, [
      canApply
        ? el("button", { class: "btn primary", onclick: () => openApply(reload) }, [
            icon("plus", 16),
            "申请请假",
          ])
        : null,
    ]),
  ]);

  for (const [key, label] of modeOptions) {
    const button = el("button", { class: key === mode ? "active" : "", text: label });
    button.addEventListener("click", () => {
      mode = key;
      params.page = 1;
      for (const item of tabButtons) item.classList.toggle("active", item === button);
      reload();
    });
    tabButtons.push(button);
    tabs.append(button);
  }

  statusFilter.addEventListener("change", () => {
    params.status = statusFilter.value;
    params.page = 1;
    reload();
  });
  typeFilter.addEventListener("change", () => {
    params.leave_type = typeFilter.value;
    params.page = 1;
    reload();
  });
  keyword.addEventListener("input", () => {
    window.clearTimeout(keyword._timer);
    keyword._timer = window.setTimeout(() => {
      params.keyword = keyword.value.trim();
      params.page = 1;
      reload();
    }, 300);
  });

  const toolbar = el("div", { class: "list-toolbar" }, [
    el("div", { class: "search-group" }, [
      el("span", { class: "search-icon" }, [icon("search", 16)]),
      keyword,
    ]),
    statusFilter,
    typeFilter,
    el("span", { class: "spacer" }),
    el("button", { class: "btn small ghost", text: "刷新", onclick: () => reload() }, [
      icon("refresh", 14),
      "刷新",
    ]),
    el("button", {
      class: "btn small",
      text: "导出",
      onclick: () => openExportDialog({ resource: "leaves", params }),
    }, [icon("download", 14), "导出"]),
  ]);

  const openDecision = async (row, approved) => {
    const remark = await promptDialog({
      title: approved ? "通过审批" : "驳回审批",
      label: "审批意见",
      value: approved ? "同意" : "",
      placeholder: approved ? "可填写审批意见" : "请填写驳回原因",
      confirmLabel: approved ? "确认通过" : "确认驳回",
    });
    if (remark === null) return;
    if (!approved && !remark.trim()) {
      toast("驳回必须填写原因", "error");
      return;
    }
    try {
      await api.post(`/leaves/${row.id}/${approved ? "approve" : "reject"}`, { remark });
      toast(approved ? "已通过" : "已驳回");
      await reload();
    } catch (error) {
      handleError(error);
    }
  };

  const openDetail = async (row) => {
    let detail;
    try {
      detail = await api.get(`/leaves/${row.id}`);
    } catch (error) {
      handleError(error);
      return;
    }
    const info = el("div", { class: "detail-grid" }, [
      ["申请人", detail.student_name || detail.teacher_name || "-"],
      ["学号/工号", detail.student_no || "-"],
      ["请假类型", LEAVE_TYPE_LABEL[detail.leave_type] || detail.leave_type],
      ["起止时间", `${fmt.dateTime(detail.start_at)} ~ ${fmt.dateTime(detail.end_at)}`],
      ["天数", `${detail.days} 天`],
      ["提交时间", fmt.dateTime(detail.created_at)],
      ["当前流程", detail.flow_name || "默认审批流程"],
      ["状态", LEAVE_STATUS_LABEL[detail.status] || detail.status],
    ].map(([label, value]) =>
      el("div", { class: "detail-item" }, [
        el("span", { text: label }),
        el("strong", { text: String(value) }),
      ]),
    ));
    const body = el("div", { class: "leave-detail" }, [
      el("section", { class: "detail-section" }, [
        el("h4", { text: "审批流程" }),
        renderFlowChart(detail),
      ]),
      el("section", { class: "detail-section" }, [el("h4", { text: "申请信息" }), info]),
      el("section", { class: "detail-section" }, [
        el("h4", { text: "请假事由" }),
        el("p", { class: "detail-text", text: detail.reason || "-" }),
      ]),
      el("section", { class: "detail-section" }, [
        el("h4", { text: "流转记录" }),
        renderTimeline(detail.events),
      ]),
    ]);
    const footer = el("div", { class: "modal-actions" });
    if (detail.actions?.can_approve) {
      footer.append(
        el("button", { class: "btn", text: "驳回", onclick: () => openDecision(detail, false) }),
        el("button", {
          class: "btn primary",
          text: "通过审批",
          onclick: () => openDecision(detail, true),
        }),
      );
    }
    if (detail.actions?.can_cancel) {
      footer.append(
        el("button", {
          class: "btn danger",
          text: "撤销申请",
          onclick: async () => {
            if (!(await confirmDialog({ title: "撤销申请", message: "确定撤销该请假申请吗？", danger: true }))) return;
            try {
              await api.post(`/leaves/${detail.id}/cancel`);
              toast("已撤销");
              drawer.close();
              await reload();
            } catch (error) {
              handleError(error);
            }
          },
        }),
      );
    }
    if (detail.actions?.can_revoke) {
      footer.append(
        el("button", {
          class: "btn danger",
          text: "撤回并回滚考勤",
          onclick: async () => {
            if (!(await confirmDialog({ title: "撤回申请", message: "撤回后考勤将回滚，确定继续？", danger: true }))) return;
            try {
              await api.post(`/leaves/${detail.id}/revoke`, { remark: "管理员撤回" });
              toast("已撤回");
              drawer.close();
              await reload();
            } catch (error) {
              handleError(error);
            }
          },
        }),
      );
    }
    footer.append(el("button", { class: "btn", text: "关闭", onclick: () => drawer.close() }));
    const drawer = openDrawer({
      title: `请假详情 · ${detail.student_name || detail.teacher_name || ""}`,
      subtitle: detail.flow_name || "审批流程",
      body,
      footer,
      width: "xl",
    });
  };

  reload = async () => {
    tableHost.innerHTML = "";
    renderTable(tableHost, [], [], null, { loading: true });
    try {
      let data;
      if (mode === "pending") {
        data = await api.get(
          `/leaves/pending/page?page=${params.page}&page_size=${params.page_size}`,
        );
      } else {
        const query = new URLSearchParams({
          mine: mode === "mine" ? "true" : "false",
          page: String(params.page),
          page_size: String(params.page_size),
        });
        if (params.keyword) query.set("keyword", params.keyword);
        if (params.status) query.set("status", params.status);
        if (params.leave_type) query.set("leave_type", params.leave_type);
        data = await api.get(`/leaves?${query.toString()}`);
      }
      tableHost.innerHTML = "";
      renderTable(
        tableHost,
        [
          {
            label: "申请人",
            render: (row) =>
              el("div", { class: "cell-main" }, [
                el("strong", { text: row.student_name || row.teacher_name || "-" }),
                el("small", { class: "muted", text: row.student_no || "" }),
              ]),
          },
          { label: "类型", value: (row) => LEAVE_TYPE_LABEL[row.leave_type] || row.leave_type },
          {
            label: "起止时间",
            render: (row) =>
              el("div", { class: "cell-stack" }, [
                el("span", { text: fmt.dateTime(row.start_at) }),
                el("small", { class: "muted", text: fmt.dateTime(row.end_at) }),
              ]),
          },
          { label: "天数", value: (row) => `${row.days} 天` },
          { label: "进度", value: progressText },
          {
            label: "状态",
            render: (row) =>
              tag(
                LEAVE_STATUS_LABEL[row.status] || row.status,
                STATUS_CLASS[row.status] || "",
              ),
          },
          { label: "提交时间", value: (row) => fmt.dateTime(row.created_at) },
        ],
        data.items,
        (row) => {
          const actions = [{ label: "查看", onClick: () => openDetail(row) }];
          if (mode === "pending" && row.actions?.can_approve) {
            actions.push({ label: "通过", onClick: () => openDecision(row, true) });
            actions.push({ label: "驳回", danger: true, onClick: () => openDecision(row, false) });
          }
          return actions;
        },
        { emptyText: mode === "pending" ? "没有待你审批的请假" : "还没有请假记录" },
      );
      renderPager(
        pager,
        data,
        (page) => {
          params.page = page;
          reload();
        },
        {
          onPageSize: (size) => {
            params.page_size = size;
            params.page = 1;
            reload();
          },
        },
      );
    } catch (error) {
      tableHost.innerHTML = "";
      tableHost.append(
        el("div", { class: "panel error-panel" }, [
          el("h3", { text: "请假列表加载失败" }),
          el("p", { class: "muted", text: error?.message || "未知错误" }),
          el("button", { class: "btn primary", text: "重试", onclick: () => reload() }),
        ]),
      );
      handleError(error);
    }
  };

  view.append(head, tabs, toolbar, card);
  container.append(view);
  await reload();
}

function openApply(reload) {
  const range = defaultRange();
  const type = el(
    "select",
    { class: "input" },
    Object.entries(LEAVE_TYPE_LABEL).map(([value, label]) => el("option", { value, text: label })),
  );
  const start = el("input", { class: "input", type: "datetime-local", value: range.start });
  const end = el("input", { class: "input", type: "datetime-local", value: range.end });
  const reason = el("textarea", { class: "input", rows: "4", placeholder: "请填写请假事由" });
  const hint = el("div", { class: "flow-preview muted", text: "提交后将按系统配置的审批流程流转。" });
  const form = el("div", { class: "form-grid cols-2" }, [
    el("label", { class: "field" }, [el("span", { text: "请假类型" }), type]),
    el("label", { class: "field" }, [el("span", { text: "开始时间" }), start]),
    el("label", { class: "field" }, [el("span", { text: "结束时间" }), end]),
    el("label", { class: "field span-full" }, [el("span", { text: "请假事由 *" }), reason]),
    el("div", { class: "span-full" }, [hint]),
  ]);
  const dialog = openModal({
    title: "申请请假",
    subtitle: "提交后可在请假中心查看审批进度",
    size: "lg",
    body: form,
    footer: el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "取消", onclick: () => dialog.close() }),
      el("button", {
        class: "btn primary",
        text: "提交申请",
        onclick: async () => {
          if (!reason.value.trim()) {
            toast("请填写请假事由", "error");
            return;
          }
          try {
            await api.post("/leaves", {
              leave_type: type.value,
              start_at: start.value,
              end_at: end.value,
              reason: reason.value.trim(),
            });
            toast("请假已提交");
            dialog.close();
            await reload();
          } catch (error) {
            handleError(error);
          }
        },
      }),
    ]),
  });
}
