// New Visit drawer — creates a Patient Encounter (with optional linked
// Patient Appointment) via /api/resource.  custom_practice is auto-set
// server-side by set_practice_on_insert hook.  Practice membership +
// DocPerm fixtures gate write access; server errors surface as red alerts.
//
// Sections: Schedule → SOAP → Examination Findings → Orders.
// Examination Findings and Orders are child-table rows appended before POST.

const NV_SECTIONS = [
  { id: 'schedule', label: 'Schedule' },
  { id: 'soap', label: 'SOAP Notes' },
  { id: 'exam', label: 'Examination' },
  { id: 'orders', label: 'Orders' },
];

const NV_BODY_SYSTEMS = ['General', 'Cardiovascular', 'Respiratory', 'Gastrointestinal',
  'Neurological', 'Musculoskeletal', 'Dermatological', 'ENT', 'Ophthalmology',
  'Genitourinary', 'Endocrine', 'Psychiatric', 'Other'];

function nvInitialForm(today) {
  return {
    patient: '',
    practitioner: '',
    encounter_date: today,
    encounter_time: '09:00',
    appointment_type: '',
    chief_complaint: '',
    hopi: '',
    subjective: '',
    objective: '',
    assessment_text: '',
    assessment_code: '',
    plan: '',
  };
}

// Module-scope so React keeps a stable component identity across MNewVisitDrawer
// re-renders. Defining this inside the parent caused every input to remount on
// every keystroke (and lose focus, popover state, etc.).
function NVField({ label, children, span = 1, required = false }) {
  return (
    <label
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        fontSize: 12,
        color: 'var(--text-muted)',
        gridColumn: span > 1 ? `span ${span}` : undefined,
      }}
    >
      <span style={{ fontWeight: 500 }}>
        {label}
        {required && <span className="nv-required" aria-hidden="true" style={{ color: 'var(--danger, #ef4444)', marginLeft: 3 }}>*</span>}
      </span>
      {children}
    </label>
  );
}

function NVSectionTabs({ active, onSelect }) {
  const onKey = (e) => {
    const idx = NV_SECTIONS.findIndex((s) => s.id === active);
    if (idx < 0) return;
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      onSelect(NV_SECTIONS[(idx + 1) % NV_SECTIONS.length].id);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      onSelect(NV_SECTIONS[(idx - 1 + NV_SECTIONS.length) % NV_SECTIONS.length].id);
    } else if (e.key === 'Home') {
      e.preventDefault();
      onSelect(NV_SECTIONS[0].id);
    } else if (e.key === 'End') {
      e.preventDefault();
      onSelect(NV_SECTIONS[NV_SECTIONS.length - 1].id);
    }
  };
  return (
    <div
      role="tablist"
      aria-label="Encounter sections"
      onKeyDown={onKey}
      style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', marginBottom: 16, gap: 0 }}
    >
      {NV_SECTIONS.map((s) => {
        const isActive = s.id === active;
        return (
          <button
            key={s.id}
            type="button"
            role="tab"
            id={`new-visit-tab-${s.id}`}
            aria-selected={isActive}
            aria-controls={`new-visit-panel-${s.id}`}
            tabIndex={isActive ? 0 : -1}
            data-testid={`visit-tab-${s.id}`}
            onClick={() => onSelect(s.id)}
            style={{
              padding: '6px 14px',
              fontSize: 12,
              border: 'none',
              cursor: 'pointer',
              borderBottom: isActive ? '2px solid var(--primary)' : '2px solid transparent',
              background: 'none',
              fontWeight: isActive ? 600 : 400,
              color: isActive ? 'var(--text-color)' : 'var(--text-muted)',
            }}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}

function MNewVisitDrawer({ open, onClose, onCreated, prefillPatient }) {
  const api = window.meridianApi || {};
  const today = new Date().toISOString().slice(0, 10);

  const [form, setForm] = React.useState(() => ({
    ...nvInitialForm(today),
    patient: prefillPatient || '',
  }));

  const [examFindings, setExamFindings] = React.useState([]);
  const [orders, setOrders] = React.useState([]);

  const [patients, setPatients] = React.useState([]);
  const [practitioners, setPractitioners] = React.useState([]);
  const [appointmentTypes, setAppointmentTypes] = React.useState([]);
  const [icd10Query, setIcd10Query] = React.useState('');
  const [icd10Results, setIcd10Results] = React.useState([]);

  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [missingFields, setMissingFields] = React.useState(() => new Set());
  const [activeSection, setActiveSection] = React.useState('schedule');

  // Load reference lists when the drawer opens. Cancellation flag prevents
  // late responses from updating state after the drawer closes.
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError(null);
    setMissingFields(new Set());
    setActiveSection('schedule');
    api.resource('Patient', { fields: JSON.stringify(['name', 'patient_name']), order_by: 'patient_name asc', limit_page_length: 200 })
      .then((rows) => { if (!cancelled) setPatients((rows && rows.data) || []); })
      .catch(() => { if (!cancelled) setPatients([]); });
    api.resource('Healthcare Practitioner', { fields: JSON.stringify(['name', 'practitioner_name']), order_by: 'practitioner_name asc', limit_page_length: 200 })
      .then((rows) => { if (!cancelled) setPractitioners((rows && rows.data) || []); })
      .catch(() => { if (!cancelled) setPractitioners([]); });
    api.resource('Appointment Type', { fields: JSON.stringify(['name']), order_by: 'name asc', limit_page_length: 200 })
      .then((rows) => {
        if (cancelled) return;
        const list = (rows && rows.data) || [];
        setAppointmentTypes(list);
        setForm((f) => f.appointment_type || !list.length ? f : { ...f, appointment_type: list[0].name });
      })
      .catch(() => { if (!cancelled) setAppointmentTypes([]); });
    return () => { cancelled = true; };
  }, [open]);

  React.useEffect(() => {
    if (open && prefillPatient) setForm((f) => ({ ...f, patient: prefillPatient }));
  }, [open, prefillPatient]);

  // ICD-10 search (debounced 300ms). Cancellation flag drops late responses.
  React.useEffect(() => {
    if (!icd10Query || icd10Query.length < 2) { setIcd10Results([]); return; }
    let cancelled = false;
    const timer = setTimeout(() => {
      api.call('medic_plus.api.daystar_health.search_icd10', { query: icd10Query, limit: 10 })
        .then((res) => { if (!cancelled) setIcd10Results((res && res.message) || []); })
        .catch(() => { if (!cancelled) setIcd10Results([]); });
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [icd10Query]);

  const update = (k, v) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (missingFields.has(k) && v) {
      setMissingFields((prev) => {
        const next = new Set(prev);
        next.delete(k);
        return next;
      });
    }
  };

  const addFinding = () => setExamFindings((prev) => [
    ...prev,
    { body_system: 'General', body_part: '', finding: '', is_abnormal: 0 },
  ]);
  const updateFinding = (i, k, v) => setExamFindings((prev) => prev.map((r, idx) => idx === i ? { ...r, [k]: v } : r));
  const removeFinding = (i) => setExamFindings((prev) => prev.filter((_, idx) => idx !== i));

  const addOrder = () => setOrders((prev) => [
    ...prev,
    { order_type: 'Lab', order_name: '', status: 'Draft' },
  ]);
  const updateOrder = (i, k, v) => setOrders((prev) => prev.map((r, idx) => idx === i ? { ...r, [k]: v } : r));
  const removeOrder = (i) => setOrders((prev) => prev.filter((_, idx) => idx !== i));

  const submit = async () => {
    const missing = new Set();
    if (!form.patient) missing.add('patient');
    if (!form.practitioner) missing.add('practitioner');
    if (!form.encounter_date) missing.add('encounter_date');
    if (!form.chief_complaint) missing.add('chief_complaint');
    if (missing.size > 0) {
      setMissingFields(missing);
      setError('Patient, practitioner, date and chief complaint are required.');
      setActiveSection('schedule');
      return;
    }
    setSubmitting(true);
    setError(null);
    setMissingFields(new Set());
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
      setForm(nvInitialForm(today));
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

  const ariaInvalid = (k) => (missingFields.has(k) ? 'true' : undefined);
  const ariaDescribedBy = (k) => (missingFields.has(k) ? 'new-visit-error' : undefined);

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
        <div
          className="card"
          id="new-visit-error"
          role="alert"
          aria-live="assertive"
          style={{ marginBottom: 12, padding: 10, background: 'var(--danger-soft)', borderColor: 'var(--danger)' }}
        >
          <div style={{ fontSize: 13, color: '#b91c1c' }}>{error}</div>
        </div>
      )}

      <NVSectionTabs active={activeSection} onSelect={setActiveSection} />

      {/* ── Schedule ───────────────────────────────────────────────────────── */}
      {activeSection === 'schedule' && (
        <div
          role="tabpanel"
          id="new-visit-panel-schedule"
          aria-labelledby="new-visit-tab-schedule"
          style={{ display: 'grid', gap: 14, gridTemplateColumns: '1fr 1fr' }}
        >
          <NVField label="Patient" required>
            <window.MSelect
              data-testid="new-visit-patient"
              value={form.patient}
              onChange={(v) => update('patient', v)}
              options={patients.map((p) => ({ value: p.name, label: p.patient_name || p.name }))}
              placeholder="Select patient…"
              searchable
              aria-invalid={ariaInvalid('patient')}
              aria-describedby={ariaDescribedBy('patient')}
            />
          </NVField>
          <NVField label="Practitioner" required>
            <window.MSelect
              data-testid="new-visit-practitioner"
              value={form.practitioner}
              onChange={(v) => update('practitioner', v)}
              options={practitioners.map((p) => ({ value: p.name, label: p.practitioner_name || p.name }))}
              placeholder="Select practitioner…"
              searchable
              aria-invalid={ariaInvalid('practitioner')}
              aria-describedby={ariaDescribedBy('practitioner')}
            />
          </NVField>
          <NVField label="Date" required>
            <window.MDatePicker
              data-testid="new-visit-date"
              value={form.encounter_date}
              onChange={(v) => update('encounter_date', v)}
              aria-invalid={ariaInvalid('encounter_date')}
              aria-describedby={ariaDescribedBy('encounter_date')}
            />
          </NVField>
          <NVField label="Time">
            <window.MTimePicker
              data-testid="new-visit-time"
              value={form.encounter_time}
              onChange={(v) => update('encounter_time', v)}
            />
          </NVField>
          <NVField label="Type" span={2}>
            <window.MSelect
              data-testid="new-visit-type"
              value={form.appointment_type}
              onChange={(v) => update('appointment_type', v)}
              options={appointmentTypes.map((t) => ({ value: t.name, label: t.name }))}
              placeholder="Select type…"
            />
          </NVField>
          <NVField label="Chief Complaint" span={2} required>
            <input
              type="text"
              data-testid="new-visit-chief-complaint"
              value={form.chief_complaint}
              onChange={(e) => update('chief_complaint', e.target.value)}
              className="input"
              placeholder="Presenting complaint…"
              aria-invalid={ariaInvalid('chief_complaint')}
              aria-describedby={ariaDescribedBy('chief_complaint')}
            />
          </NVField>
        </div>
      )}

      {/* ── SOAP Notes ─────────────────────────────────────────────────────── */}
      {activeSection === 'soap' && (
        <div
          role="tabpanel"
          id="new-visit-panel-soap"
          aria-labelledby="new-visit-tab-soap"
          style={{ display: 'flex', flexDirection: 'column', gap: 14 }}
        >
          <window.MTextArea
            data-testid="new-visit-hopi"
            label="History of Presenting Illness"
            rows={3}
            value={form.hopi}
            onChange={(v) => update('hopi', v)}
            placeholder="Background and history…"
          />
          <window.MTextArea
            data-testid="new-visit-subjective"
            label="Subjective (S)"
            rows={3}
            value={form.subjective}
            onChange={(v) => update('subjective', v)}
            placeholder="Patient's description of symptoms…"
          />
          <window.MTextArea
            data-testid="new-visit-objective"
            label="Objective (O)"
            rows={3}
            value={form.objective}
            onChange={(v) => update('objective', v)}
            placeholder="Vital signs, physical findings…"
          />
          <window.MTextArea
            data-testid="new-visit-assessment-text"
            label="Assessment (A)"
            rows={2}
            value={form.assessment_text}
            onChange={(v) => update('assessment_text', v)}
            placeholder="Clinical impression / diagnosis…"
          />
          <NVField label="ICD-10 Code">
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
          </NVField>
          <window.MTextArea
            data-testid="new-visit-plan"
            label="Plan (P)"
            rows={3}
            value={form.plan}
            onChange={(v) => update('plan', v)}
            placeholder="Treatment plan, follow-up, referrals…"
          />
        </div>
      )}

      {/* ── Examination Findings ───────────────────────────────────────────── */}
      {activeSection === 'exam' && (
        <div
          role="tabpanel"
          id="new-visit-panel-exam"
          aria-labelledby="new-visit-tab-exam"
        >
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
                <window.MSelect
                  value={row.body_system}
                  onChange={(v) => updateFinding(i, 'body_system', v)}
                  options={NV_BODY_SYSTEMS.map((s) => ({ value: s, label: s }))}
                />
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
              <button
                className="btn btn-ghost btn-xs"
                onClick={() => removeFinding(i)}
                aria-label={`Remove finding ${i + 1}`}
                title="Remove"
              >
                ✕
              </button>
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
        <div
          role="tabpanel"
          id="new-visit-panel-orders"
          aria-labelledby="new-visit-tab-orders"
        >
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
                <window.MSelect
                  value={row.order_type}
                  onChange={(v) => updateOrder(i, 'order_type', v)}
                  options={[
                    { value: 'Lab', label: 'Lab' },
                    { value: 'Imaging', label: 'Imaging' },
                    { value: 'Referral', label: 'Referral' },
                    { value: 'Immunisation', label: 'Immunisation' },
                  ]}
                />
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
              <button
                className="btn btn-ghost btn-xs"
                onClick={() => removeOrder(i)}
                aria-label={`Remove order ${i + 1}`}
                title="Remove"
              >
                ✕
              </button>
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
