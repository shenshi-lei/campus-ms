import { el, icon } from "../ui.js";
import { openPersonPicker } from "./tree-select.js";

const SIZE_CLASS = {
  sm: "modal-sm",
  md: "modal-md",
  lg: "modal-lg",
  xl: "modal-xl",
  full: "modal-full",
};

function trapFocus(container) {
  const selectors =
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  container.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const items = [...container.querySelectorAll(selectors)].filter(
      (item) => !item.disabled && item.offsetParent !== null,
    );
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
}

export function openModal({
  title,
  subtitle = "",
  size = "md",
  body,
  footer = null,
  closeOnOverlay = true,
  onClose = null,
  className = "",
}) {
  const previous = document.activeElement;
  const overlay = el("div", { class: "overlay" });
  const modal = el("div", { class: `modal ${SIZE_CLASS[size] || SIZE_CLASS.md} ${className}` });
  const header = el("header", { class: "modal-head" }, [
    el("div", { class: "modal-head-copy" }, [
      el("h3", { text: title }),
      subtitle ? el("p", { class: "muted", text: subtitle }) : null,
    ]),
    el(
      "button",
      { class: "icon-btn modal-close", title: "关闭", onclick: () => close() },
      [icon("close", 18)],
    ),
  ]);
  const bodyNode = el("div", { class: "modal-body" }, [body]);
  modal.append(header, bodyNode);
  if (footer) modal.append(el("div", { class: "modal-foot" }, [footer]));
  overlay.append(modal);

  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    overlay.remove();
    document.removeEventListener("keydown", onKey);
    if (previous && previous.focus) previous.focus();
    if (onClose) onClose();
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  };
  document.addEventListener("keydown", onKey);
  if (closeOnOverlay) {
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) close();
    });
  }
  trapFocus(modal);
  document.body.append(overlay);
  requestAnimationFrame(() => {
    const focusable = modal.querySelector("input, select, textarea, button");
    if (focusable) focusable.focus();
  });
  return { close, overlay, modal, body: bodyNode };
}

export function openDrawer({
  title,
  subtitle = "",
  body,
  footer = null,
  width = "lg",
  onClose = null,
}) {
  const overlay = el("div", { class: "overlay drawer-overlay" });
  const drawer = el("aside", { class: `drawer drawer-${width}` }, [
    el("header", { class: "modal-head" }, [
      el("div", { class: "modal-head-copy" }, [
        el("h3", { text: title }),
        subtitle ? el("p", { class: "muted", text: subtitle }) : null,
      ]),
      el("button", { class: "icon-btn", title: "关闭", onclick: () => close() }, [
        icon("close", 18),
      ]),
    ]),
    el("div", { class: "drawer-body" }, [body]),
    footer ? el("div", { class: "modal-foot" }, [footer]) : null,
  ]);
  overlay.append(drawer);
  const close = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
    if (onClose) onClose();
  };
  const onKey = (event) => {
    if (event.key === "Escape") close();
  };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });
  document.body.append(overlay);
  return { close, drawer, body: drawer.querySelector(".drawer-body") };
}

export function confirmDialog({
  title = "请确认",
  message = "确定执行该操作吗？",
  confirmLabel = "确定",
  cancelLabel = "取消",
  danger = false,
} = {}) {
  return new Promise((resolve) => {
    const footer = el("div", { class: "modal-actions" }, [
      el("button", {
        class: "btn",
        text: cancelLabel,
        onclick: () => {
          dialog.close();
          resolve(false);
        },
      }),
      el("button", {
        class: `btn ${danger ? "danger" : "primary"}`,
        text: confirmLabel,
        onclick: () => {
          dialog.close();
          resolve(true);
        },
      }),
    ]);
    const dialog = openModal({
      title,
      size: "sm",
      body: el("p", { class: "confirm-message", text: message }),
      footer,
      onClose: () => resolve(false),
    });
  });
}

export function promptDialog({
  title = "请输入",
  label = "",
  value = "",
  placeholder = "",
  confirmLabel = "确定",
} = {}) {
  return new Promise((resolve) => {
    const input = el("input", { class: "input", value, placeholder });
    const body = el("label", { class: "field" }, [
      label ? el("span", { text: label }) : null,
      input,
    ]);
    const footer = el("div", { class: "modal-actions" }, [
      el("button", {
        class: "btn",
        text: "取消",
        onclick: () => {
          dialog.close();
          resolve(null);
        },
      }),
      el("button", {
        class: "btn primary",
        text: confirmLabel,
        onclick: () => {
          const text = input.value;
          dialog.close();
          resolve(text);
        },
      }),
    ]);
    const dialog = openModal({
      title,
      size: "sm",
      body,
      footer,
      onClose: () => resolve(null),
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const text = input.value;
        dialog.close();
        resolve(text);
      }
    });
  });
}

function buildInput(field, inputs) {
  let input;
  if (field.type === "select") {
    input = el(
      "select",
      {},
      (field.options || []).map((item) =>
        el("option", { value: String(item.value), text: item.label }),
      ),
    );
    if (field.value !== undefined && field.value !== null) {
      input.value = String(field.value);
    }
  } else if (field.type === "textarea") {
    input = el("textarea", {
      rows: String(field.rows || 4),
      placeholder: field.placeholder || "",
    });
    input.value = field.value === undefined || field.value === null ? "" : String(field.value);
    if (field.required) input.required = true;
  } else if (field.type === "person" || field.type === "person-multi") {
    const multiple = field.type === "person-multi";
    const valueNode = el("div", { class: "person-value muted", text: "未选择" });
    const hidden = el("input", { type: "hidden" });
    const button = el("button", { type: "button", class: "btn person-trigger" }, [
      icon("students", 16),
      multiple ? "选择人员" : "选择人员",
    ]);
    let selected = multiple ? [...(field.value || [])] : field.value || null;
    const sync = () => {
      if (multiple) {
        hidden.value = JSON.stringify(selected.map((item) => item.id));
        valueNode.textContent = selected.length
          ? selected.map((item) => item.label).join("、")
          : "未选择";
      } else {
        hidden.value = selected ? String(selected.id) : "";
        valueNode.textContent = selected ? selected.label : "未选择";
      }
    };
    button.addEventListener("click", async () => {
      const result = await openPersonPicker({
        title: field.title || "选择人员",
        multiple,
        personType: field.personType || "student",
        value: multiple ? selected.map((item) => item.id) : selected?.id,
      });
      if (!result) return;
      selected = multiple ? result : result[0] || null;
      sync();
    });
    sync();
    input = el("div", { class: "person-field" }, [hidden, button, valueNode]);
    inputs[field.name] = { get value() { return hidden.value; }, node: input, multiple, get selected() { return selected; } };
    return input;
  } else {
    input = el("input", {
      type: field.type || "text",
      value: field.value === undefined || field.value === null ? "" : String(field.value),
      placeholder: field.placeholder || "",
    });
    if (field.required) input.required = true;
  }
  inputs[field.name] = input;
  return input;
}

export function openForm({
  title,
  fields,
  submitLabel = "保存",
  cancelLabel = "取消",
  onSubmit,
  size = "md",
  subtitle = "",
  columns = 2,
}) {
  const inputs = {};
  const grid = el("div", { class: `form-grid cols-${columns}` });
  for (const field of fields) {
    const input = buildInput(field, inputs);
    grid.append(
      el("label", { class: `field ${field.span === "full" ? "span-full" : ""}` }, [
        el("span", { text: field.label + (field.required ? " *" : "") }),
        input,
        field.help ? el("small", { class: "muted", text: field.help }) : null,
      ]),
    );
  }
  const form = el("form", { class: "modal-form" });
  form.append(grid);
  let dialog;
  const footer = el("div", { class: "modal-actions" }, [
    el("button", {
      type: "button",
      class: "btn",
      text: cancelLabel,
      onclick: () => dialog.close(),
    }),
    el("button", { type: "submit", class: "btn primary", text: submitLabel }),
  ]);
  form.append(footer);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = {};
    for (const field of fields) {
      const raw = inputs[field.name].value;
      if (field.as === "int") {
        values[field.name] = raw === "" ? null : Number.parseInt(raw, 10);
      } else if (field.as === "number") {
        values[field.name] = raw === "" ? null : Number(raw);
      } else if (field.type === "person-multi") {
        values[field.name] = raw ? JSON.parse(raw) : [];
      } else if (field.type === "person") {
        values[field.name] = raw === "" ? null : Number(raw);
      } else {
        values[field.name] = raw === "" ? null : raw;
      }
    }
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      await onSubmit(values);
      dialog.close();
    } catch (error) {
      const { handleError } = await import("../core/state.js");
      handleError(error);
    } finally {
      submit.disabled = false;
    }
  });
  dialog = openModal({ title, subtitle, size, body: form, footer: null });
  return dialog;
}
