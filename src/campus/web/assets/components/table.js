import { api } from "../api.js";
import { debounce, el, emptyBlock, icon, toast } from "../ui.js";
import { handleError } from "../core/state.js";
import { openModal } from "./modal.js";

export function renderTable(container, columns, rows, rowActions, options = {}) {
  container.innerHTML = "";
  const wrap = el("div", { class: "table-wrap" });
  const table = el("table", { class: `table ${options.compact ? "compact" : ""}` });
  const head = el(
    "tr",
    {},
    columns.map((column) =>
      el("th", {
        text: column.label,
        style: column.width ? `width:${column.width}` : null,
        class: column.align ? `align-${column.align}` : "",
      }),
    ),
  );
  if (rowActions) head.append(el("th", { class: "actions-col", text: "操作" }));
  table.append(el("thead", {}, [head]));
  const body = el("tbody");
  if (options.loading) {
    body.append(
      el(
        "tr",
        {},
        el("td", { colspan: columns.length + (rowActions ? 1 : 0) }, [
          el("div", { class: "table-loading" }, [
            el("div", { class: "spinner" }),
            el("span", { text: "加载中…" }),
          ]),
        ]),
      ),
    );
  } else if (!rows.length) {
    body.append(
      el(
        "tr",
        { class: "empty-row" },
        el("td", { colspan: columns.length + (rowActions ? 1 : 0) }, [
          emptyBlock(options.emptyText || "暂无数据"),
        ]),
      ),
    );
  } else {
    for (const row of rows) {
      const cells = columns.map((column) => {
        if (column.render) {
          return el("td", { class: column.align ? `align-${column.align}` : "" }, [
            column.render(row),
          ]);
        }
        return el(
          "td",
          {
            class: column.align ? `align-${column.align}` : "",
            title: column.tooltip ? String(column.tooltip(row) ?? "") : null,
          },
          [String(column.value(row) ?? "-")],
        );
      });
      if (rowActions) {
        const actions = rowActions(row) || [];
        cells.push(
          el(
            "td",
            { class: "row-actions" },
            actions.map((action) =>
              el("button", {
                class: "btn small" + (action.danger ? " danger" : ""),
                text: action.label,
                onclick: action.onClick,
              }),
            ),
          ),
        );
      }
      const tr = el("tr", {}, cells);
      if (options.onRow) {
        tr.classList.add("clickable-row");
        tr.addEventListener("click", (event) => {
          if (event.target.closest("button")) return;
          options.onRow(row);
        });
      }
      body.append(tr);
    }
  }
  table.append(body);
  wrap.append(table);
  container.append(wrap);
}

function pageWindow(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1);
  const pages = new Set([1, total, current, current - 1, current + 1, current - 2, current + 2]);
  const list = [...pages].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b);
  const result = [];
  let previous = 0;
  for (const page of list) {
    if (previous && page - previous > 1) result.push("...");
    result.push(page);
    previous = page;
  }
  return result;
}

export function renderPager(container, data, go, options = {}) {
  container.innerHTML = "";
  const total = Number(data.total || 0);
  const pageSize = Number(data.page_size || 20);
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(Math.max(1, Number(data.page || 1)), pages);
  const sizes = options.pageSizes || [10, 20, 50, 100];

  const sizeSelect = el(
    "select",
    { class: "pager-size", "aria-label": "每页条数" },
    sizes.map((size) => el("option", { value: String(size), text: `${size} 条/页` })),
  );
  sizeSelect.value = String(pageSize);
  sizeSelect.addEventListener("change", () => {
    if (options.onPageSize) options.onPageSize(Number(sizeSelect.value));
    else go(1, Number(sizeSelect.value));
  });

  const first = el("button", {
    class: "btn small page-btn",
    text: "«",
    title: "首页",
    onclick: () => go(1),
  });
  const prev = el("button", {
    class: "btn small page-btn",
    text: "‹",
    title: "上一页",
    onclick: () => go(Math.max(1, current - 1)),
  });
  first.disabled = current <= 1;
  prev.disabled = current <= 1;

  const numbers = el("div", { class: "page-numbers" });
  for (const item of pageWindow(current, pages)) {
    if (item === "...") {
      numbers.append(el("span", { class: "page-ellipsis", text: "…" }));
    } else {
      numbers.append(
        el("button", {
          class: `btn small page-btn ${item === current ? "active" : ""}`,
          text: String(item),
          onclick: () => go(item),
        }),
      );
    }
  }

  const next = el("button", {
    class: "btn small page-btn",
    text: "›",
    title: "下一页",
    onclick: () => go(Math.min(pages, current + 1)),
  });
  const last = el("button", {
    class: "btn small page-btn",
    text: "»",
    title: "末页",
    onclick: () => go(pages),
  });
  next.disabled = current >= pages;
  last.disabled = current >= pages;

  const jump = el("input", {
    class: "page-jump",
    type: "number",
    min: "1",
    max: String(pages),
    placeholder: "页码",
    "aria-label": "跳转页码",
  });
  const jumpButton = el("button", {
    class: "btn small",
    text: "跳转",
    onclick: () => {
      const target = Number(jump.value);
      if (Number.isFinite(target)) go(Math.min(Math.max(1, target), pages));
    },
  });
  jump.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      jumpButton.click();
    }
  });

  container.append(
    el("div", { class: "pager-total" }, [
      el("span", { text: "共 " }),
      el("strong", { text: String(total) }),
      el("span", { text: " 条" }),
    ]),
    el("div", { class: "pager-right" }, [
      sizeSelect,
      el("div", { class: "pager-controls" }, [first, prev, numbers, next, last]),
      el("div", { class: "pager-jump" }, [el("span", { text: "前往" }), jump, el("span", { text: "页" }), jumpButton]),
    ]),
  );
}

function filterControl(filter, params, reload) {
  if (filter.type === "select") {
    const select = el(
      "select",
      { class: "filter-select", "aria-label": filter.label },
      [{ value: "", label: filter.placeholder || `全部${filter.label}` }, ...(filter.options || [])].map(
        (item) => el("option", { value: String(item.value), text: item.label }),
      ),
    );
    if (params[filter.name] !== undefined && params[filter.name] !== null) {
      select.value = String(params[filter.name]);
    }
    select.addEventListener("change", () => {
      params[filter.name] = select.value || "";
      params.page = 1;
      reload();
    });
    return select;
  }
  if (filter.type === "date") {
    const input = el("input", { class: "filter-date", type: "date", "aria-label": filter.label });
    input.addEventListener("change", () => {
      params[filter.name] = input.value;
      params.page = 1;
      reload();
    });
    return input;
  }
  const input = el("input", {
    class: "filter-input",
    type: "search",
    placeholder: filter.placeholder || filter.label,
    "aria-label": filter.label,
  });
  const apply = debounce(() => {
    params[filter.name] = input.value.trim();
    params.page = 1;
    reload();
  }, 300);
  input.addEventListener("input", apply);
  return input;
}

export function openExportDialog({ resource, params, filename = "" }) {
  const format = el("select", { class: "input" }, [
    el("option", { value: "csv", text: "CSV（兼容 Excel）" }),
    el("option", { value: "xlsx", text: "Excel（.xlsx）" }),
    el("option", { value: "pdf", text: "PDF（打印版）" }),
  ]);
  const dialog = openModal({
    title: "导出数据",
    subtitle: "导出范围与当前筛选条件一致",
    size: "sm",
    body: el("label", { class: "field" }, [el("span", { text: "文件格式" }), format]),
    footer: el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "取消", onclick: () => dialog.close() }),
      el("button", {
        class: "btn primary",
        text: "开始导出",
        onclick: () => {
          const query = new URLSearchParams({ fmt: format.value });
          if (params.keyword) query.set("keyword", params.keyword);
          const name = filename || `${resource}-${new Date().toISOString().slice(0, 10)}`;
          api
            .download(
              `/transfer/export/resource/${resource}?${query.toString()}`,
              `${name}.${format.value}`,
            )
            .catch(handleError);
          dialog.close();
        },
      }),
    ]),
  });
}

export function openImportDialog({ resource, title = "批量导入", templatePath = "" }) {
  const file = el("input", { type: "file", accept: ".csv,text/csv" });
  const textarea = el("textarea", {
    class: "input import-textarea",
    rows: "10",
    placeholder: "粘贴 CSV 内容，或选择文件后自动填充",
  });
  const hint = el("p", {
    class: "muted",
    text: "第一行为表头；系统会校验必填字段并返回失败行。",
  });
  file.addEventListener("change", async () => {
    const selected = file.files?.[0];
    if (selected) textarea.value = await selected.text();
  });
  const body = el("div", { class: "import-body" }, [hint, file, textarea]);
  if (templatePath) {
    body.append(
      el("button", {
        class: "btn small",
        text: "下载导入模板",
        onclick: () => api.download(templatePath, `${resource}-template.csv`),
      }),
    );
  }
  const dialog = openModal({
    title,
    size: "lg",
    body,
    footer: el("div", { class: "modal-actions" }, [
      el("button", { class: "btn", text: "取消", onclick: () => dialog.close() }),
      el("button", {
        class: "btn primary",
        text: "开始导入",
        onclick: async () => {
          try {
            const result = await api.post(`/transfer/import/${resource}`, { csv: textarea.value });
            toast(`导入完成：新增 ${result.created}，更新 ${result.updated}`);
            if (result.errors?.length) {
              dialog.body.append(
                el("div", { class: "import-errors" }, [
                  el("h4", { text: `失败 ${result.errors.length} 行` }),
                  el("pre", { text: result.errors.join("\n") }),
                ]),
              );
            } else {
              dialog.close();
            }
          } catch (error) {
            handleError(error);
          }
        },
      }),
    ]),
  });
  return dialog;
}

export async function crudView(container, config) {
  const params = {
    page: 1,
    page_size: config.pageSize || 20,
    keyword: "",
    ...(config.params || {}),
  };
  const view = el("section", { class: "view-page" });
  const head = el("div", { class: "page-head" }, [
    el("div", {}, [
      el("h2", { text: config.title }),
      config.subtitle ? el("p", { class: "muted", text: config.subtitle }) : null,
    ]),
  ]);
  const toolbar = el("div", { class: "list-toolbar" });
  const filterWrap = el("div", { class: "filter-wrap" });
  const filterNodes = [];
  let searchInput = null;
  const card = el("div", { class: "card list-card" });
  const tableHost = el("div", { class: "table-scroll" });
  const footer = el("div", { class: "list-footer" });
  const pager = el("div", { class: "pager" });
  card.append(tableHost, footer);
  footer.append(pager);
  let reload = async () => {};

  if (config.search) {
    const input = el("input", {
      class: "search",
      type: "search",
      placeholder: config.search,
      "aria-label": "搜索",
    });
    const apply = debounce(() => {
      params.keyword = input.value.trim();
      params.page = 1;
      reload();
    }, 300);
    searchInput = input;
    input.addEventListener("input", apply);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        apply();
      }
    });
    toolbar.append(el("div", { class: "search-group" }, [el("span", { class: "search-icon" }, [icon("search", 16)]), input]));
  }
  if (config.filters?.length) {
    for (const filter of config.filters) {
      const node = filterControl(filter, params, () => reload());
      filterNodes.push(node);
      filterWrap.append(node);
    }
    filterWrap.append(
      el("button", {
        class: "btn small ghost",
        text: "重置筛选",
        onclick: () => {
          for (const filter of config.filters) params[filter.name] = "";
          for (const node of filterNodes) {
            if (node.tagName === "SELECT" || node.tagName === "INPUT") node.value = "";
          }
          if (searchInput) searchInput.value = "";
          params.keyword = "";
          params.page = 1;
          reload();
        },
      }),
    );
    toolbar.append(filterWrap);
  }
  toolbar.append(el("span", { class: "spacer" }));
  if (config.actions) {
    const actions = config.actions(() => reload());
    if (actions?.length) toolbar.append(el("div", { class: "actions" }, actions));
  }
  if (config.exportResource) {
    toolbar.append(
      el("button", {
        class: "btn",
        onclick: () =>
          openExportDialog({
            resource: config.exportResource,
            params,
            filename: config.exportFilename,
          }),
      }, [icon("download", 16), "导出"]),
    );
  }
  if (config.export) {
    const exportSpec = config.export;
    toolbar.append(
      el("button", {
        class: "btn",
        onclick: () => {
          const path =
            typeof exportSpec === "function" ? exportSpec(params) : exportSpec.path || exportSpec;
          const filename =
            (typeof exportSpec === "object" && exportSpec.filename) ||
            `${config.title || "export"}-${new Date().toISOString().slice(0, 10)}.csv`;
          api.download(path, filename).catch(handleError);
        },
      }, [icon("download", 16), "导出"]),
    );
  }
  if (config.import) {
    toolbar.append(
      el("button", {
        class: "btn",
        onclick: () =>
          openImportDialog({
            resource: config.import.resource,
            templatePath: config.import.templatePath,
          }),
      }, [icon("plus", 16), "导入"]),
    );
  }

  reload = async () => {
    tableHost.innerHTML = "";
    renderTable(tableHost, config.columns, [], config.rowActions ? (row) => config.rowActions(row, () => reload()) : null, {
      loading: true,
    });
    try {
      const data = await config.list(params);
      tableHost.innerHTML = "";
      renderTable(
        tableHost,
        config.columns,
        data.items,
        config.rowActions ? (row) => config.rowActions(row, () => reload()) : null,
        { emptyText: config.emptyText, onRow: config.onRow },
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
          el("h3", { text: "加载失败" }),
          el("p", { class: "muted", text: error?.message || "未知错误" }),
          el("button", { class: "btn primary", text: "重试", onclick: () => reload() }),
        ]),
      );
      handleError(error);
    }
  };

  view.append(head, toolbar, card);
  container.append(view);
  await reload();
  return { reload, params };
}
