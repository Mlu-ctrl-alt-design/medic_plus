// Patient Portal API client.
// Reads bootstrap state injected by medic_plus/www/portal/index.py:
//   csrfToken, sessionUser, slug, practice, isAuthed, hasPatient.

(function () {
  const bootstrap = window.__DAYSTAR_PORTAL__ || {};

  function showError(message) {
    if (window.frappe && typeof window.frappe.show_alert === "function") {
      window.frappe.show_alert({ message, indicator: "red" }, 5);
    } else {
      console.error("[portal-api]", message);
      alert(message);
    }
  }

  async function parseJson(response) {
    const text = await response.text();
    if (!text) return null;
    try { return JSON.parse(text); } catch { return text; }
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

  function downloadUrl(method, args = {}) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(args)) {
      if (v == null) continue;
      params.append(k, typeof v === "string" ? v : JSON.stringify(v));
    }
    return `/api/method/${method}?${params.toString()}`;
  }

  window.portalApi = {
    bootstrap,
    slug: bootstrap.slug,
    isAuthenticated: !!bootstrap.isAuthed,
    hasPatient: !!bootstrap.hasPatient,
    sessionUser: bootstrap.sessionUser,
    practice: bootstrap.practice,
    call,
    downloadUrl,
    showError,
  };
})();
