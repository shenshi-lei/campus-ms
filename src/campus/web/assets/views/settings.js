import { api } from "../api.js";
import { el, icon, toast } from "../ui.js";
import {
  classOptions,
  departmentOptions,
  handleError,
  state,
} from "../core/state.js";
import { confirmDialog, openForm, openModal } from "../components/modal.js";
import { openPersonPicker } from "../components/tree-select.js";
import { openExportDialog } from "../components/table.js";
import {
  accountPanel,
  departmentPanel,
  rolePermissionPanel,
  semesterPanel,
  subjectPanel,
} from "./legacy.js";

const ROLE_OPTIONS = [
  { value: "head_teacher", label: "班主任（按班级解析）" },
  { value: "student_affairs", label: "学工处" },
  { value: "academic_director", label: "教务主任" },
  { value: "admin", label: "管理员" },
  { value: "teacher", label: "教师" },
];
const APPLICANT_OPTIONS = [
  { value: "", label: "全部申请人" },
  { value: "student", label: "学生" },
  { value: "teacher", label: "教师" },
];
const LEAVE_TYPE_OPTIONS = [
  { value: "", label: "全部请假类型" },
  { value: "personal", label: "事假" },
  { value: "sick", label: "病假" },
  { value: "business", label: "公出" },
  { value: "compensatory", label: "调休" },
  { value: "bereavement", label: "婚丧" },
  { value: "maternity", label: "产假" },
  { value: "other", label: "其他" },
];

function sectionTitle(title, subtitle, actions = null) {
  return el("div", { class: "section-head" }, [
    el("div", {}, [el("h3", { text: title }), subtitle ? el("p", { class: "muted", text: subtitle }) : null]),
    actions,
  ]);
}

async function groupPanel(container) {
  container.innerHTML = "";
  const data = await api.get("/groups");
  const card = el("div", { class: "card list-card" });
  const table = el("div", { class: "table-scroll" });
  card.append(table);
  const reload = () => groupPanel(container);
  const rows = el("div", { class: "group-grid" });
  for (const group of data) {
    rows.append(
      el("article", { class: "group-card" }, [
        el("div", { class: "group-card-head" }, [
          el("div", {}, [
            el("h4", { text: group.name }),
            el("p", { class: "muted", text: `${group.code} · ${group.kind} · ${group.member_count} 人` }),
          ]),
          el("span", { class: `tag ${group.is_active ? "success" : "muted"}`, text: group.is_active ? "启用" : "停用" }),
        ]),
        el("p", { class: "muted small", text: group.description || "暂无描述" }),
        el("div", { class: "person-chips" }, group.members.slice(0, 8).map((member) =>
          el("span", { class: "person-chip", text: member.display_name }),
        )),
        el("div", { class: "group-card-actions" }, [
          el("button", { class: "btn small", text: "编辑", onclick: () => openGroupEditor(group, reload) }),
          el("button", {
            class: "btn small",
            text: "查看接收人",
            onclick: async () => {
              try {
                const expanded = await api.get(`/groups/${group.id}/expand`);
                toast(`实际接收人 ${expanded.user_count} 人`);
              } catch (error) {
                handleError(error);
              }
            },
          }),
          el("button", {
            class: "btn small danger",
            text: "删除",
            onclick: async () => {
              if (!(await confirmDialog({ title: "删除群组", message: `确定删除「${group.name}」吗？`, danger: true }))) return;
              try {
                await api.del(`/groups/${group.id}`);
                toast("已删除");
                await reload();
              } catch (error) {
                handleError(error);
              }
            },
          }),
        ]),
      ]),
    );
  }
  if (!data.length) rows.append(el("div", { class: "empty", text: "还没有群组" }));
  table.append(
    sectionTitle("群组管理", "从组织树选择人员，用于通知、审批和日程。", el("button", {
      class: "btn primary",
      onclick: () => openGroupEditor(null, reload),
    }, [icon("plus", 16), "新建群组"])),
    rows,
  );
  container.append(card);
}

function openGroupEditor(group, reload) {
  const members = (group?.members || []).map((item) => ({
    member_type: item.member_type,
    member_id: item.member_id,
    display_name: item.display_name,
  }));
  const code = el("input", { class: "input", value: group?.code || "", disabled: Boolean(group) });
  const name = el("input", { class: "input", value: group?.name || "" });
  const description = el("input", { class: "input", value: group?.description || "" });
  const kind = el("input", { class: "input", value: group?.kind || "custom" });
  const active = el("select", { class: "input" }, [
    el("option", { value: "true", text: "启用" }),
    el("option", { value: "false", text: "停用" }),
  ]);
  active.value = group?.is_active === false ? "false" : "true";
  const memberBox = el("div", { class: "person-chips" });
  const renderMembers = () => {
    memberBox.innerHTML = "";
    if (!members.length) memberBox.append(el("span", { class: "muted", text: "尚未添加成员" }));
    for (const member of members) {
      memberBox.append(
        el("span", { class: "person-chip" }, [
          el("span", { text: member.display_name }),
          el("button", {
            type: "button",
            onclick: () => {
              members.splice(members.indexOf(member), 1);
              renderMembers();
            },
          }, [icon("close", 12)]),
        ]),
      );
    }
  };
  renderMembers();
  const addPeople = async (personType) => {
    const result = await openPersonPicker({ title: `选择${personType === "student" ? "学生" : "教师"}`, multiple: true, personType });
    if (!result) return;
    for (const item of result) {
      members.push({ member_type: personType, member_id: item.id, display_name: item.label });
    }
    renderMembers();
  };
  const addClass = async () => {
    const select = el("select", { class: "input" }, classOptions().map((item) => el("option", { value: String(item.value), text: item.label })));
    const dialog = openModal({
      title: "添加班级",
      size: "sm",
      body: el("label", { class: "field" }, [el("span", { text: "班级" }), select]),
      footer: el("div", { class: "modal-actions" }, [
        el("button", { class: "btn", text: "取消", onclick: () => dialog.close() }),
        el("button", {
          class: "btn primary",
          text: "添加",
          onclick: () => {
            const id = Number(select.value);
            const row = classOptions().find((item) => Number(item.value) === id);
            if (row) members.push({ member_type: "class", member_id: id, display_name: row.label });
            renderMembers();
            dialog.close();
          },
        }),
      ]),
    });
  };
  const addDepartment = async () => {
    const select = el("select", { class: "input" }, departmentOptions().map((item) => el("option", { value: String(item.value), text: item.label })));
    const dialog = openModal({
      title: "添加院系",
      size: "sm",
      body: el("label", { class: "field" }, [el("span", { text: "院系/处室" }), select]),
      footer: el("div", { class: "modal-actions" }, [
        el("button", { class: "btn", text: "取消", onclick: () => dialog.close() }),
        el("button", {
          class: "btn primary",
          text: "添加",
          onclick: () => {
            const id = Number(select.value);
            const row = departmentOptions().find((item) => Number(item.value) === id);
            if (row) members.push({ member_type: "department", member_id: id, display_name: row.label });
            renderMembers();
            dialog.close();
          },
        }),
      ]),
    });
  };
  const form = el("div", { class: "form-grid cols-2" }, [
    el("label", { class: "field" }, [el("span", { text: "编码" }), code]),
    el("label", { class: "field" }, [el("span", { text: "名称" }), name]),
    el("label", { class: "field" }, [el("span", { text: "分类" }), kind]),
    el("label", { class: "field" }, [el("span", { text: "状态" }), active]),
    el("label", { class: "field span-full" }, [el("span", { text: "描述" }), description]),
    el("div", { class: "field span-full" }, [
      el("span", { text: "成员" }),
      el("div", { class: "toolbar" }, [
        el("button", { type: "button", class: "btn small", text: "添加学生", onclick: () => addPeople("student") }),
        el("button", { type: "button", class: "btn small", text: "添加教师", onclick: () => addPeople("teacher") }),
        el("button", { type: "button", class: "btn small", text: "添加班级", onclick: addClass }),
        el("button", { type: "button", class: "btn small", text: "添加院系", onclick: addDepartment }),
      ]),
      memberBox,
    ]),
  ]);
  const dialog = openModal({
    title: group ? "编辑群组" : "新建群组",
    size: "lg",
    body: form,
    footer: el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "取消", onclick: () => dialog.close() }),
      el("button", {
        class: "btn primary",
        text: "保存",
        onclick: async () => {
          if (!code.value.trim() || !name.value.trim()) {
            toast("编码和名称不能为空", "error");
            return;
          }
          const payload = {
            code: code.value.trim(),
            name: name.value.trim(),
            description: description.value.trim(),
            kind: kind.value.trim() || "custom",
            is_active: active.value === "true",
            members: members.map(({ member_type, member_id }) => ({ member_type, member_id })),
          };
          try {
            if (group) await api.patch(`/groups/${group.id}`, payload);
            else await api.post("/groups", payload);
            toast("群组已保存");
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

async function flowPanel(container) {
  container.innerHTML = "";
  const [flows, groups] = await Promise.all([api.get("/leaves/flows"), api.get("/groups")]);
  const reload = () => flowPanel(container);
  const card = el("div", { class: "card list-card" });
  card.append(
    sectionTitle("请假审批流程", "按申请人类型、请假类型与天数区间匹配，节点支持角色、班主任、指定人和群组。", el("button", {
      class: "btn primary",
      onclick: () => openFlowEditor(null, groups, reload),
    }, [icon("plus", 16), "新建流程"])),
  );
  const list = el("div", { class: "flow-config-list" });
  for (const flow of flows) {
    list.append(
      el("article", { class: "flow-config-card" }, [
        el("div", { class: "flow-config-head" }, [
          el("div", {}, [
            el("h4", { text: flow.name }),
            el("p", { class: "muted", text: `${flow.code} · ${flow.applicant_type || "全部申请人"} · ${flow.leave_type || "全部类型"} · ${flow.min_days}${flow.max_days !== null ? `-${flow.max_days}` : "+"} 天` }),
          ]),
          el("span", { class: `tag ${flow.is_active ? "success" : "muted"}`, text: flow.is_active ? "启用" : "停用" }),
        ]),
        el("div", { class: "flow-chain" }, flow.steps.flatMap((step, index) => [
          el("span", { class: "flow-chip" }, [
            el("strong", { text: step.name }),
            el("small", { text: approverLabel(step) }),
          ]),
          index < flow.steps.length - 1 ? el("span", { class: "flow-arrow", text: "→" }) : null,
        ])),
        el("div", { class: "group-card-actions" }, [
          el("button", { class: "btn small", text: "编辑", onclick: () => openFlowEditor(flow, groups, reload) }),
          el("button", {
            class: "btn small",
            text: flow.is_active ? "停用" : "启用",
            onclick: async () => {
              try {
                await api.patch(`/leaves/flows/${flow.id}`, { is_active: !flow.is_active });
                toast("已更新");
                await reload();
              } catch (error) {
                handleError(error);
              }
            },
          }),
          el("button", {
            class: "btn small danger",
            text: "删除",
            onclick: async () => {
              if (!(await confirmDialog({ title: "删除流程", message: "删除后不可恢复，确定继续？", danger: true }))) return;
              try {
                await api.del(`/leaves/flows/${flow.id}`);
                toast("已删除");
                await reload();
              } catch (error) {
                handleError(error);
              }
            },
          }),
        ]),
      ]),
    );
  }
  if (!flows.length) list.append(el("div", { class: "empty", text: "还没有流程" }));
  card.append(list);
  container.append(card);
}

function approverLabel(step) {
  if (step.approver_type === "head_teacher") return "班主任";
  if (step.approver_type === "user") return step.user_name || "指定人员";
  if (step.approver_type === "group") return step.group_name || "群组";
  const role = ROLE_OPTIONS.find((item) => item.value === step.role_code);
  return role?.label || step.role_code || "角色";
}

function openFlowEditor(flow, groups, reload) {
  const code = el("input", { class: "input", value: flow?.code || "", disabled: Boolean(flow) });
  const name = el("input", { class: "input", value: flow?.name || "" });
  const applicant = el("select", { class: "input" }, APPLICANT_OPTIONS.map((item) => el("option", { value: item.value, text: item.label })));
  const leaveType = el("select", { class: "input" }, LEAVE_TYPE_OPTIONS.map((item) => el("option", { value: item.value, text: item.label })));
  const minDays = el("input", { class: "input", type: "number", step: "0.5", value: flow?.min_days ?? 0 });
  const maxDays = el("input", { class: "input", type: "number", step: "0.5", value: flow?.max_days ?? "" });
  const priority = el("input", { class: "input", type: "number", value: flow?.priority ?? 0 });
  const active = el("select", { class: "input" }, [
    el("option", { value: "true", text: "启用" }),
    el("option", { value: "false", text: "停用" }),
  ]);
  const description = el("input", { class: "input", value: flow?.description || "" });
  applicant.value = flow?.applicant_type || "";
  leaveType.value = flow?.leave_type || "";
  active.value = flow?.is_active === false ? "false" : "true";
  const stepsHost = el("div", { class: "flow-steps-editor" });
  const steps = (flow?.steps || []).map((item) => ({ ...item }));
  if (!steps.length) steps.push({ step_no: 1, name: "班主任审批", approver_type: "head_teacher", role_code: "head_teacher" });
  const addStep = () => {
    steps.push({ step_no: steps.length + 1, name: `第 ${steps.length + 1} 级审批`, approver_type: "role", role_code: "student_affairs" });
    renderSteps();
  };
  const renderSteps = () => {
    stepsHost.innerHTML = "";
    steps.forEach((step, index) => {
      step.step_no = index + 1;
      const type = el("select", { class: "input" }, [
        el("option", { value: "head_teacher", text: "班主任" }),
        el("option", { value: "role", text: "角色" }),
        el("option", { value: "user", text: "指定人员" }),
        el("option", { value: "group", text: "群组" }),
      ]);
      type.value = step.approver_type || "role";
      const role = el("select", { class: "input" }, ROLE_OPTIONS.map((item) => el("option", { value: item.value, text: item.label })));
      role.value = step.role_code || "student_affairs";
      const person = el("button", { class: "btn small", text: step.user_name || "选择人员" });
      let userId = step.user_id || null;
      person.addEventListener("click", async () => {
        const result = await openPersonPicker({ title: "选择审批人", multiple: false, personType: "teacher" });
        if (result?.length) {
          userId = result[0].id;
          person.textContent = result[0].label;
        }
      });
      const group = el("select", { class: "input" }, groups.map((item) => el("option", { value: String(item.id), text: item.name })));
      group.value = String(step.group_id || groups[0]?.id || "");
      const nameInput = el("input", { class: "input", value: step.name || "" });
      const holder = el("div", { class: "flow-step-row" }, [
        el("span", { class: "step-index", text: String(index + 1) }),
        nameInput,
        type,
        el("div", { class: "step-approver" }, [role, person, group]),
        el("button", {
          class: "btn small danger",
          text: "移除",
          onclick: () => {
            if (steps.length <= 1) {
              toast("至少保留一个节点", "error");
              return;
            }
            steps.splice(index, 1);
            renderSteps();
          },
        }),
      ]);
      const toggle = () => {
        role.style.display = type.value === "role" ? "" : "none";
        person.style.display = type.value === "user" ? "" : "none";
        group.style.display = type.value === "group" ? "" : "none";
      };
      type.addEventListener("change", () => {
        step.approver_type = type.value;
        toggle();
      });
      nameInput.addEventListener("input", () => { step.name = nameInput.value; });
      role.addEventListener("change", () => { step.role_code = role.value; });
      group.addEventListener("change", () => { step.group_id = Number(group.value) || null; });
      holder._read = () => ({
        step_no: index + 1,
        name: nameInput.value.trim() || `第 ${index + 1} 级审批`,
        approver_type: type.value,
        role_code: type.value === "role" ? role.value : type.value === "head_teacher" ? "head_teacher" : null,
        user_id: type.value === "user" ? userId : null,
        group_id: type.value === "group" ? Number(group.value) || null : null,
      });
      stepsHost.append(holder);
      toggle();
    });
    stepsHost.append(el("button", { class: "btn small", text: "+ 添加节点", onclick: addStep }));
  };
  renderSteps();
  const form = el("div", { class: "form-grid cols-2" }, [
    el("label", { class: "field" }, [el("span", { text: "编码" }), code]),
    el("label", { class: "field" }, [el("span", { text: "名称" }), name]),
    el("label", { class: "field" }, [el("span", { text: "申请人" }), applicant]),
    el("label", { class: "field" }, [el("span", { text: "请假类型" }), leaveType]),
    el("label", { class: "field" }, [el("span", { text: "最小天数" }), minDays]),
    el("label", { class: "field" }, [el("span", { text: "最大天数（留空不限）" }), maxDays]),
    el("label", { class: "field" }, [el("span", { text: "优先级" }), priority]),
    el("label", { class: "field" }, [el("span", { text: "状态" }), active]),
    el("label", { class: "field span-full" }, [el("span", { text: "描述" }), description]),
    el("div", { class: "field span-full" }, [el("span", { text: "审批节点" }), stepsHost]),
  ]);
  const dialog = openModal({
    title: flow ? "编辑流程" : "新建流程",
    size: "xl",
    body: form,
    footer: el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "取消", onclick: () => dialog.close() }),
      el("button", {
        class: "btn primary",
        text: "保存",
        onclick: async () => {
          const payload = {
            code: code.value.trim(),
            name: name.value.trim(),
            applicant_type: applicant.value || null,
            leave_type: leaveType.value || null,
            min_days: Number(minDays.value || 0),
            max_days: maxDays.value === "" ? null : Number(maxDays.value),
            priority: Number(priority.value || 0),
            is_active: active.value === "true",
            description: description.value.trim(),
            steps: stepsHost.querySelectorAll(".flow-step-row").length
              ? [...stepsHost.querySelectorAll(".flow-step-row")].map((row) => row._read())
              : [],
          };
          if (!payload.code || !payload.name) {
            toast("编码和名称不能为空", "error");
            return;
          }
          try {
            if (flow) await api.patch(`/leaves/flows/${flow.id}`, payload);
            else await api.post("/leaves/flows", payload);
            toast("流程已保存");
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

async function periodPanel(container) {
  container.innerHTML = "";
  const periods = await api.get("/settings/periods");
  const rows = el("div", { class: "period-editor" });
  const inputs = [];
  for (const period of periods) {
    const start = el("input", { class: "input", value: period.start });
    const end = el("input", { class: "input", value: period.end });
    inputs.push({ no: period.no, start, end });
    rows.append(
      el("div", { class: "period-row" }, [
        el("strong", { text: `第 ${period.no} 节` }),
        start,
        el("span", { class: "muted", text: "至" }),
        end,
      ]),
    );
  }
  const card = el("div", { class: "card list-card" });
  card.append(
    sectionTitle("节次时间", "用于课表日/周视图展示。", el("button", {
      class: "btn primary",
      text: "保存",
      onclick: async () => {
        const value = JSON.stringify(inputs.map((item) => ({ no: item.no, start: item.start.value, end: item.end.value })));
        try {
          await api.request("PUT", "/settings/period_times", { value, description: "节次时间" });
          toast("已保存");
        } catch (error) {
          handleError(error);
        }
      },
    })),
    rows,
  );
  container.append(card);
}

function exportPanel(container) {
  container.innerHTML = "";
  const resources = [
    ["students", "学生", "student:read"],
    ["teachers", "教师", "teacher:read"],
    ["courses", "课程", "course:read"],
    ["classes", "班级", "class:read"],
    ["enrollments", "选课", "enrollment:read"],
    ["scores", "成绩", "score:read"],
    ["attendance", "考勤", "attendance:read"],
    ["leaves", "请假", "leave:read"],
    ["fees", "缴费", "fee:read"],
    ["schedules", "课表", "schedule:read"],
    ["audit", "审计", "audit:read"],
  ];
  const grid = el("div", { class: "group-grid" });
  for (const [resource, label, permission] of resources) {
    if (!state.permissions.has(permission)) continue;
    grid.append(
      el("article", { class: "group-card" }, [
        el("div", { class: "group-card-head" }, [
          el("div", {}, [el("h4", { text: `${label}数据` })]),
          el("span", { class: "muted small", text: resource }),
        ]),
        el("p", { class: "muted small", text: "支持 CSV、Excel 与 PDF；导出范围与当前权限一致。" }),
        el("div", { class: "group-card-actions" }, [
          el("button", {
            class: "btn small primary",
            text: "导出",
            onclick: () => openExportDialog({ resource, params: {} }),
          }),
          ...(["students", "teachers", "courses"].includes(resource)
            ? [el("button", {
                class: "btn small",
                text: "下载模板",
                onclick: () =>
                  api
                    .download(`/transfer/template/${resource}`, `${resource}-template.csv`)
                    .catch(handleError),
              })]
            : []),
        ]),
      ]),
    );
  }
  const card = el("div", { class: "card list-card" });
  card.append(
    sectionTitle(
      "导入导出中心",
      "下载中文文件名已做 UTF-8 处理；导入支持预览、校验与错误行反馈。",
    ),
    grid,
    el("p", { class: "muted small", text: "导入入口位于各列表页右上角「导入」按钮。" }),
  );
  container.append(card);
}

export async function settingsView(container) {
  const sections = [
    ["roles", "角色权限", "settings", rolePermissionPanel],
    ["accounts", "账号", "user", accountPanel],
    ["groups", "群组", "students", groupPanel],
    ["flows", "请假流程", "clock", flowPanel],
    ["departments", "院系", "classes", departmentPanel],
    ["subjects", "学科", "book", subjectPanel],
    ["semesters", "学期", "calendar", semesterPanel],
    ["periods", "节次时间", "clock", periodPanel],
    ["export", "导入导出", "download", exportPanel],
  ];
  let current = "roles";
  const view = el("section", { class: "view-page settings-page" });
  const head = el("div", { class: "page-head" }, [
    el("div", {}, [
      el("h2", { text: "系统设置" }),
      el("p", { class: "muted", text: "组织、权限、群组、审批流程与系统参数。" }),
    ]),
  ]);
  const layout = el("div", { class: "settings-layout" });
  const nav = el("aside", { class: "settings-nav" });
  const content = el("div", { class: "settings-content" });
  const buttons = [];
  for (const [key, label, iconName, render] of sections) {
    const button = el("button", { class: key === current ? "active" : "" }, [icon(iconName, 16), label]);
    button.addEventListener("click", async () => {
      current = key;
      buttons.forEach((item) => item.classList.toggle("active", item === button));
      content.innerHTML = "";
      try {
        await render(content);
      } catch (error) {
        handleError(error);
      }
    });
    buttons.push(button);
    nav.append(button);
  }
  layout.append(nav, content);
  view.append(head, layout);
  container.append(view);
  await rolePermissionPanel(content);
}
