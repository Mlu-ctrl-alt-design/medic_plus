(function() {
  const { useEffect, useState } = React;

  function PortalPracticePicker() {
    const [practices, setPractices] = useState(null);
    const [error, setError] = useState("");

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.resolve_my_practices")
        .then((rows) => {
          if (!rows || rows.length === 0) {
            // Zero matches — punt to /register/patient
            window.location.href = "/register/patient";
            return;
          }
          if (rows.length === 1) {
            window.location.href = `/portal/${rows[0].slug}`;
            return;
          }
          setPractices(rows);
        })
        .catch((e) => setError(e.message));
    }, []);

    if (error) return <div style={{padding: 24, color: "#991b1b"}}>{error}</div>;
    if (!practices) return <window.PortalLoading label="Resolving your practices…" />;

    return (
      <window.PortalShell>
        <div style={{padding: 24, maxWidth: 480, margin: "40px auto"}}>
          <h1 style={{fontSize: 22, fontWeight: 600, marginBottom: 16}}>Pick a practice</h1>
          <div style={{display: "grid", gap: 12}}>
            {practices.map(p => (
              <a key={p.slug} href={`/portal/${p.slug}`}
                style={{display: "flex", alignItems: "center", gap: 12, padding: 16, border: "1px solid var(--border)", borderRadius: 8, textDecoration: "none", color: "var(--text)"}}>
                {p.logo && <img src={p.logo} alt="" style={{height: 32, width: "auto"}} />}
                <div style={{fontWeight: 500}}>{p.practice_name}</div>
              </a>
            ))}
          </div>
        </div>
      </window.PortalShell>
    );
  }

  window.PortalPracticePicker = PortalPracticePicker;
})();
