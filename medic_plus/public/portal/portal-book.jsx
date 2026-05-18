(function() {
  const { useEffect, useState } = React;

  function PortalBookDrawer({ onBooked }) {
    const slug = window.portalApi.slug;
    const [practitioners, setPractitioners] = useState([]);
    const [practitioner, setPractitioner] = useState("");
    const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
    const [slots, setSlots] = useState([]);
    const [slot, setSlot] = useState("");
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
      window.portalApi.call("medic_plus.api.booking.get_practice_practitioners", { practice_slug: slug })
        .then((rows) => setPractitioners(rows || []))
        .catch((e) => setError(e.message));
    }, []);

    useEffect(() => {
      if (!practitioner || !date) { setSlots([]); return; }
      setSlot("");
      window.portalApi.call("medic_plus.api.booking.get_availability",
        { practice_slug: slug, practitioner, date })
        .then((rows) => setSlots(rows || []))
        .catch((e) => setError(e.message));
    }, [practitioner, date]);

    async function submit(e) {
      e.preventDefault();
      setBusy(true); setError("");
      try {
        await window.portalApi.call("medic_plus.api.patient_portal.book_for_authed_patient", {
          slug, practitioner, appointment_date: date, appointment_time: slot, reason,
        });
        onBooked && onBooked();
      } catch (err) {
        setError(err.message);
      } finally { setBusy(false); }
    }

    const practitionerOptions = practitioners.map(p => ({
      value: p.name,
      label: p.practitioner_name || p.name,
    }));

    return (
      <form onSubmit={submit}>
        <div className="portal-form-field">
          <label>Practitioner</label>
          <window.MSelect
            value={practitioner}
            onChange={setPractitioner}
            options={practitionerOptions}
            placeholder="Pick a doctor…"
          />
        </div>

        <div className="portal-form-field">
          <label>Date</label>
          <window.MDatePicker
            value={date}
            onChange={setDate}
            min={new Date().toISOString().slice(0, 10)}
            placeholder="YYYY-MM-DD"
          />
        </div>

        <div className="portal-form-field">
          <label>Available slots</label>
          {practitioner && slots.length === 0 && (
            <div style={{fontSize: 12, color: "var(--text-muted)"}}>No slots on this date.</div>
          )}
          <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(80px, 1fr))", gap: 8}}>
            {slots.map((t) => (
              <button key={t} type="button"
                onClick={() => setSlot(t)}
                className={`portal-cta ${slot === t ? "" : "secondary"}`}
                style={{padding: "0 8px", minHeight: 40, fontSize: 13}}>
                {String(t).slice(0,5)}
              </button>
            ))}
          </div>
        </div>

        <div className="portal-form-field">
          <label>Reason (optional)</label>
          <window.MTextArea
            value={reason}
            onChange={setReason}
            rows={3}
          />
        </div>

        <button className="portal-cta" type="submit" disabled={busy || !practitioner || !slot} style={{width: "100%"}}>
          {busy ? "Booking…" : "Confirm booking"}
        </button>
        {error && <div style={{marginTop: 16, padding: 12, background: "#fef2f2", borderRadius: 8, fontSize: 12, color: "#991b1b"}}>{error}</div>}
      </form>
    );
  }

  window.PortalBookDrawer = PortalBookDrawer;
})();
