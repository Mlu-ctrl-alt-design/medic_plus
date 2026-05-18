(function() {
  const { useEffect, useState } = React;

  function PortalAppointmentsScreen({ go }) {
    const [data, setData] = useState(null);
    const [busy, setBusy] = useState("");

    function refresh() {
      const slug = window.portalApi.slug;
      window.portalApi.call("medic_plus.api.patient_portal.list_my_appointments", { slug })
        .then(setData);
    }
    useEffect(refresh, []);

    async function cancel(name) {
      if (!confirm("Cancel this appointment?")) return;
      setBusy(name);
      try {
        await window.portalApi.call("medic_plus.api.patient_portal.cancel_my_appointment",
          { slug: window.portalApi.slug, name });
        refresh();
      } catch (e) {
        window.portalApi.showError(e.message);
      } finally { setBusy(""); }
    }

    if (!data) return <window.PortalLoading />;

    return (
      <div className="fade-in">
        <div style={{display: "flex", alignItems: "center", marginBottom: 16}}>
          <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", flex: 1}}>Appointments</h1>
          <button className="portal-cta" onClick={() => go("book")}>+ Book</button>
        </div>

        <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-muted)", margin: "16px 0 8px"}}>
          Upcoming
        </div>
        {data.upcoming.length === 0 ? (
          <window.PortalEmpty title="No upcoming appointments" />
        ) : data.upcoming.map(a => (
          <div key={a.name} className="portal-card" style={{padding: 16, marginBottom: 8, display: "flex", alignItems: "center", gap: 12}}>
            <div style={{flex: 1}}>
              <div style={{fontWeight: 600}}>{a.appointment_date} · {String(a.appointment_time).slice(0,5)}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>
                {a.practitioner_name || a.practitioner} · {a.status}
              </div>
            </div>
            <button className="portal-cta secondary" onClick={() => cancel(a.name)} disabled={busy === a.name}>
              {busy === a.name ? "…" : "Cancel"}
            </button>
          </div>
        ))}

        <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-muted)", margin: "24px 0 8px"}}>
          Past
        </div>
        {data.past.length === 0 ? (
          <window.PortalEmpty title="No past appointments" />
        ) : data.past.map(a => (
          <div key={a.name} className="portal-card" style={{padding: 16, marginBottom: 8}}>
            <div style={{fontWeight: 500}}>{a.appointment_date} · {String(a.appointment_time).slice(0,5)}</div>
            <div style={{fontSize: 12, color: "var(--text-muted)"}}>
              {a.practitioner_name || a.practitioner} · {a.status}
            </div>
          </div>
        ))}
      </div>
    );
  }

  window.PortalAppointmentsScreen = PortalAppointmentsScreen;
})();
