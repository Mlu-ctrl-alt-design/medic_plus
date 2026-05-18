// Portal layout primitives — shell, topbar, tabs, drawer.

(function() {
  const { useEffect } = React;

  function PortalShell({ children }) {
    return <div className="portal-shell">{children}</div>;
  }

  function PortalTopbar({ practice, route, go, onLogout }) {
    return (
      <div className="portal-topbar">
        {practice && practice.logo && (
          <img src={practice.logo} alt={practice.practice_name} className="practice-logo" />
        )}
        <div className="practice-name">{practice ? practice.practice_name : "Patient Portal"}</div>
        <div className="spacer" />
        {window.portalApi.isAuthenticated && (
          <button className="portal-cta secondary" style={{padding: "0 12px", minHeight: 36}} onClick={onLogout}>
            Sign out
          </button>
        )}
      </div>
    );
  }

  function PortalTabs({ route, go }) {
    const tabs = [
      { id: "home", label: "Home" },
      { id: "appointments", label: "Appointments" },
      { id: "records", label: "Records" },
      { id: "documents", label: "Documents" },
      { id: "billing", label: "Billing" },
      { id: "profile", label: "Profile" },
    ];
    return (
      <div className="portal-tabs" role="tablist">
        {tabs.map(t => (
          <button
            key={t.id}
            role="tab"
            aria-selected={route === t.id}
            className={`portal-tab${route === t.id ? " active" : ""}`}
            onClick={() => go(t.id)}
          >{t.label}</button>
        ))}
      </div>
    );
  }

  function PortalDrawer({ open, onClose, children, title }) {
    useEffect(() => {
      if (!open) return;
      const onKey = (e) => { if (e.key === "Escape") onClose(); };
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    return (
      <div className={`portal-drawer${open ? " open" : ""}`} onClick={onClose}>
        <div className="portal-drawer-content" onClick={(e) => e.stopPropagation()}>
          <div className="portal-topbar">
            <div className="practice-name">{title}</div>
            <div className="spacer" />
            <button className="portal-cta secondary" style={{padding: "0 12px", minHeight: 36}} onClick={onClose}>Close</button>
          </div>
          <div style={{padding: 16, flex: 1, overflowY: "auto"}}>{children}</div>
        </div>
      </div>
    );
  }

  function PortalLoading({ label = "Loading…" }) {
    return <div style={{padding: 24, color: "var(--text-muted)", fontSize: 13}}>{label}</div>;
  }

  function PortalEmpty({ title, description, action }) {
    return (
      <div style={{padding: 40, textAlign: "center", color: "var(--text-muted)"}}>
        <div style={{fontSize: 16, fontWeight: 600, color: "var(--text)", marginBottom: 8}}>{title}</div>
        {description && <div style={{fontSize: 13, marginBottom: 16}}>{description}</div>}
        {action}
      </div>
    );
  }

  window.PortalShell = PortalShell;
  window.PortalTopbar = PortalTopbar;
  window.PortalTabs = PortalTabs;
  window.PortalDrawer = PortalDrawer;
  window.PortalLoading = PortalLoading;
  window.PortalEmpty = PortalEmpty;
})();
