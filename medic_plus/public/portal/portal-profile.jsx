(function() {
  const { useEffect, useState } = React;

  const FIELDS = [
    { name: "first_name", label: "First name", type: "text" },
    { name: "middle_name", label: "Middle name", type: "text" },
    { name: "last_name", label: "Last name", type: "text" },
    { name: "dob", label: "Date of birth", type: "date" },
    { name: "sex", label: "Sex", type: "select", options: ["Male", "Female", "Other"] },
    { name: "blood_group", label: "Blood group", type: "select", options: ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] },
    { name: "marital_status", label: "Marital status", type: "select", options: ["Single", "Married", "Divorced", "Widowed"] },
    { name: "mobile", label: "Mobile", type: "tel" },
    { name: "phone", label: "Phone", type: "tel" },
    { name: "email", label: "Email", type: "email" },
    { name: "occupation", label: "Occupation", type: "text" },
    { name: "address_line1", label: "Address line 1", type: "text" },
    { name: "address_line2", label: "Address line 2", type: "text" },
    { name: "city", label: "City", type: "text" },
    { name: "state", label: "State", type: "text" },
    { name: "zip_code", label: "Zip code", type: "text" },
    { name: "country", label: "Country", type: "text" },
    { name: "allergies", label: "Allergies (self-reported)", type: "textarea" },
    { name: "medication", label: "Current medication (self-reported)", type: "textarea" },
  ];

  function PortalProfileScreen() {
    const slug = window.portalApi.slug;
    const [me, setMe] = useState(null);
    const [form, setForm] = useState({});
    const [busy, setBusy] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.get_me", { slug })
        .then((m) => { setMe(m); setForm(m); });
    }, []);

    function update(name, value) {
      setForm((f) => ({ ...f, [name]: value }));
      setSaved(false);
    }

    async function save() {
      setBusy(true); setError(""); setSaved(false);
      const payload = {};
      for (const f of FIELDS) {
        const cur = form[f.name];
        const orig = me ? me[f.name] : null;
        if ((cur || "") !== (orig || "")) payload[f.name] = cur || null;
      }
      if (Object.keys(payload).length === 0) { setBusy(false); return; }
      try {
        const updated = await window.portalApi.call("medic_plus.api.patient_portal.update_me", { slug, payload });
        setMe(updated); setForm(updated); setSaved(true);
      } catch (e) {
        setError(e.message);
      } finally { setBusy(false); }
    }

    if (!me) return <window.PortalLoading />;

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 4}}>My profile</h1>
        <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 20}}>
          Update your contact details and personal information. Clinical history is managed by your practice.
        </div>

        <div style={{display: "grid", gap: 12}}>
          {FIELDS.map((f) => (
            <div key={f.name} className="portal-form-field">
              <label>{f.label}</label>
              {f.type === "textarea" ? (
                <window.MTextArea value={form[f.name] || ""} onChange={(v) => update(f.name, v)} rows={3} />
              ) : f.type === "select" ? (
                <window.MSelect
                  value={form[f.name] || ""}
                  onChange={(v) => update(f.name, v)}
                  options={f.options.map(o => ({ value: o, label: o }))}
                  placeholder="—"
                />
              ) : f.type === "date" ? (
                <window.MDatePicker value={form[f.name] || ""} onChange={(v) => update(f.name, v)} placeholder="YYYY-MM-DD" />
              ) : (
                <input type={f.type} value={form[f.name] || ""} onChange={(e) => update(f.name, e.target.value)}
                  className="portal-input" />
              )}
            </div>
          ))}
        </div>

        <div style={{position: "sticky", bottom: 16, marginTop: 24, display: "flex", gap: 8, alignItems: "center"}}>
          <button className="portal-cta" onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </button>
          {saved && <span style={{fontSize: 12, color: "#059669"}}>Saved</span>}
          {error && <span style={{fontSize: 12, color: "#991b1b"}}>{error}</span>}
        </div>
      </div>
    );
  }

  window.PortalProfileScreen = PortalProfileScreen;
})();
