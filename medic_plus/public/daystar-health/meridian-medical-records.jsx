// Medical Records — practice-wide list of Patient Medical Record rows
// (Frappe Healthcare's auto-populated clinical timeline). Read-only;
// click a row to open the patient drawer where the clinician can see
// the full per-patient context.

const PMR_TYPES = [
  'Patient Encounter',
  'Lab Test',
  'Vital Signs',
  'Sick Note',
  'Inpatient Record',
];
const PMR_FILTERS_KEY = 'daystar.medicalRecords.filters';
const PMR_PAGE_SIZE = 50;

function _readSavedFilters() {
  try {
    const raw = sessionStorage.getItem(PMR_FILTERS_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch { return null; }
}

function _saveFilters(f) {
  try { sessionStorage.setItem(PMR_FILTERS_KEY, JSON.stringify(f)); } catch {}
}

function _initialFilters() {
  const today = new Date();
  const past = new Date(today);
  past.setDate(today.getDate() - 30);
  const fmt = (d) => d.toISOString().slice(0, 10);
  return _readSavedFilters() || {
    patient: '',
    reference_doctype: [],
    date_from: fmt(past),
    date_to: fmt(today),
  };
}

function MMedicalRecordsScreen({ go }) {
  const init = _initialFilters();
  const [filters, setFilters] = mUseState(init);
  const [debFilters, setDebFilters] = mUseState(init);
  const [page, setPage] = mUseState(0);
  const [state, setState] = mUseState({ status: 'loading', rows: [], total: 0, error: null });

  // Debounce filter changes 300ms.
  mUseEffect(() => {
    const t = setTimeout(() => {
      setDebFilters(filters);
      setPage(0);
      _saveFilters(filters);
    }, 300);
    return () => clearTimeout(t);
  }, [filters]);

  // Fetch on debounced filter / page change.
  mUseEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, status: 'loading', error: null }));
    const apiFilters = {
      date_from: debFilters.date_from,
      date_to: debFilters.date_to,
    };
    if (debFilters.patient) apiFilters.patient = debFilters.patient;
    if (debFilters.reference_doctype && debFilters.reference_doctype.length) {
      apiFilters.reference_doctype = debFilters.reference_doctype;
    }
    window.meridianApi
      .call('medic_plus.api.daystar_health.get_medical_records', {
        filters: apiFilters,
        limit_start: page * PMR_PAGE_SIZE,
        limit_page_length: PMR_PAGE_SIZE,
      })
      .then((data) => {
        if (cancelled) return;
        setState({
          status: 'ready',
          rows: (data && data.rows) || [],
          total: (data && data.total) || 0,
          error: null,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = (err && err.message) || 'Could not load medical records.';
        setState({ status: 'error', rows: [], total: 0, error: msg });
        window.meridianApi.showError(msg);
      });
    return () => { cancelled = true; };
  }, [debFilters, page]);

  const update = (k, v) => setFilters((f) => ({ ...f, [k]: v }));
  const toggleType = (t) => setFilters((f) => {
    const next = (f.reference_doctype || []).includes(t)
      ? f.reference_doctype.filter((x) => x !== t)
      : [...(f.reference_doctype || []), t];
    return { ...f, reference_doctype: next };
  });

  const total = state.total;
  const startIdx = total === 0 ? 0 : page * PMR_PAGE_SIZE + 1;
  const endIdx = Math.min((page + 1) * PMR_PAGE_SIZE, total);
  const pageCount = Math.max(1, Math.ceil(total / PMR_PAGE_SIZE));

  return (
    <div className="page fade-in" data-testid="medical-records-page">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em', margin: 0 }}>Medical Records</h1>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }} data-testid="medical-records-count">
          {state.status === 'loading' ? 'Loading…' : `${startIdx}–${endIdx} of ${total}`}
        </div>
      </div>

      <div className="card card-pad toolbar" style={{ marginBottom: 16, display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--text-muted)', flex: '1 1 200px' }}>
          <span style={{ fontWeight: 500 }}>Patient (name)</span>
          <input
            type="text"
            data-testid="pmr-filter-patient"
            placeholder="Filter by Patient ID (HLC-PAT-…)"
            value={filters.patient}
            onChange={(e) => update('patient', e.target.value.trim())}
            className="input"
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ fontWeight: 500 }}>From</span>
          <input
            type="date"
            data-testid="pmr-filter-from"
            value={filters.date_from}
            onChange={(e) => update('date_from', e.target.value)}
            className="input"
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ fontWeight: 500 }}>To</span>
          <input
            type="date"
            data-testid="pmr-filter-to"
            value={filters.date_to}
            onChange={(e) => update('date_to', e.target.value)}
            className="input"
          />
        </label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignSelf: 'center' }} data-testid="pmr-filter-types">
          {PMR_TYPES.map((t) => {
            const active = (filters.reference_doctype || []).includes(t);
            return (
              <button
                key={t}
                onClick={() => toggleType(t)}
                className={`btn btn-sm ${active ? 'btn-primary' : 'btn-ghost'}`}
              >
                {t}
              </button>
            );
          })}
        </div>
      </div>

      <div className="card" data-testid="medical-records-list">
        {state.status === 'loading' && (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>Loading…</div>
        )}
        {state.status === 'error' && (
          <div style={{ padding: 24, textAlign: 'center', color: '#b91c1c', fontSize: 13 }}>{state.error}</div>
        )}
        {state.status === 'ready' && state.rows.length === 0 && (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }} data-testid="medical-records-empty">
            No medical records match these filters.
          </div>
        )}
        {state.status === 'ready' && state.rows.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 110 }}>Date</th>
                <th>Patient</th>
                <th style={{ width: 150 }}>Type</th>
                <th>Subject</th>
                <th style={{ width: 160 }}>By</th>
                <th style={{ width: 32 }}></th>
              </tr>
            </thead>
            <tbody>
              {state.rows.map((r) => (
                <tr
                  key={r.name}
                  data-testid="pmr-row"
                  onClick={() => go('patient', r.patient)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>{r.communication_date}</td>
                  <td>{r.patient_name || r.patient}</td>
                  <td><span className="badge badge-neutral">{r.reference_doctype}</span></td>
                  <td style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{r.subject || '—'}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-dim)' }}>{r.user || '—'}</td>
                  <td>{r.has_attach && <window.MIcons.Download size={14} />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {pageCount > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 16 }}>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Page {page + 1} of {pageCount}</span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

window.MMedicalRecordsScreen = MMedicalRecordsScreen;
