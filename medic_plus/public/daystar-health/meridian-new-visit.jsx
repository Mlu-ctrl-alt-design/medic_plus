// New Visit drawer — creates a Patient Appointment via /api/resource.
// custom_practice is auto-set server-side by set_practice_on_insert hook,
// so we don't pass it from the client. Practice membership + DocPerm
// fixtures (Issue #12) gate write access; the drawer surfaces server
// errors verbatim so PermissionError flows back as a red alert.

function MNewVisitDrawer({ open, onClose, onCreated, prefillPatient }) {
  const api = window.meridianApi || {};
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = React.useState({
    patient: prefillPatient || '',
    practitioner: '',
    appointment_date: today,
    appointment_time: '09:00',
    duration: 15,
    appointment_type: '',
    notes: '',
  });
  const [patients, setPatients] = React.useState([]);
  const [practitioners, setPractitioners] = React.useState([]);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (!open) return;
    setError(null);
    api.resource('Patient', { fields: JSON.stringify(['name', 'patient_name']), order_by: 'patient_name asc', limit_page_length: 200 })
      .then((rows) => setPatients((rows && rows.data) || []))
      .catch(() => setPatients([]));
    api.resource('Healthcare Practitioner', { fields: JSON.stringify(['name', 'practitioner_name']), order_by: 'practitioner_name asc', limit_page_length: 200 })
      .then((rows) => setPractitioners((rows && rows.data) || []))
      .catch(() => setPractitioners([]));
  }, [open]);

  React.useEffect(() => {
    if (open && prefillPatient) setForm((f) => ({ ...f, patient: prefillPatient }));
  }, [open, prefillPatient]);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.patient || !form.practitioner || !form.appointment_date || !form.appointment_time) {
      setError('Patient, practitioner, date and time are all required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        doctype: 'Patient Appointment',
        patient: form.patient,
        practitioner: form.practitioner,
        appointment_date: form.appointment_date,
        appointment_time: form.appointment_time,
        duration: form.duration ? Number(form.duration) : 15,
      };
      if (form.appointment_type) payload.appointment_type = form.appointment_type;
      if (form.notes) payload.notes = form.notes;

      const response = await fetch('/api/method/frappe.client.insert', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': api.bootstrap.csrfToken || '',
          Accept: 'application/json',
        },
        body: JSON.stringify({ doc: JSON.stringify(payload) }),
      });
      const text = await response.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch { data = text; }
      if (!response.ok) {
        let msg = `Create failed (${response.status})`;
        if (data && data._server_messages) {
          try {
            const list = JSON.parse(data._server_messages);
            if (list.length) msg = JSON.parse(list[0]).message || msg;
          } catch {}
        } else if (data && data.exception) {
          msg = data.exception;
        }
        throw new Error(msg);
      }
      const created = (data && (data.message || data)) || null;
      if (onCreated) onCreated(created);
      // reset form for next open
      setForm({
        patient: '', practitioner: '', appointment_date: today,
        appointment_time: '09:00', duration: 15, appointment_type: '', notes: '',
      });
      onClose && onClose();
    } catch (err) {
      setError(err.message || 'Could not create appointment.');
    } finally {
      setSubmitting(false);
    }
  };

  const Field = ({ label, children }) => (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}>
      <span style={{ fontWeight: 500 }}>{label}</span>
      {children}
    </label>
  );

  return (
    <window.MDrawer
      open={open}
      onClose={onClose}
      title="New visit"
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn btn-primary btn-sm" data-testid="new-visit-submit" onClick={submit} disabled={submitting}>
            {submitting ? 'Creating…' : 'Create appointment'}
          </button>
        </>
      }
    >
      {error && (
        <div className="card" style={{ marginBottom: 16, padding: 12, background: 'var(--danger-soft)', borderColor: 'var(--danger)' }}>
          <div style={{ fontSize: 13, color: '#b91c1c' }}>{error}</div>
        </div>
      )}
      <div style={{ display: 'grid', gap: 14, gridTemplateColumns: '1fr 1fr' }}>
        <Field label="Patient">
          <select data-testid="new-visit-patient" value={form.patient} onChange={(e) => update('patient', e.target.value)} className="input">
            <option value="">Select patient…</option>
            {patients.map((p) => (
              <option key={p.name} value={p.name}>{p.patient_name || p.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Practitioner">
          <select data-testid="new-visit-practitioner" value={form.practitioner} onChange={(e) => update('practitioner', e.target.value)} className="input">
            <option value="">Select practitioner…</option>
            {practitioners.map((p) => (
              <option key={p.name} value={p.name}>{p.practitioner_name || p.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Date">
          <input type="date" data-testid="new-visit-date" value={form.appointment_date} onChange={(e) => update('appointment_date', e.target.value)} className="input" />
        </Field>
        <Field label="Time">
          <input type="time" data-testid="new-visit-time" value={form.appointment_time} onChange={(e) => update('appointment_time', e.target.value)} className="input" />
        </Field>
        <Field label="Duration (min)">
          <input type="number" min="5" step="5" value={form.duration} onChange={(e) => update('duration', e.target.value)} className="input" />
        </Field>
        <Field label="Type">
          <input type="text" placeholder="Consultation, follow-up…" value={form.appointment_type} onChange={(e) => update('appointment_type', e.target.value)} className="input" />
        </Field>
      </div>
      <div style={{ marginTop: 14 }}>
        <Field label="Notes">
          <textarea rows={3} value={form.notes} onChange={(e) => update('notes', e.target.value)} className="input" style={{ resize: 'vertical', minHeight: 60 }} />
        </Field>
      </div>
    </window.MDrawer>
  );
}

window.MNewVisitDrawer = MNewVisitDrawer;
