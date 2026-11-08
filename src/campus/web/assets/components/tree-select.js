import { api } from "../api.js";
import { el, icon } from "../ui.js";

function flatten(nodes, result = []) {
  for (const node of nodes) {
    result.push(node);
    if (node.children?.length) flatten(node.children, result);
  }
  return result;
}

function matches(node, keyword) {
  if (!keyword) return true;
  if (`${node.label} ${node.subtitle}`.includes(keyword)) return true;
  return (node.children || []).some((child) => matches(child, keyword));
}

function renderNode(node, state, depth) {
  const hasChildren = Boolean(node.children?.length);
  const expanded = state.expanded.has(node.key);
  const row = el("div", { class: "tree-row", style: `padding-left:${depth * 16 + 6}px` });
  if (hasChildren) {
    row.append(
      el(
        "button",
        {
          type: "button",
          class: "tree-toggle",
          onclick: () => {
            if (expanded) state.expanded.delete(node.key);
            else state.expanded.add(node.key);
            state.rerender();
          },
        },
        [icon(expanded ? "chevronDown" : "chevronRight", 14)],
      ),
    );
  } else {
    row.append(el("span", { class: "tree-toggle placeholder" }));
  }
  if (node.selectable) {
    const checked = state.selected.has(Number(node.key.split(":")[1]));
    const box = el("input", { type: "checkbox" });
    box.checked = checked;
    box.addEventListener("change", () => {
      const id = Number(node.key.split(":")[1]);
      if (box.checked) state.selected.set(id, node);
      else state.selected.delete(id);
      state.rerender();
    });
    row.append(box);
  } else {
    row.append(el("span", { class: "tree-dot" }));
  }
  row.append(
    el("button", {
      type: "button",
      class: "tree-label",
      onclick: () => {
        if (hasChildren) {
          if (expanded) state.expanded.delete(node.key);
          else state.expanded.add(node.key);
          state.rerender();
        } else if (node.selectable) {
          const id = Number(node.key.split(":")[1]);
          if (state.selected.has(id)) state.selected.delete(id);
          else state.selected.set(id, node);
          state.rerender();
        }
      },
    }, [
      el("span", { text: node.label }),
      node.subtitle ? el("small", { text: node.subtitle }) : null,
      node.count ? el("em", { class: "tree-count", text: String(node.count) }) : null,
    ]),
  );
  return row;
}

function renderTree(nodes, state, keyword, depth = 0) {
  const holder = el("div", { class: "tree-level" });
  for (const node of nodes) {
    if (!matches(node, keyword)) continue;
    holder.append(renderNode(node, state, depth));
    if (node.children?.length && (state.expanded.has(node.key) || keyword)) {
      holder.append(renderTree(node.children, state, keyword, depth + 1));
    }
  }
  return holder;
}

export function openPersonPicker({
  title = "选择人员",
  multiple = false,
  personType = "student",
  value = null,
  types = null,
} = {}) {
  return new Promise((resolve) => {
    const selected = new Map();
    const expanded = new Set();
    const overlay = el("div", { class: "overlay" });
    const modal = el("div", { class: "modal modal-lg person-modal" });
    const tree = el("div", { class: "tree-panel" });
    const chips = el("div", { class: "person-chips" });
    const search = el("input", {
      class: "input",
      type: "search",
      placeholder: "搜索姓名、学号、工号或班级",
    });
    const count = el("span", { class: "muted" });
    const state = {
      selected,
      expanded,
      rerender: () => {
        tree.innerHTML = "";
        tree.append(renderTree(nodes, state, search.value.trim()));
        chips.innerHTML = "";
        if (!selected.size) {
          chips.append(el("span", { class: "muted", text: "尚未选择" }));
        } else {
          for (const [id, node] of selected) {
            chips.append(
              el("span", { class: "person-chip" }, [
                el("span", { text: node.label }),
                el("button", {
                  type: "button",
                  title: "移除",
                  onclick: () => {
                    selected.delete(id);
                    state.rerender();
                  },
                }, [icon("close", 12)]),
              ]),
            );
          }
        }
        count.textContent = `已选 ${selected.size} 人`;
      },
    };
    let nodes = [];
    const close = (result = null) => {
      overlay.remove();
      resolve(result);
    };
    const footer = el("div", { class: "modal-actions" }, [
      count,
      el("span", { class: "spacer" }),
      el("button", { class: "btn", text: "取消", onclick: () => close(null) }),
      el("button", {
        class: "btn primary",
        text: "确定",
        onclick: () => {
          const result = [...selected.values()].map((node) => ({
            id: Number(node.key.split(":")[1]),
            label: node.label,
            subtitle: node.subtitle,
            type: node.type,
          }));
          close(result);
        },
      }),
    ]);
    modal.append(
      el("header", { class: "modal-head" }, [
        el("div", { class: "modal-head-copy" }, [
          el("h3", { text: title }),
          el("p", { class: "muted", text: "按组织树浏览，或直接搜索人员" }),
        ]),
        el("button", { class: "icon-btn", onclick: () => close(null) }, [icon("close", 18)]),
      ]),
      el("div", { class: "person-toolbar" }, [search]),
      el("div", { class: "person-body" }, [tree, el("div", { class: "person-selected" }, [chips])]),
      footer,
    );
    overlay.append(modal);
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) close(null);
    });
    document.body.append(overlay);
    tree.append(el("div", { class: "empty", text: "加载中…" }));
    search.addEventListener("input", () => state.rerender());

    api
      .get(`/org/tree?person_type=${encodeURIComponent(personType)}`)
      .then((data) => {
        nodes = data.nodes || [];
        const flat = flatten(nodes);
        for (const node of flat) {
          if (node.has_children) expanded.add(node.key);
          if (!node.selectable) continue;
          const id = Number(node.key.split(":")[1]);
          if (value && (Array.isArray(value) ? value.includes(id) : value === id)) {
            selected.set(id, node);
          }
        }
        if (!expanded.size) {
          for (const node of nodes) if (node.has_children) expanded.add(node.key);
        }
        state.rerender();
      })
      .catch((error) => {
        tree.innerHTML = "";
        tree.append(el("div", { class: "empty", text: error?.message || "人员树加载失败" }));
      });
  });
}
