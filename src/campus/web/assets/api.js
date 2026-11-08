const TOKEN_KEY = "campus.token";

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export const api = {
  token: localStorage.getItem(TOKEN_KEY) || "",

  setToken(token) {
    this.token = token || "";
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  },

  async request(method, path, body) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }
    const response = await fetch(`/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { message: text };
      }
    }
    if (!response.ok) {
      throw new ApiError(
        data?.message || `请求失败（HTTP ${response.status}）`,
        response.status,
        data?.code,
      );
    }
    return data;
  },

  get(path) {
    return this.request("GET", path);
  },
  post(path, body) {
    return this.request("POST", path, body);
  },
  patch(path, body) {
    return this.request("PATCH", path, body);
  },
  del(path) {
    return this.request("DELETE", path);
  },

  async download(path, filename) {
    const headers = {};
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const response = await fetch(`/api/v1${path}`, { headers });
    if (!response.ok) {
      let data = null;
      const text = await response.text();
      try {
        data = JSON.parse(text);
      } catch {
        data = { message: text };
      }
      throw new ApiError(data?.message || "下载失败", response.status, data?.code);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};
