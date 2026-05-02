// New Visit drawer — creates a Patient Encounter (with optional linked
// Patient Appointment) via /api/resource.  custom_practice is auto-set
// server-side by set_practice_on_insert hook.  Practice membership +
// DocPerm fixtures gate write access; server errors surface as red alerts.
//
// Sections: Schedule → SOAP → Examination Findings → Orders.
// Examination Findings and Orders are child-table rows appended before POST.

function MNewVisitDrawer({ open, onClose, onCreated, prefillPatient }) {
  const api = window.meridianApi || {};
  const today = new Date().toISOString().slice(0, 10);

  // ── Scheduling fields ──────────────────────────────────────────────────────
  const [form, setForm] = React.useState({
    patient: prefillPatient || '',
    practitioner: '',
    encounter_date: today,
    encounter_time: '09:00',
    appointment_type: '',
    // SOAP
    chief_complaint: '',
    hopi: '',
    subjective: '',
    objective: '',
    assessment_text: '',
    assessment_code: '',
    plan: '',
  });

  // ── Child rows ─────────────────────────────────────────────────────────────
  const [examFindings, setExamFindings] = React.useState([]);
  const [orders, setOrders] = React.useState([]);

  // ── Remote data ────────────────────────────────────────────────────────────
  const [patients, setPatients] = React.useState([]);
  const [practitioners, setPractitioners] = React.useState([]);
  const [appointmentTypes, setAppointmentTypes] = React.useState([]);
  const [icd10Query, setIcd10Query] = React.useState('');
  const [icd10Results, setIcd10Results] = React.useState([]);

  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [activeSection, setActiveSection] = React.useState('schedule');

  // ── Load reference lists on open ──────────────────────────────────────────
  React.useEffect(() => {
    if (!open) return;
    setError(null);
    setActiveSection('schedule');
    api.resource('Patient', { fields: JSON.stringify(['name', 'patient_name']), order_by: 'patient_name asc', limit_page_length: 200 })
      .then((rows) => setPatients((rows && rows.data) || []))
      .catch(() => setPatients([]));
    api.resource('Healthcare Practitioner', { fields: JSON.stringify(['name', 'practitioner_name']), order_by: 'practitioner_name asc', limit_page_length: 200 })
      .then((rows) => setPractitioners((rows && rows.data) || []))
      .catch(() => setPractitioners([]));
    api.resource('Appointment Type', { fields: JSON.stringify(['name']), order_by: 'name asc', limit_page_length: 200 })
      .then((rows) => {
        const list = (rows && rows.data) || [];
        setAppointmentTypes(list);
        setForm((f) => f.appointment_type || !list.length ? f : { ...f, appointment_type: list[0].name });
      })
      .catch(() => setAppointmentTypes([]));
  }, [open]);

  React.useEffect(() => {
    if (open && prefillPatient) setForm((f) => ({ ...f, patient: prefillPatient }));
  }, [open, prefillPatient]);

  // ── ICD-10 search (debounced 300ms) ────────────────────────────────────────
  React.useEffect(() => {
    if (!icd10Query || icd10Query.length < 2) { setIcd10Results([]); return; }
    const timer = setTimeout(() => {
      api.call('medic_plus.api.daystar_health.search_icd10', { query: icd10Query, limit: 10 })
        .then((res) => setIcd10Results((res && res.message) || []))
        .catch(() => setIcd10Results([]));
    }, 300);
    return () => clearTimeout(timer);
  }, [icd10Query]);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  // ── Examination Findings helpers ───────────────────────────────────────────
  const addFinding = () => setExamFindings((prev) => [
    ...prev,
    { body_system: 'General', body_part: '', finding: '', is_abnormal: 0 },
  ]);
  const updateFinding = (i, k, v) => setExamFindings((prev) => prev.map((r, idx) => idx === i ? { ...r, [k]: v } : r));
  const removeFinding = (i) => setExamFindings((prev) => prev.filter((_, idx) => idx !== i));

  // ── Orders helpers ─────────────────────────────────────────────────────────
  const addOrder = () => setOrders((prev) => [
    ...prev,
    { order_type: 'Lab', order_name: '', status: 'Draft' },
  ]);
  const updateOrder = (i, k, v) => setOrders((prev) => prev.map((r, idx) => idx === i ? { ...r, [k]: v } : r));
  const removeOrder = (i) => setOrders((prev) => prev.filter((_, idx) => idx !== i));

  // ── Submit ─────────────────────────────────────────────────────────────────
  const submit = async () => {
    if (!form.patient || !form.practitioner || !form.encounter_date || !form.chief_complaint) {
      setError('Patient, practitioner, date and chief complaint are required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        doctype: 'Patient Encounter',
        patient: form.patient,
        practitioner: form.practitioner,
        encounter_date: form.encounter_date,
        encounter_time: form.encounter_time ? form.encounter_time + ':00' : '09:00:00',
        custom_chief_complaint: form.chief_complaint,
        custom_hopi: form.hopi || '',
        custom_subjective: form.subjective || '',
        custom_objective: form.objective || '',
        custom_assessment_text: form.assessment_text || '',
        custom_assessment_code: form.assessment_code || '',
        custom_plan: form.plan || '',
        custom_examination_findings: examFindings.filter((r) => r.body_part && r.finding),
        custom_encounter_orders: orders.filter((r) => r.order_name),
      };
      if (form.appointment_type) payload.appointment_type = form.appointment_type;

      const response = await fetch('/api/method/frappe.client.insert', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': (api.bootstrap && api.bootstrap.csrfToken) || '',
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
      // Reset for next open
      setForm({
        patient: '', practitioner: '', encounter_date: today,
        encounter_time: '09:00', appointment_type: '',
        chief_complaint: '', hopi: '', subjective: '',
        objective: '', assessment_text: '', assessment_code: '', plan: '',
      });
      setExamFindings([]);
      setOrders([]);
      setIcd10Query('');
      setIcd10Results([]);
      onClose && onClose();
    } catch (err) {
      setError(err.message || 'Could not create encounter.');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Layout helpers ─────────────────────────────────────────────────────────
  const Field = ({ label, children, span = 1 }) => (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--text-muted)', gridColumn: span > 1 ? `span ${span}` : undefined }}>
      <span style={{ fontWeight: 500 }}>{label}</span>
      {children}
    </label>
  );

  const SectionTab = ({ id, label }) => (
    <button
      data-testid={`visit-tab-${id}`}
      onClick={() => setActiveSection(id)}
      style={{
        padding: '6px 14px', fontSize: 12, border: 'none', cursor: 'pointer',
        borderBottom: activeSection === id ? '2px solid var(--primary)' : '2px solid transparent',
        background: 'none', fontWeight: activeSection === id ? 600 : 400,
        color: activeSection === id ? 'var(--text-color)' : 'var(--text-muted)',
      }}
    >
      {label}
    </button>
  );

  const BODY_SYSTEMS = ['General', 'Cardiovascular', 'Respiratory', 'Gastrointestinal',
    'Neurological', 'Musculoskeletal', 'Dermatological', 'ENT', 'Ophthalmology',
    'Genitourinary', 'Endocrine', 'Psychiatric', 'Other'];

  return (
    <window.MDrawer
      open={open}
      onClose={onClose}
      title="New encounter"
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={submitting}>Cancel</button>
          <button
            className="btn btn-primary btn-sm"
            data-testid="new-visit-submit"
            onClick={submit}
            disabled={submitting}
          >
            {submitting ? 'Creating…' : 'Create encounter'}
          </button>
        </>
      }
    >
      {error && (
        <div className="card" style={{ marginBottom: 12, padding: 10, background: 'var(--danger-soft)', borderColor: 'var(--danger)' }}>
          <div style={{ fontSize: 13, color: '#b91c1c' }}>{error}</div>
        </div>
      )}

      {/* Section tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', marginBottom: 16, gap: 0 }}>
        <SectionTab id="schedule" label="Schedule" />
        <SectionTab id="soap" label="SOAP Notes" />
        <SectionTab id="exam" label="Examination" />
        <SectionTab id="orders" label="Orders" />
      </div>

      {/* ── Schedule ───────────────────────────────────────────────────────── */}
      {activeSection === 'schedule' && (
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
            <input type="date" data-testid="new-visit-date" value={form.encounter_date} onChange={(e) => update('encounter_date', e.target.value)} className="input" />
          </Field>
          <Field label="Time">
            <input type="time" data-testid="new-visit-time" value={form.encounter_time} onChange={(e) => update('encounter_time', e.target.value)} className="input" />
          </Field>
          <Field label="Type" span={2}>
            <select data-testid="new-visit-type" value={form.appointment_type} onChange={(e) => update('appointment_type', e.target.value)} className="input">
              <option value="">Select type…</option>
              {appointmentTypes.map((t) => (
                <option key={t.name} value={t.name}>{t.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Chief Complaint" span={2}>
            <input
              type="text"
              data-testid="new-visit-chief-complaint"
              value={form.chief_complaint}
              onChange={(e) => update('chief_complaint', e.target.value)}
              className="input"
              placeholder="Presenting complaint…"
            />
          </Field>
        </div>
      )}

      {/* ── SOAP Notes ─────────────────────────────────────────────────────── */}
      {activeSection === 'soap' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="History of Presenting Illness">
            <textarea
              data-testid="new-visit-hopi"
              rows={3}
              value={form.hopi}
              onChange={(e) => update('hopi', e.target.value)}
              className="input"
              style={{ resize: 'vertical', minHeight: 60 }}
              placeholder="Background and history…"
            />
          </Field>
          <Field label="Subjective (S)">
            <textarea
              data-testid="new-visit-subjective"
              rows={3}
              value={form.subjective}
              onChange={(e) => update('subjective', e.target.value)}
              className="input"
              style={{ resize: 'vertical', minHeight: 60 }}
              placeholder="Patient's description of symptoms…"
            />
          </Field>
          <Field label="Objective (O)">
            <textarea
              data-testid="new-visit-objective"
              rows={3}
              value={form.objective}
              onChange={(e) => update('objective', e.target.value)}
              className="input"
              style={{ resize: 'vertical', minHeight: 60 }}
              placeholder="Vital signs, physical findings…"
            />
          </Field>
          <Field label="Assessment (A)">
            <textarea
              data-testid="new-visit-assessment-text"
              rows={2}
              value={form.assessment_text}
              onChange={(e) => update('assessment_text', e.target.value)}
              className="input"
              style={{ resize: 'vertical', minHeight: 48 }}
              placeholder="Clinical impression / diagnosis…"
            />
          </Field>
          {/* ICD-10 code picker */}
          <Field label="ICD-10 Code">
            <div style={{ position: 'relative' }}>
              {form.assessment_code ? (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span
                    data-testid="new-visit-assessment-code-selected"
                    className="input"
                    style={{ flex: 1, background: 'var(--control-bg)', color: 'var(--text-color)' }}
                  >
                    {form.assessment_code}
                  </span>
                  <button
                    className="btn btn-ghost btn-xs"
                    onClick={() => { update('assessment_code', ''); setIcd10Query(''); }}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <>
                  <input
                    type="text"
                    data-testid="new-visit-icd10-search"
                    value={icd10Query}
                    onChange={(e) => setIcd10Query(e.target.value)}
                    className="input"
                    placeholder="Search ICD-10 code or description…"
                  />
                  {icd10Results.length > 0 && (
                    <div style={{
                      position: 'absolute', top: '100%', left: 0, right: 0,
                      background: 'var(--card-bg)', border: '1px solid var(--border-color)',
                      borderRadius: 4, zIndex: 100, maxHeight: 200, overflowY: 'auto',
                    }}>
                      {icd10Results.map((r) => (
                        <div
                          key={r.name}
                          data-testid={`icd10-result-${r.code}`}
                          onClick={() => { update('assessment_code', r.name); setIcd10Query(''); setIcd10Results([]); }}
                          style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12 }}
                          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--control-bg)'}
                          onMouseLeave={(e) => e.currentTarget.style.background = ''}
                        >
                          <strong>{r.code}</strong> — {r.display}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </Field>
          <Field label="Plan (P)">
            <textarea
              data-testid="new-visit-plan"
              rows={3}
              value={form.plan}
              onChange={(e) => update('plan', e.target.value)}
              className="input"
              style={{ resize: 'vertical', minHeight: 60 }}
              placeholder="Treatment plan, follow-up, referrals…"
            />
          </Field>
        </div>
      )}

      {/* ── Examination Findings ───────────────────────────────────────────── */}
      {activeSection === 'exam' && (
        <div>
          {examFindings.length === 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 12 }}>
              No examination findings added.
            </div>
          )}
          {examFindings.map((row, i) => (
            <div
              key={i}
              data-testid={`exam-finding-row-${i}`}
              style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr auto', gap: 8, marginBottom: 8, alignItems: 'end' }}
            >
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>System</div>
                <select
                  value={row.body_system}
                  onChange={(e) => updateFinding(i, 'body_system', e.target.value)}
                  className="input"
                  style={{ fontSize: 12 }}
                >
                  {BODY_SYSTEMS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>Body Part</div>
                <input
                  type="text"
                  value={row.body_part}
                  onChange={(e) => updateFinding(i, 'body_part', e.target.value)}
                  className="input"
                  placeholder="e.g. Chest"
                  style={{ fontSize: 12 }}
                />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>Finding</div>
                <input
                  type="text"
                  value={row.finding}
                  onChange={(e) => updateFinding(i, 'finding', e.target.value)}
                  className="input"
                  placeholder="Describe finding…"
                  style={{ fontSize: 12 }}
                />
              </div>
              <button className="btn btn-ghost btn-xs" onClick={() => removeFinding(i)} title="Remove">✕</button>
            </div>
          ))}
          <button
            data-testid="add-exam-finding"
            className="btn btn-ghost btn-sm"
            onClick={addFinding}
            style={{ marginTop: 4 }}
          >
            + Add finding
          </button>
        </div>
      )}

      {/* ── Encounter Orders ───────────────────────────────────────────────── */}
      {activeSection === 'orders' && (
        <div>
          {orders.length === 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 12 }}>
              No orders added.
            </div>
          )}
          {orders.map((row, i) => (
            <div
              key={i}
              data-testid={`order-row-${i}`}
              style={{ display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: 8, marginBottom: 8, alignItems: 'end' }}
            >
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>Type</div>
                <select
                  value={row.order_type}
                  onChange={(e) => updateOrder(i, 'order_type', e.target.value)}
                  className="input"
                  style={{ fontSize: 12 }}
                >
                  <option value="Lab">Lab</option>
                  <option value="Imaging">Imaging</option>
                  <option value="Referral">Referral</option>
                  <option value="Immunisation">Immunisation</option>
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>Order Name</div>
                <input
                  type="text"
                  value={row.order_name}
                  onChange={(e) => updateOrder(i, 'order_name', e.target.value)}
                  className="input"
                  placeholder="e.g. Full Blood Count"
                  style={{ fontSize: 12 }}
                />
              </div>
              <button className="btn btn-ghost btn-xs" onClick={() => removeOrder(i)} title="Remove">✕</button>
            </div>
          ))}
          <button
            data-testid="add-order"
            className="btn btn-ghost btn-sm"
            onClick={addOrder}
            style={{ marginTop: 4 }}
          >
            + Add order
          </button>
        </div>
      )}
    </window.MDrawer>
  );
}

window.MNewVisitDrawer = MNewVisitDrawer;
