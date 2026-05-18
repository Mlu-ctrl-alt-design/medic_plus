(function() {
  const { useEffect, useState } = React;

  function PortalDocumentsScreen() {
    const slug = window.portalApi.slug;
    const [data, setData] = useState(null);

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.list_my_documents", { slug })
        .then(setData);
    }, []);

    function downloadHref(doctype, name) {
      return window.portalApi.downloadUrl(
        "medic_plus.api.patient_portal.download_my_document",
        { slug, doctype, name }
      );
    }

    if (!data) return <window.PortalLoading />;

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 16}}>Documents</h1>

        <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-muted)", margin: "16px 0 8px"}}>
          Sick notes
        </div>
        {data.sick_notes.length === 0 ? <window.PortalEmpty title="No sick notes" />
        : data.sick_notes.map(d => (
          <div key={d.name} className="portal-card" style={{padding: 16, marginBottom: 8, display: "flex", alignItems: "center", gap: 12}}>
            <div style={{flex: 1}}>
              <div style={{fontWeight: 600}}>{d.date_issued}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{d.diagnosis || "—"} · {d.days_off} day(s) off</div>
            </div>
            <a href={downloadHref("Sick Note", d.name)} target="_blank" rel="noopener noreferrer"
              className="portal-cta secondary">Download</a>
          </div>
        ))}

        <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-muted)", margin: "24px 0 8px"}}>
          Prescriptions
        </div>
        {data.prescriptions.length === 0 ? <window.PortalEmpty title="No prescriptions" />
        : data.prescriptions.map(d => (
          <div key={d.name} className="portal-card" style={{padding: 16, marginBottom: 8, display: "flex", alignItems: "center", gap: 12}}>
            <div style={{flex: 1}}>
              <div style={{fontWeight: 600}}>{d.medication_request_date}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{d.status}</div>
            </div>
            <a href={downloadHref("Medication Request", d.name)} target="_blank" rel="noopener noreferrer"
              className="portal-cta secondary">Download</a>
          </div>
        ))}
      </div>
    );
  }

  window.PortalDocumentsScreen = PortalDocumentsScreen;
})();
