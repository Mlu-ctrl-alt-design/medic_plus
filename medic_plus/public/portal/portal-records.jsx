(function() {
  const { useEffect, useState } = React;

  function PortalRecordsScreen() {
    const slug = window.portalApi.slug;
    const [data, setData] = useState(null);
    const [tab, setTab] = useState("encounters");

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.list_my_records", { slug })
        .then(setData);
    }, []);

    if (!data) return <window.PortalLoading />;

    const tabs = [
      { id: "encounters", label: `Visits (${data.encounters.length})` },
      { id: "problems", label: `Problems (${data.problems.length})` },
      { id: "allergies", label: `Allergies (${data.allergies.length})` },
      { id: "chronic_conditions", label: `Chronic (${data.chronic_conditions.length})` },
    ];

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 16}}>Records</h1>

        <div className="portal-tabs">
          {tabs.map(t => (
            <button key={t.id} className={`portal-tab${tab === t.id ? " active" : ""}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "encounters" && (
          data.encounters.length === 0 ? <window.PortalEmpty title="No visits recorded" />
          : data.encounters.map(e => (
            <div key={e.name} className="portal-card" style={{padding: 16, marginBottom: 8}}>
              <div style={{fontWeight: 600}}>{e.encounter_date}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{e.practitioner_name || ""}</div>
            </div>
          ))
        )}

        {tab === "problems" && (
          data.problems.length === 0 ? <window.PortalEmpty title="No problems on record" />
          : data.problems.map(p => (
            <div key={p.name} className="portal-card" style={{padding: 16, marginBottom: 8}}>
              <div style={{fontWeight: 600}}>{p.description}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{p.status} · {p.onset_date || ""}</div>
            </div>
          ))
        )}

        {tab === "allergies" && (
          data.allergies.length === 0 ? <window.PortalEmpty title="No allergies on record" />
          : data.allergies.map(a => (
            <div key={a.name} className="portal-card" style={{padding: 16, marginBottom: 8}}>
              <div style={{fontWeight: 600}}>{a.substance}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{a.severity} · {a.reaction}</div>
            </div>
          ))
        )}

        {tab === "chronic_conditions" && (
          data.chronic_conditions.length === 0 ? <window.PortalEmpty title="No chronic conditions on record" />
          : data.chronic_conditions.map(c => (
            <div key={c.name} className="portal-card" style={{padding: 16, marginBottom: 8}}>
              <div style={{fontWeight: 600}}>{c.diagnosis}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{c.chronic_status} · {c.started_on || ""}</div>
            </div>
          ))
        )}
      </div>
    );
  }

  window.PortalRecordsScreen = PortalRecordsScreen;
})();
