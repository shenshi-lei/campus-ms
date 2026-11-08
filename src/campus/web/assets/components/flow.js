import { el } from "../ui.js";

const EVENT_LABEL = {
  submit: "提交申请",
  approve: "审批通过",
  reject: "审批驳回",
  cancel: "撤销申请",
  revoke: "管理员撤回",
  attendance_sync: "同步考勤",
  comment: "审批意见",
};

function stateOf(approval, request) {
  if (approval.status === "approved") return "done";
  if (approval.status === "rejected") return "rejected";
  if (approval.status === "cancelled") return "cancelled";
  if (request.status === "pending" && request.current_step === approval.step_no) return "current";
  return "waiting";
}

function stepLabel(approval) {
  return approval.step_name || approval.approver_role_code || `第 ${approval.step_no} 级`;
}

function approvalMeta(approval) {
  if (approval.approver_name) return approval.approver_name;
  if (approval.approver_role_code === "head_teacher") return "班主任";
  if (approval.approver_role_code === "student_affairs") return "学工处";
  if (approval.approver_role_code === "academic_director") return "教务主任";
  if (approval.approver_role_code === "admin") return "管理员";
  return approval.approver_role_code || "";
}

export function renderFlowChart(request) {
  const steps = [
    { key: "submit", title: "提交申请", state: "done", meta: "申请人" },
    ...(request.approvals || []).map((approval) => ({
      key: `step-${approval.step_no}`,
      title: stepLabel(approval),
      state: stateOf(approval, request),
      meta: approvalMeta(approval),
      remark: approval.remark,
      decided_at: approval.decided_at,
    })),
  ];
  const finalState =
    request.status === "approved"
      ? "done"
      : request.status === "rejected"
        ? "rejected"
        : request.status === "cancelled"
          ? "cancelled"
          : "waiting";
  steps.push({
    key: "final",
    title:
      request.status === "approved"
        ? "审批完成"
        : request.status === "rejected"
          ? "已驳回"
          : request.status === "cancelled"
            ? "已撤销"
            : "待完成",
    state: finalState,
    meta: request.status === "pending" ? `当前第 ${request.current_step} 级` : "",
  });

  const chart = el("div", { class: "flow-chart" });
  steps.forEach((step, index) => {
    chart.append(
      el("div", { class: `flow-node ${step.state}` }, [
        el("span", { class: "flow-dot" }, [
          step.state === "done" ? "✓" : step.state === "rejected" ? "!" : String(index + 1),
        ]),
        el("div", { class: "flow-copy" }, [
          el("strong", { text: step.title }),
          step.meta ? el("small", { text: step.meta }) : null,
          step.remark ? el("p", { text: step.remark }) : null,
        ]),
      ]),
    );
    if (index < steps.length - 1) {
      chart.append(el("span", { class: `flow-link ${step.state}` }));
    }
  });
  return chart;
}

export function renderTimeline(events) {
  if (!events?.length) return el("div", { class: "empty", text: "暂无流转记录" });
  const list = el("ol", { class: "flow-timeline" });
  for (const event of events) {
    list.append(
      el("li", { class: `timeline-event ${event.action}` }, [
        el("span", { class: "timeline-dot" }),
        el("div", { class: "timeline-copy" }, [
          el("div", { class: "timeline-head" }, [
            el("strong", { text: EVENT_LABEL[event.action] || event.action }),
            el("time", { text: new Date(event.created_at).toLocaleString("zh-CN") }),
          ]),
          el("p", { text: `${event.actor_name || "系统"}${event.detail ? " · " + event.detail : ""}` }),
        ]),
      ]),
    );
  }
  return list;
}
