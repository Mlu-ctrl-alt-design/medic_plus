// Meridian Practice screen — read-only display of the active practice's
// fields, mirroring what's visible on the Desk Practice form.

// Practice.logo and Practice.color are admin-controlled DB values; treat
// them as untrusted. Only allow http(s) / relative / data-image URLs for
// the logo (no javascript:, no vbscript:) and only allow #RRGGBB(AA),
// 3/6/8-digit hex or rgb()/rgba() for the brand colour.
function safeImageSrc(value) {
  if (typeof value !== "string" || !value) return null;
  const v = value.trim();
  if (/^https?:\/\//i.test(v)) return v;
  if (v.startsWith("/")) return v;
  if (/^data:image\//i.test(v)) return v;
  return null;
}
function safeCssColor(value) {
  if (typeof value !== "string" || !value) return null;
  const v = value.trim();
  if (/^#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(v)) return v;
  if (/^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*(?:0|1|0?\.\d+)\s*)?\)$/i.test(v)) return v;
  return null;
}

const PRACTICE_TABS = [
  { key: "overview",    label: "Overview" },
  { key: "my-calendar", label: "My Calendar" },
];

function PracticeTabBar({ active, onChange }) {
  return (
    <div
      role="tablist"
      style={{
        display: "flex", gap: 0, borderBottom: "1px solid var(--border-color)",
        marginBottom: 20,
      }}
    >
      {PRACTICE_TABS.map(t => {
        const isActive = t.key === active;
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(t.key)}
            style={{
              padding: "10px 18px", fontSize: 13, fontWeight: isActive ? 600 : 400,
              color: isActive ? "var(--accent, #2563eb)" : "var(--text-muted)",
              background: "none", border: "none", cursor: "pointer",
              borderBottom: isActive ? "2px solid var(--accent, #2563eb)" : "2px solid transparent",
              marginBottom: -1, transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

function MPracticeScreen({ go }) {
  const [activeTab, setActiveTab] = mUseState("overview");
  const [state, setState] = mUseState({ status: "loading", practice: null, error: null });

  mUseEffect(() => {
    let cancelled = false;
    window.meridianApi.call("medic_plus.api.daystar_health.get_active_practice_details")
      .then((practice) => {
        if (cancelled) return;
        setState({ status: "ok", practice, error: null });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({ status: "error", practice: null, error: err.message || "Could not load practice." });
      });
    return () => { cancelled = true; };
  }, []);

  if (state.status === "loading") {
    return (
      <div className="page fade-in" data-testid="practice-page">
        <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 20 }}>Practice</h1>
        <PracticeTabBar active={activeTab} onChange={setActiveTab} />
        <div className="card card-pad">
          <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Loading practice details…</div>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="page fade-in" data-testid="practice-page">
        <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 20 }}>Practice</h1>
        <PracticeTabBar active={activeTab} onChange={setActiveTab} />
        <div className="card card-pad" style={{ background: "var(--danger-soft)", borderColor: "var(--danger)" }}>
          <div style={{ fontSize: 13, color: "#b91c1c" }}>{state.error}</div>
        </div>
      </div>
    );
  }

  const p = state.practice || {};
  const fmt = (v) => (v === null || v === undefined || v === "") ? "—" : v;
  const planLabel = (s) => fmt(s);
  const logoSrc = safeImageSrc(p.logo);
  const brandColor = safeCssColor(p.color);

  return (
    <div className="page fade-in" data-testid="practice-page">
      {/* Page header — always visible */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
        {logoSrc ? (
          <img
            src={logoSrc}
            alt={p.practice_name || "Practice logo"}
            style={{ width: 48, height: 48, borderRadius: 10, objectFit: "cover", border: "1px solid var(--border)" }}
          />
        ) : (
          <div
            aria-hidden="true"
            style={{
              width: 48, height: 48, borderRadius: 10,
              background: brandColor || "var(--accent-soft)",
              color: "var(--accent-text)", display: "grid", placeItems: "center",
              fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em",
              border: "1px solid var(--border)",
            }}
          >
            {(p.practice_name || "P")[0].toUpperCase()}
          </div>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", letterSpacing: "-0.02em" }} data-testid="practice-name">
            {p.practice_name || p.name}
          </h1>
          <div style={{ fontSize: 12.5, color: "var(--text-muted)", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontFamily: "var(--font-mono)" }}>{p.name}</span>
            {p.slug && <><span>·</span><span>/{p.slug}</span></>}
            {p.is_active ? <span className="pill-stable" style={{ marginLeft: 4 }}>Active</span> : <span style={{ color: "var(--danger)" }}>Inactive</span>}
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <PracticeTabBar active={activeTab} onChange={setActiveTab} />

      {/* My Calendar tab */}
      {activeTab === "my-calendar" && (
        <window.MCalendarScreen go={go} embedded={true} />
      )}

      {/* Overview tab */}
      {activeTab === "overview" && (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>

        <section className="card card-pad" data-testid="practice-contact">
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Contact</div>
          <DetailRow label="Phone" value={fmt(p.phone)} />
          <DetailRow label="Email" value={fmt(p.email)} />
          <DetailRow label="Address" value={fmt(p.address)} multiline />
        </section>

        <section className="card card-pad" data-testid="practice-subscription">
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Subscription</div>
          <DetailRow label="Plan" value={planLabel(p.subscription_plan)} />
          <DetailRow label="Status" value={fmt(p.subscription_status)} />
          {p.trial_ends_on && <DetailRow label="Trial ends" value={p.trial_ends_on} />}
          {p.current_period_end && <DetailRow label="Renews" value={p.current_period_end} />}
        </section>

        <section className="card card-pad" data-testid="practice-branding">
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Branding & Owner</div>
          <DetailRow label="Owner / Primary Doctor" value={fmt(p.owner_practitioner_name || p.owner_practitioner)} />
          <DetailRow label="Brand colour" value={
            brandColor ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: 3, background: brandColor, border: "1px solid var(--border)" }} />
                <span style={{ fontFamily: "var(--font-mono)" }}>{brandColor}</span>
              </span>
            ) : "—"
          } />
          <DetailRow label="ERPNext Company" value={fmt(p.company)} />
        </section>

        <section className="card card-pad" style={{ gridColumn: "1 / -1" }} data-testid="practice-doctors">
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Doctors & Admins</div>
          {(p.doctors || []).length === 0 ? (
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>No doctors or admins registered yet.</div>
          ) : (
            <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--text-muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  <th style={{ padding: "8px 4px", borderBottom: "1px solid var(--border)" }}>Name</th>
                  <th style={{ padding: "8px 4px", borderBottom: "1px solid var(--border)" }}>User</th>
                  <th style={{ padding: "8px 4px", borderBottom: "1px solid var(--border)" }}>Role</th>
                </tr>
              </thead>
              <tbody>
                {p.doctors.map((d) => (
                  <tr key={d.name}>
                    <td style={{ padding: "10px 4px", borderBottom: "1px solid var(--border)" }}>{d.practitioner_name || d.practitioner || "—"}</td>
                    <td style={{ padding: "10px 4px", borderBottom: "1px solid var(--border)", color: "var(--text-muted)" }}>{d.user}</td>
                    <td style={{ padding: "10px 4px", borderBottom: "1px solid var(--border)" }}>{d.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
      )}
    </div>
  );
}

function DetailRow({ label, value, multiline = false }) {
  return (
    <div style={{ display: "flex", flexDirection: multiline ? "column" : "row", gap: multiline ? 4 : 12, padding: "6px 0", fontSize: 13 }}>
      <div style={{ color: "var(--text-muted)", minWidth: multiline ? 0 : 140, fontSize: 12 }}>{label}</div>
      <div style={{ color: "var(--text)", whiteSpace: multiline ? "pre-wrap" : "normal", flex: 1 }}>{value}</div>
    </div>
  );
}

window.MPracticeScreen = MPracticeScreen;
