// Daystar Health SPA API client.
// Reads bootstrap state injected by daystar-health.py: csrfToken, sessionUser,
// hasPractice. Wraps fetch with CSRF + JSON conventions used by every screen.

(function () {
  const bootstrap = window.__DAYSTAR_HEALTH__ || {};

  function showError(message) {
    if (window.frappe && typeof window.frappe.show_alert === "function") {
      window.frappe.show_alert({ message, indicator: "red" }, 5);
    } else {
      // Fallback for the standalone page where frappe.show_alert isn't loaded.
      console.error("[meridian-api]", message);
      alert(message);
    }
  }

  async function parseJson(response) {
    const text = await response.text();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }

  function extractServerMessage(payload, fallback) {
    if (!payload || typeof payload === "string") return payload || fallback;
    if (payload.message) return payload.message;
    if (payload._server_messages) {
      try {
        const list = JSON.parse(payload._server_messages);
        if (list.length) return JSON.parse(list[0]).message || fallback;
      } catch {}
    }
    if (payload.exc_type) return `${payload.exc_type}: ${payload.exception || fallback}`;
    return fallback;
  }

  async function call(method, args = {}) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": bootstrap.csrfToken || "",
        Accept: "application/json",
      },
      body: JSON.stringify(args),
    });
    const payload = await parseJson(response);
    if (!response.ok) {
      const msg = extractServerMessage(payload, response.statusText);
      const err = new Error(msg);
      err.status = response.status;
      err.payload = payload;
      throw err;
    }
    return payload && payload.message !== undefined ? payload.message : payload;
  }

  async function resource(doctype, params = {}) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) continue;
      search.append(key, typeof value === "string" ? value : JSON.stringify(value));
    }
    const url = `/api/resource/${encodeURIComponent(doctype)}?${search.toString()}`;
    const response = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    const payload = await parseJson(response);
    if (!response.ok) {
      const msg = extractServerMessage(payload, response.statusText);
      const err = new Error(msg);
      err.status = response.status;
      err.payload = payload;
      throw err;
    }
    return payload;
  }

  async function login(email, pwd) {
    // Frappe's /api/method/login accepts form-encoded usr/pwd and sets the
    // session cookie. It returns home_page on success.
    const body = new URLSearchParams({ usr: email, pwd });
    const response = await fetch("/api/method/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
    const payload = await parseJson(response);
    if (!response.ok) {
      const msg = extractServerMessage(payload, "Invalid email or password.");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }
    return payload;
  }

  async function recoverPassword(email) {
    return call("frappe.core.doctype.user.user.reset_password", { user: email });
  }

  async function logout() {
    await fetch("/api/method/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-Frappe-CSRF-Token": bootstrap.csrfToken || "",
        Accept: "application/json",
      },
    });
    window.location.href = "/daystar-health";
  }

  window.meridianApi = {
    bootstrap,
    sessionUser: bootstrap.sessionUser || "Guest",
    hasPractice: !!bootstrap.hasPractice,
    isAuthenticated: bootstrap.sessionUser && bootstrap.sessionUser !== "Guest",
    call,
    resource,
    login,
    recoverPassword,
    logout,
    showError,
  };
})();
