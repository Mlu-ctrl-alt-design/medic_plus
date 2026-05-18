(function() {
  const { useEffect, useState } = React;

  function PortalBillingScreen() {
    const slug = window.portalApi.slug;
    const [data, setData] = useState(null);

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.list_my_invoices", { slug })
        .then(setData);
    }, []);

    function downloadHref(name) {
      return window.portalApi.downloadUrl(
        "medic_plus.api.patient_portal.download_my_invoice", { slug, name }
      );
    }

    if (!data) return <window.PortalLoading />;

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 16}}>Billing</h1>
        {data.length === 0 ? <window.PortalEmpty title="No invoices yet" description="Your invoices will appear here once your practice issues them." />
        : data.map(inv => (
          <div key={inv.name} className="portal-card" style={{padding: 16, marginBottom: 8}}>
            <div style={{display: "flex", alignItems: "center", marginBottom: 4, gap: 12}}>
              <div style={{fontWeight: 600, flex: 1}}>{inv.name}</div>
              <a href={downloadHref(inv.name)} target="_blank" rel="noopener noreferrer"
                className="portal-cta secondary">PDF</a>
            </div>
            <div style={{fontSize: 12, color: "var(--text-muted)"}}>
              {inv.posting_date} · {inv.currency} {inv.grand_total} · outstanding: {inv.outstanding_amount} · {inv.status}
            </div>
          </div>
        ))}
      </div>
    );
  }

  window.PortalBillingScreen = PortalBillingScreen;
})();
