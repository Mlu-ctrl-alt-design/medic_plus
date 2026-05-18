(function() {
  const { useEffect, useState } = React;

  function PortalHomeScreen({ go }) {
    const [data, setData] = useState(null);
    const [me, setMe] = useState(null);

    useEffect(() => {
      const slug = window.portalApi.slug;
      Promise.all([
        window.portalApi.call("medic_plus.api.patient_portal.list_my_appointments", { slug }),
        window.portalApi.call("medic_plus.api.patient_portal.get_me", { slug }),
      ]).then(([appts, me]) => { setData(appts); setMe(me); });
    }, []);

    if (!data) return <window.PortalLoading />;

    const next = data.upcoming[0] || null;

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 4}}>
          Hi {me ? me.first_name : ""}
        </h1>
        <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 20}}>
          Welcome back to your patient portal.
        </div>

        <div className="portal-card" style={{padding: 20, marginBottom: 16}}>
          <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 8}}>
            Next appointment
          </div>
          {next ? (
            <div>
              <div style={{fontSize: 16, fontWeight: 600, marginBottom: 4}}>
                {next.appointment_date} · {String(next.appointment_time).slice(0,5)}
              </div>
              <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 16}}>
                With {next.practitioner_name || next.practitioner}
              </div>
              <button className="portal-cta secondary" onClick={() => go("appointments")}>
                View details
              </button>
            </div>
          ) : (
            <div>
              <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 16}}>
                You have no upcoming appointments.
              </div>
              <button className="portal-cta" onClick={() => go("book")}>
                Book an appointment
              </button>
            </div>
          )}
        </div>

        <div className="portal-grid-2">
          <button className="portal-cta secondary" onClick={() => go("book")} style={{height: 80}}>
            New appointment
          </button>
          <button className="portal-cta secondary" onClick={() => go("records")} style={{height: 80}}>
            View records
          </button>
        </div>
      </div>
    );
  }

  window.PortalHomeScreen = PortalHomeScreen;
})();
