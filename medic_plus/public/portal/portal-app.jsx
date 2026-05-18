// Root React tree for the Patient Portal.

(function() {
  const { useState, useEffect, useCallback } = React;

  const VALID_ROUTES = ["home", "appointments", "book", "records", "documents", "billing", "profile"];

  function readUrl() {
    const params = new URLSearchParams(window.location.search);
    let route = params.get("screen");
    if (!route || !VALID_ROUTES.includes(route)) route = null;
    return { route };
  }

  function syncUrl(route, replace) {
    const url = route && route !== "home"
      ? `${window.location.pathname}?screen=${route}`
      : window.location.pathname;
    const fn = replace ? "replaceState" : "pushState";
    window.history[fn]({ route }, "", url);
  }

  function App() {
    const api = window.portalApi;
    const { isAuthenticated, hasPatient, practice, slug } = api;

    // If no slug — render the resolver page (login or practice picker).
    const noSlug = !slug;
    const [route, setRoute] = useState(() => readUrl().route || "home");
    const [bookOpen, setBookOpen] = useState(false);

    useEffect(() => { syncUrl(route, true); }, []);

    useEffect(() => {
      const handler = () => {
        const u = readUrl();
        setRoute(u.route || "home");
      };
      window.addEventListener("popstate", handler);
      return () => window.removeEventListener("popstate", handler);
    }, []);

    const go = useCallback((r) => {
      if (r === "book") { setBookOpen(true); return; }
      setRoute(r);
      syncUrl(r, false);
      window.scrollTo(0, 0);
    }, []);

    async function onLogout() {
      try { await fetch("/api/method/logout", { method: "GET", credentials: "same-origin" }); } catch {}
      window.location.href = slug ? `/portal/${slug}` : "/portal";
    }

    // ----- Resolver views -----
    if (noSlug) {
      if (!isAuthenticated) {
        return (
          <window.PortalShell>
            <div style={{padding: 24, maxWidth: 480, margin: "60px auto"}}>
              <h1 style={{fontSize: 22, fontWeight: 600, marginBottom: 12}}>Patient Portal</h1>
              <p style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 16}}>
                Enter your practice's portal address to continue.
              </p>
              <input
                type="text" placeholder="e.g. my-clinic"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.target.value.trim()) {
                    window.location.href = `/portal/${e.target.value.trim()}`;
                  }
                }}
                className="portal-input"
              />
            </div>
          </window.PortalShell>
        );
      }
      return <window.PortalPracticePicker />;
    }

    if (!isAuthenticated || !hasPatient) {
      return (
        <window.PortalShell>
          <window.PortalLoginScreen slug={slug} />
        </window.PortalShell>
      );
    }

    return (
      <window.PortalShell>
        <window.PortalTopbar practice={practice} route={route} go={go} onLogout={onLogout} />
        <div className="portal-main">
          <window.PortalTabs route={route} go={go} />
          {route === "home" && <window.PortalHomeScreen go={go} />}
          {route === "appointments" && <window.PortalAppointmentsScreen go={go} />}
          {route === "records" && <window.PortalRecordsScreen go={go} />}
          {route === "documents" && <window.PortalDocumentsScreen go={go} />}
          {route === "billing" && <window.PortalBillingScreen go={go} />}
          {route === "profile" && <window.PortalProfileScreen go={go} />}
        </div>
        <window.PortalDrawer open={bookOpen} onClose={() => setBookOpen(false)} title="Book an appointment">
          {bookOpen && <window.PortalBookDrawer onBooked={() => { setBookOpen(false); go("appointments"); }} />}
        </window.PortalDrawer>
      </window.PortalShell>
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
})();
