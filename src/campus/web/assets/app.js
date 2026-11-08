import { api } from "./api.js";
import { charts } from "./charts.js";
import { el, icon, initials, toast } from "./ui.js";
import {
  PAGE_META,
  can,
  ensureLookups,
  handleError,
  navItems,
  setUnauthorizedHandler,
  state,
} from "./core/state.js";
import { setRouterHandlers } from "./core/router.js";
import { confirmDialog, openForm } from "./components/modal.js";
import { VIEWS } from "./views/index.js";

const SIDEBAR_KEY = "campus.sidebar";
let sidebarCollapsed = localStorage.getItem(SIDEBAR_KEY) === "1";
let mobileNavOpen = false;
let notificationTimer = null;

function renderLogin() {
  const root = document.getElementById("app");
  root.innerHTML = "";
  const usernameInput = el("input", {
    name: "username",
    required: true,
    autocomplete: "username",
    value: "admin",
  });
  const passwordInput = el("input", {
    name: "password",
    type: "password",
    required: true,
    autocomplete: "current-password",
    value: "admin123",
  });
  const form = el("form", { class: "login-card" }, [
    el("div", { class: "login-card-head" }, [
      el("span", { class: "eyebrow", text: "WELCOME BACK" }),
      el("h2", { text: "登录校园管理系统" }),
      el("p", { class: "muted", text: "使用演示账号即可体验完整功能" }),
    ]),
    el("label", { class: "field" }, [el("span", { text: "用户名" }), usernameInput]),
    el("label", { class: "field" }, [el("span", { text: "密码" }), passwordInput]),
    el("button", { type: "submit", class: "btn primary block" }, ["登录", icon("chevronRight", 16)]),
    el("div", { class: "login-hint" }, [
      el("span", { class: "muted", text: "演示账号" }),
      el(
        "div",
        { class: "chips" },
        [
          ["管理员", "admin", "admin123"],
          ["教师", "t001", "teacher123"],
          ["学生", "s001", "student123"],
        ].map(([label, user, password]) =>
          el("button", {
            type: "button",
            class: "chip",
            text: label,
            onclick: () => {
              usernameInput.value = user;
              passwordInput.value = password;
            },
          }),
        ),
      ),
    ]),
  ]);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await api.post("/auth/login", {
        username: usernameInput.value.trim(),
        password: passwordInput.value,
      });
      api.setToken(result.access_token);
      state.user = result.user;
      state.view = "dashboard";
      state.lookupsLoaded = false;
      await boot();
    } catch (error) {
      handleError(error);
    }
  });

  const hero = el("section", { class: "login-hero" }, [
    el("div", { class: "login-brand" }, [
      el("span", { class: "brand-mark" }, [icon("classes", 20)]),
      el("span", { text: "校园管理系统" }),
    ]),
    el("div", { class: "login-hero-copy" }, [
      el("h1", { text: "让校园管理更清晰、更从容" }),
      el("p", { text: "从学籍、排课到成绩与缴费，一个入口掌握全校运行状态。" }),
      el(
        "ul",
        { class: "login-points" },
        [
          ["实时仪表盘", "关键指标、趋势与预警一屏掌握"],
          ["角色化视图", "管理员、教师与学生各取所需"],
          ["一体化教务", "选课、成绩、考勤与缴费闭环"],
        ].map(([title, desc]) =>
          el("li", {}, [
            el("span", { class: "point-icon" }, [icon("check", 14)]),
            el("div", {}, [el("strong", { text: title }), el("p", { text: desc })]),
          ]),
        ),
      ),
    ]),
    el("div", { class: "login-art", "aria-hidden": "true" }, [
      el("span", { class: "blob blob-a" }),
      el("span", { class: "blob blob-b" }),
      el("div", { class: "mock-board" }, Array.from({ length: 12 }, (_, index) => el("span", { class: `cell c${index % 5}` }))),
    ]),
  ]);

  root.append(
    el("div", { class: "login-page" }, [hero, el("section", { class: "login-panel" }, [form])]),
  );
}


function clearSession() {
  api.setToken("");
  state.user = null;
  state.permissions = new Set();
  state.nav = [];
  state.scope = {};
  state.lookupsLoaded = false;
  charts.dispose();
  if (notificationTimer) {
    window.clearInterval(notificationTimer);
    notificationTimer = null;
  }
}

function logout() {
  clearSession();
  renderLogin();
}

async function requestLogout() {
  const confirmed = await confirmDialog({
    title: "退出登录",
    message: "退出后需要重新登录，未保存的内容将丢失。确定退出吗？",
    confirmLabel: "退出登录",
    danger: true,
  });
  if (confirmed) logout();
}

function navigate(view) {
  if (!VIEWS[view] || state.view === view) return;
  state.view = view;
  mobileNavOpen = false;
  renderShell();
}

function buildSearch() {
  const input = el("input", {
    class: "topbar-search",
    type: "search",
    placeholder: "搜索功能（Ctrl+K）",
    "aria-label": "搜索功能",
  });
  const results = el("div", { class: "search-results hidden" });
  const wrap = el("div", { class: "search-wrap" }, [
    el("span", { class: "search-icon" }, [icon("search", 16)]),
    input,
    results,
  ]);
  const pool = navItems();
  const render = () => {
    const keyword = input.value.trim();
    results.innerHTML = "";
    const matches = pool.filter((item) => !keyword || item.label.includes(keyword));
    if (!matches.length) {
      results.append(el("div", { class: "search-empty", text: "没有找到对应功能" }));
    } else {
      for (const item of matches) {
        results.append(
          el(
            "button",
            {
              type: "button",
              class: "search-item",
              onclick: () => {
                results.classList.add("hidden");
                navigate(item.id);
              },
            },
            [icon(item.icon, 16), item.label],
          ),
        );
      }
    }
    results.classList.remove("hidden");
  };
  input.addEventListener("focus", render);
  input.addEventListener("input", render);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      const first = results.querySelector(".search-item");
      if (first) first.click();
    }
    if (event.key === "Escape") {
      input.blur();
      results.classList.add("hidden");
    }
  });
  input.addEventListener("blur", () => {
    setTimeout(() => results.classList.add("hidden"), 120);
  });
  return wrap;
}

async function refreshNotifications() {
  const badge = document.getElementById("notification-badge");
  if (!badge || !state.user) return;
  try {
    const summary = await api.get("/notifications/summary");
    badge.textContent = summary.unread > 99 ? "99+" : String(summary.unread);
    badge.classList.toggle("hidden", summary.unread === 0);
  } catch {
    badge.classList.add("hidden");
  }
}

function openChangePassword() {
  openForm({
    title: "修改密码",
    subtitle: "修改后当前会话仍有效，下次登录使用新密码。",
    size: "sm",
    fields: [
      { name: "old_password", label: "当前密码", type: "password", required: true },
      { name: "new_password", label: "新密码（至少 8 位）", type: "password", required: true },
      { name: "confirm_password", label: "确认新密码", type: "password", required: true },
    ],
    submitLabel: "保存",
    onSubmit: async (values) => {
      if (values.new_password !== values.confirm_password) {
        throw new Error("两次输入的新密码不一致");
      }
      if (String(values.new_password || "").length < 8) {
        throw new Error("新密码至少 8 位");
      }
      await api.post("/auth/change-password", {
        old_password: values.old_password,
        new_password: values.new_password,
      });
      toast("密码已更新");
    },
  });
}

async function renderView() {
  const main = document.getElementById("view");
  if (!main) return;
  main.innerHTML = "";
  try {
    if (state.view !== "dashboard") await ensureLookups();
    const view = VIEWS[state.view];
    if (view) await view(main);
  } catch (error) {
    console.error("view render failed", state.view, error);
    handleError(error);
  }
}

function navButton(item, collapsed) {
  return el(
    "button",
    {
      class: "nav-btn" + (state.view === item.id ? " active" : ""),
      title: collapsed ? item.label : null,
      onclick: () => navigate(item.id),
    },
    [icon(item.icon, 18), collapsed ? null : el("span", { text: item.label })],
  );
}

async function renderShell() {
  const root = document.getElementById("app");
  root.innerHTML = "";
  charts.dispose();
  if (!navItems().some((item) => item.id === state.view)) state.view = "dashboard";
  const groups = state.nav
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !(item.id === "reports" && state.user.role === "student")),
    }))
    .filter((group) => group.items.length);

  const navGroups = groups.map((group) =>
    el("div", { class: "nav-group" }, [
      sidebarCollapsed ? null : el("span", { class: "nav-group-label", text: group.label }),
      ...group.items.map((item) => navButton(item, sidebarCollapsed)),
    ]),
  );

  const meta = PAGE_META[state.view] || PAGE_META.dashboard;
  const today = new Date().toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  });

  const sidebar = el("aside", { class: "sidebar" }, [
    el(
      "a",
      {
        class: "brand",
        href: "#",
        onclick: (event) => {
          event.preventDefault();
          navigate("dashboard");
        },
      },
      [
        el("span", { class: "brand-mark" }, [icon("classes", 20)]),
        sidebarCollapsed
          ? null
          : el("span", { class: "brand-text" }, [
              el("strong", { text: "校园管理系统" }),
              el("small", { text: "Campus MS" }),
            ]),
      ],
    ),
    el(
      "button",
      {
        class: "btn ghost sidebar-toggle",
        title: sidebarCollapsed ? "展开侧边栏" : "收起侧边栏",
        onclick: () => {
          sidebarCollapsed = !sidebarCollapsed;
          localStorage.setItem(SIDEBAR_KEY, sidebarCollapsed ? "1" : "0");
          renderShell();
        },
      },
      [icon(sidebarCollapsed ? "chevronRight" : "chevronLeft", 16), sidebarCollapsed ? null : "收起"],
    ),
    el("nav", { class: "nav" }, navGroups),
    el("div", { class: "sidebar-foot" }, [
      el("div", {
        class: "user-chip clickable",
        title: "修改密码",
        role: "button",
        tabindex: "0",
        onclick: openChangePassword,
        onkeydown: (event) => {
          if (event.key === "Enter" || event.key === " ") openChangePassword();
        },
      }, [
        el("span", {
          class: "avatar",
          text: initials(state.user.display_name || state.user.username),
          title: state.user.display_name || state.user.username,
        }),
        sidebarCollapsed
          ? null
          : el("div", { class: "user-meta" }, [
              el("strong", { text: state.user.display_name || state.user.username }),
              el("span", { text: state.user.role }),
            ]),
      ]),
      el(
        "button",
        { class: "icon-btn", title: "退出登录", onclick: requestLogout },
        [icon("logout", 18)],
      ),
    ]),
  ]);

  const topbar = el("header", { class: "topbar" }, [
    el("div", { class: "topbar-heading" }, [
      el("button", {
        class: "icon-btn mobile-nav-toggle",
        title: "打开导航",
        onclick: () => {
          mobileNavOpen = !mobileNavOpen;
          renderShell();
        },
      }, [icon("chevronRight", 18)]),
      el("div", {}, [
        el("h1", { text: meta.title }),
        el("p", { text: meta.subtitle }),
      ]),
    ]),
    el("div", { class: "topbar-actions" }, [
      buildSearch(),
      el("span", { class: "today-pill" }, [icon("calendar", 15), today]),
      el(
        "button",
        {
          class: "icon-btn bell-btn",
          title: "消息中心",
          onclick: () => navigate("notifications"),
        },
        [
          icon("bell", 18),
          el("span", { class: "badge hidden", id: "notification-badge", text: "0" }),
        ],
      ),
    ]),
  ]);

  const main = el("main", { class: "content", id: "view" });
  const layout = el(
    "div",
    {
      class:
        "layout" +
        (sidebarCollapsed ? " sidebar-collapsed" : "") +
        (mobileNavOpen ? " mobile-nav-open" : ""),
    },
    [sidebar, el("div", { class: "main" }, [topbar, main])],
  );
  if (mobileNavOpen) {
    layout.append(
      el("div", {
        class: "mobile-nav-backdrop",
        onclick: () => {
          mobileNavOpen = false;
          renderShell();
        },
      }),
    );
  }
  root.append(layout);
  await renderView();
  refreshNotifications();
  if (!notificationTimer) {
    notificationTimer = window.setInterval(() => {
      if (state.user) refreshNotifications();
    }, 60000);
  }
  requestAnimationFrame(() => {
    document.querySelector(".nav-btn.active")?.scrollIntoView({ block: "nearest", inline: "center" });
  });
}

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    const search = document.querySelector(".topbar-search");
    if (search) {
      event.preventDefault();
      search.focus();
    }
  }
  if (!event.ctrlKey && !event.metaKey && event.key === "[") {
    const target = document.activeElement;
    if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
    sidebarCollapsed = !sidebarCollapsed;
    localStorage.setItem(SIDEBAR_KEY, sidebarCollapsed ? "1" : "0");
    renderShell();
  }
});

window.addEventListener("campus:navigate", (event) => navigate(event.detail));

async function boot() {
  if (!api.token) {
    renderLogin();
    return;
  }
  try {
    state.user = await api.get("/auth/me");
    state.permissions = new Set(state.user.permissions || []);
    state.nav = state.user.nav || [];
    state.scope = state.user.scope || {};
    await renderShell();
  } catch (error) {
    api.setToken("");
    renderLogin();
  }
}

setUnauthorizedHandler(() => {
  clearSession();
  renderLogin();
});
setRouterHandlers({ navigate, refresh: renderView });
boot();
