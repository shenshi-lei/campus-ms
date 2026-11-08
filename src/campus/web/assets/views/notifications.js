import { api } from "../api.js";
import { el, fmt, icon, toast } from "../ui.js";
import { handleError } from "../core/state.js";
import { renderPager, renderTable } from "../components/table.js";

const KIND_LABEL = { approval: "审批", calendar: "日程", notice: "通知", system: "系统" };

export async function notificationsView(container) {
  const view = el("section", { class: "view-page" });
  const head = el("div", { class: "page-head" }, [
    el("div", {}, [
      el("h2", { text: "消息中心" }),
      el("p", { class: "muted", text: "审批待办、日程提醒与系统消息。" }),
    ]),
    el("div", { class: "actions" }, [
      el("button", {
        class: "btn",
        onclick: async () => {
          try {
            await api.post("/notifications/read-all");
            toast("已全部标记为已读");
            await reload();
          } catch (error) {
            handleError(error);
          }
        },
      }, [icon("check", 16), "全部已读"]),
    ]),
  ]);
  const unread = el("button", { class: "btn small", text: "仅看未读" });
  const tableHost = el("div", { class: "table-scroll" });
  const pager = el("div", { class: "pager" });
  const card = el("div", { class: "card list-card" }, [tableHost, el("div", { class: "list-footer" }, [pager])]);
  const params = { page: 1, page_size: 20, unread_only: false };
  let reload = async () => {};
  unread.addEventListener("click", () => {
    params.unread_only = !params.unread_only;
    unread.classList.toggle("primary", params.unread_only);
    params.page = 1;
    reload();
  });

  reload = async () => {
    tableHost.innerHTML = "";
    renderTable(tableHost, [], [], null, { loading: true });
    try {
      const data = await api.get(
        `/notifications?page=${params.page}&page_size=${params.page_size}&unread_only=${params.unread_only}`,
      );
      tableHost.innerHTML = "";
      renderTable(
        tableHost,
        [
          {
            label: "类型",
            render: (row) => el("span", { class: `tag ${row.kind}`, text: KIND_LABEL[row.kind] || row.kind }),
          },
          {
            label: "消息",
            render: (row) =>
              el("div", { class: "cell-main" }, [
                el("strong", { text: row.title, class: row.is_read ? "" : "unread-title" }),
                el("small", { class: "muted", text: row.body || "" }),
              ]),
          },
          { label: "时间", value: (row) => fmt.dateTime(row.created_at) },
          { label: "状态", render: (row) => el("span", { class: "muted", text: row.is_read ? "已读" : "未读" }) },
        ],
        data.items,
        (row) => [
          {
            label: row.is_read ? "查看" : "标记已读",
            onClick: async () => {
              try {
                if (!row.is_read) await api.post(`/notifications/${row.id}/read`);
                if (row.link) window.location.hash = row.link;
                else await reload();
                if (row.link) {
                  const target = row.link.replace(/^\//, "").split("?")[0];
                  if (target) window.dispatchEvent(new CustomEvent("campus:navigate", { detail: target }));
                }
              } catch (error) {
                handleError(error);
              }
            },
          },
        ],
        { emptyText: params.unread_only ? "没有未读消息" : "暂无消息" },
      );
      renderPager(pager, data, (page) => {
        params.page = page;
        reload();
      }, {
        onPageSize: (size) => {
          params.page_size = size;
          params.page = 1;
          reload();
        },
      });
    } catch (error) {
      tableHost.innerHTML = "";
      tableHost.append(el("div", { class: "panel error-panel" }, [el("h3", { text: "消息加载失败" }), el("p", { class: "muted", text: error?.message || "" })]));
      handleError(error);
    }
  };
  view.append(head, el("div", { class: "list-toolbar" }, [unread, el("span", { class: "spacer" })]), card);
  container.append(view);
  await reload();
}
