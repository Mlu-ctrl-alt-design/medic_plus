// Patient detail — wired to medic_plus.api.daystar_health.get_patient_detail.
// One composite fetch, six tabs hydrate from the bundle. POPIA: SA ID is
// never returned by the endpoint, so it cannot leak into the UI here.

const PATIENT_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'visits', label: 'Visits' },
  { id: 'vitals', label: 'Vitals' },
  { id: 'medications', label: 'Medications' },
  { id: 'labs', label: 'Labs' },
  { id: 'notes', label: 'Notes' },
];

function MPatientScreen({ go, patientId }) {
  const [tab, setTab] = mUseState('overview');
  const [state, setState] = mUseState({ status: 'loading', data: null, error: null });

  mUseEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', data: null, error: null });
    window.meridianApi
      .call('medic_plus.api.daystar_health.get_patient_detail', { patient: patientId })
      .then(data => { if (!cancelled) setState({ status: 'ready', data, error: null }); })
      .catch(err => {
        if (cancelled) return;
        const msg = err.message || 'Could not load patient.';
        setState({ status: 'error', data: null, error: msg });
        window.meridianApi.showError(msg);
      });
    return () => { cancelled = true; };
  }, [patientId]);

  if (state.status === 'loading') return <PatientSkeleton />;
  if (state.status === 'error') return <PatientError message={state.error} go={go} />;

  const data = state.data;
  const p = data.patient || {};
  const links = data.full_record_links || {};

  return (
    <div className="page fade-in" data-testid="patient-detail-page">
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <div className="avatar" style={{ width: 56, height: 56, fontSize: 18, borderRadius: 14 }}>
          {(p.patient_name || p.name || '?').split(' ').map(n => n[0]).join('').slice(0, 2)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 data-testid="patient-name" style={{ fontSize: 22, fontWeight: 600, margin: 0, letterSpacing: '-0.02em' }}>
            {p.patient_name || p.name}
          </h1>
          <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 4 }}>
            {[p.sex, p.dob ? `DOB ${p.dob}` : null, p.email, p.mobile].filter(Boolean).join(' · ') || '—'}
          </div>
        </div>
        <span className={`badge ${p.status === 'Active' ? 'badge-success' : 'badge-neutral'}`}>{p.status || '—'}</span>
      </div>

      <div className="tabs" data-testid="patient-tabs" style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', marginBottom: 16 }}>
        {PATIENT_TABS.map(t => (
          <button
            key={t.id}
            data-testid={`patient-tab-${t.id}`}
            className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <OverviewTab data={data} />}
      {tab === 'visits' && <VisitsTab visits={data.visits || []} link={links.visits} />}
      {tab === 'vitals' && <VitalsTab vitals={data.vitals || []} link={links.vitals} />}
      {tab === 'medications' && <MedicationsTab meds={data.medications || []} link={links.medications} />}
      {tab === 'labs' && <LabsTab labs={data.labs || []} link={links.labs} />}
      {tab === 'notes' && <NotesTab notes={data.notes || []} link={links.notes} />}
    </div>
  );
}

function PatientSkeleton() {
  return (
    <div className="page fade-in" data-testid="patient-skeleton">
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <div style={{ width: 56, height: 56, borderRadius: 14, background: 'var(--bg-subtle)', animation: 'pulse 1.6s infinite' }} />
        <div style={{ flex: 1 }}>
          <PSkeletonBar w={220} h={20} />
          <div style={{ height: 8 }} />
          <PSkeletonBar w={300} h={14} />
        </div>
      </div>
      <div className="card card-pad"><PSkeletonBar w="100%" h={140} /></div>
    </div>
  );
}

function PSkeletonBar({ w = '100%', h = 14 }) {
  return <div style={{ width: w, height: h, background: 'var(--bg-subtle)', borderRadius: 4, animation: 'pulse 1.6s infinite' }} />;
}

function PatientError({ message, go }) {
  return (
    <div className="page fade-in">
      <div className="card card-pad" data-testid="patient-error" style={{ textAlign: 'center', padding: 60 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 8px' }}>Couldn't load patient</h2>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>{message}</p>
        <button className="btn btn-secondary btn-sm" onClick={() => go('patients')}>Back to patients</button>
      </div>
    </div>
  );
}

function OverviewTab({ data }) {
  const p = data.patient || {};
  const latestVitals = (data.vitals || [])[0];
  return (
    <div data-testid="patient-tab-content-overview" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap)' }}>
      <div className="card card-pad">
        <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: '0 0 12px' }}>Demographics</h3>
        <KV label="Name" value={p.patient_name || p.name} />
        <KV label="Sex" value={p.sex} />
        <KV label="Date of birth" value={p.dob} />
        <KV label="Email" value={p.email} />
        <KV label="Mobile" value={p.mobile} />
      </div>
      <div className="card card-pad">
        <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: '0 0 12px' }}>Latest vitals</h3>
        {latestVitals ? (
          <>
            <KV label="Date" value={latestVitals.date} />
            <KV label="BP" value={latestVitals.bp_systolic && latestVitals.bp_diastolic ? `${latestVitals.bp_systolic}/${latestVitals.bp_diastolic}` : null} />
            <KV label="Weight" value={latestVitals.weight} />
            <KV label="Temperature" value={latestVitals.temperature} />
          </>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No vitals recorded yet.</div>
        )}
      </div>
      <div className="card card-pad" style={{ gridColumn: '1 / -1' }}>
        <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: '0 0 12px' }}>Activity at a glance</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          <Stat label="Visits" value={(data.visits || []).length} />
          <Stat label="Active medications" value={(data.medications || []).length} />
          <Stat label="Lab tests" value={(data.labs || []).length} />
          <Stat label="Notes" value={(data.notes || []).length} />
        </div>
      </div>
    </div>
  );
}

function KV({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontWeight: 500 }}>{value || '—'}</span>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, marginTop: 4 }}>{value}</div>
    </div>
  );
}

function VisitsTab({ visits, link }) {
  return (
    <div className="card" data-testid="patient-tab-content-visits">
      <div className="card-header">
        <h3 className="card-title">Recent visits ({visits.length})</h3>
        {link && <a href={link} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" data-testid="patient-tab-link-visits">See full record →</a>}
      </div>
      {visits.length === 0 ? (
        <EmptyTab name="visits" />
      ) : (
        <table className="table">
          <thead><tr><th>Date</th><th>Type</th><th>Practitioner</th><th>Department</th></tr></thead>
          <tbody>
            {visits.map(v => (
              <tr key={v.id}>
                <td className="mono">{v.date || '—'}</td>
                <td>{v.type || '—'}</td>
                <td>{v.practitioner || '—'}</td>
                <td>{v.department || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function VitalsTab({ vitals, link }) {
  return (
    <div className="card" data-testid="patient-tab-content-vitals">
      <div className="card-header">
        <h3 className="card-title">Latest vitals ({vitals.length})</h3>
        {link && <a href={link} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" data-testid="patient-tab-link-vitals">See full record →</a>}
      </div>
      {vitals.length === 0 ? (
        <EmptyTab name="vital signs" />
      ) : (
        <table className="table">
          <thead><tr><th>Date</th><th>BP</th><th>Weight</th><th>Temperature</th><th>Resp.</th></tr></thead>
          <tbody>
            {vitals.map(v => (
              <tr key={v.id}>
                <td className="mono">{v.date || '—'}</td>
                <td>{v.bp_systolic && v.bp_diastolic ? `${v.bp_systolic}/${v.bp_diastolic}` : '—'}</td>
                <td>{v.weight || '—'}</td>
                <td>{v.temperature || '—'}</td>
                <td>{v.respiratory_rate || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function MedicationsTab({ meds, link }) {
  return (
    <div className="card" data-testid="patient-tab-content-medications">
      <div className="card-header">
        <h3 className="card-title">Active medications ({meds.length})</h3>
        {link && <a href={link} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" data-testid="patient-tab-link-medications">See full record →</a>}
      </div>
      {meds.length === 0 ? (
        <EmptyTab name="medications" />
      ) : (
        <table className="table">
          <thead><tr><th>Drug</th><th>Dosage</th><th>Period</th><th>Started</th></tr></thead>
          <tbody>
            {meds.map(m => (
              <tr key={m.id}>
                <td style={{ fontWeight: 500 }}>{m.name || '—'}</td>
                <td>{m.dosage || '—'}</td>
                <td>{m.period || '—'}</td>
                <td className="mono">{m.started || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function LabsTab({ labs, link }) {
  return (
    <div className="card" data-testid="patient-tab-content-labs">
      <div className="card-header">
        <h3 className="card-title">Lab tests ({labs.length})</h3>
        {link && <a href={link} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" data-testid="patient-tab-link-labs">See full record →</a>}
      </div>
      {labs.length === 0 ? (
        <EmptyTab name="lab tests" />
      ) : (
        <table className="table">
          <thead><tr><th>Test</th><th>Status</th><th>Result date</th></tr></thead>
          <tbody>
            {labs.map(l => (
              <tr key={l.id}>
                <td>{l.template || l.id}</td>
                <td><span className="badge badge-neutral">{l.status || '—'}</span></td>
                <td className="mono">{l.result_date || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function NotesTab({ notes, link }) {
  return (
    <div className="card" data-testid="patient-tab-content-notes">
      <div className="card-header">
        <h3 className="card-title">Notes ({notes.length})</h3>
        {link && <a href={link} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" data-testid="patient-tab-link-notes">See full record →</a>}
      </div>
      {notes.length === 0 ? (
        <EmptyTab name="notes" />
      ) : (
        <div>
          {notes.map((n, i) => (
            <div key={n.id} style={{ padding: '14px 20px', borderBottom: i < notes.length - 1 ? '1px solid var(--border)' : 'none' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 12 }}>
                <span style={{ fontWeight: 500 }}>{n.author || '—'}</span>
                <span style={{ color: 'var(--text-dim)' }}>{n.when || ''}</span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }} dangerouslySetInnerHTML={{ __html: n.body || '' }} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyTab({ name }) {
  return (
    <div data-testid="patient-tab-empty" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
      No {name} recorded for this patient yet.
    </div>
  );
}

window.MPatientScreen = MPatientScreen;
