// Encounter detail — read-only SOAP viewer wired to
// medic_plus.api.daystar_health.get_encounter_detail.
// Opened from the Appointments screen (row click when encounter exists,
// or after clicking "Start" on a pre-booked appointment).

function EncSection({ label, body }) {
  if (!body || !String(body).trim()) return null;
  return (
    <div className="card" style={{ marginTop: 10 }}>
      <div style={{ padding: '6px 14px 2px', fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ padding: '2px 14px 10px', fontSize: 13, color: 'var(--text-color)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
        {body}
      </div>
    </div>
  );
}

function EncounterSkeleton() {
  return (
    <div data-testid="encounter-skeleton" style={{ padding: 8 }}>
      {[200, 140, 100, 160, 120].map((w, i) => (
        <div key={i} style={{ height: 13, width: w, background: 'var(--bg-subtle)', borderRadius: 4, marginBottom: 14, animation: 'pulse 1.6s infinite' }} />
      ))}
    </div>
  );
}

function MEncounterScreen({ encounterId, go }) {
  const [state, setState] = mUseState({ status: 'loading', data: null, error: null });

  mUseEffect(() => {
    if (!encounterId) return;
    let cancelled = false;
    setState({ status: 'loading', data: null, error: null });
    window.meridianApi
      .call('medic_plus.api.daystar_health.get_encounter_detail', { encounter: encounterId })
      .then(data => { if (!cancelled) setState({ status: 'ready', data, error: null }); })
      .catch(err => {
        if (cancelled) return;
        const msg = err.message || 'Could not load encounter.';
        setState({ status: 'error', data: null, error: msg });
        window.meridianApi.showError(msg);
      });
    return () => { cancelled = true; };
  }, [encounterId]);

  if (state.status === 'loading') return <EncounterSkeleton />;
  if (state.status === 'error') {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
        {state.error}
      </div>
    );
  }

  const { encounter, problem_list } = state.data || {};
  if (!encounter) return null;

  const deskUrl = `/healthcare/patient-encounter/${encounterId}`;
  const assessmentBody = [
    encounter.assessment_code ? `ICD-10: ${encounter.assessment_code}` : '',
    encounter.assessment_text || '',
  ].filter(Boolean).join('\n');

  return (
    <div data-testid="encounter-detail">
      {/* Header */}
      <div style={{ marginBottom: 14, paddingBottom: 12, borderBottom: '1px solid var(--border-color)' }}>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
          {encounter.encounter_date || encounterId}
        </div>
        {encounter.chief_complaint && (
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-color)', marginBottom: 8 }}>
            {encounter.chief_complaint}
          </div>
        )}
        <a
          href={deskUrl}
          target="_blank"
          rel="noreferrer"
          className="btn btn-secondary btn-sm"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          data-testid="encounter-edit-in-desk"
        >
          Edit in Desk ↗
        </a>
      </div>

      {/* SOAP notes */}
      <EncSection label="History of Presenting Illness" body={encounter.hopi} />
      <EncSection label="Subjective (S)" body={encounter.subjective} />
      <EncSection label="Objective (O)" body={encounter.objective} />
      <EncSection label="Assessment (A)" body={assessmentBody} />
      <EncSection label="Plan (P)" body={encounter.plan} />

      {/* Examination Findings */}
      {encounter.examination_findings && encounter.examination_findings.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-header" style={{ padding: '8px 14px' }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>
              Examination Findings ({encounter.examination_findings.length})
            </h4>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ fontSize: 12 }}>
              <thead>
                <tr><th>System</th><th>Body Part</th><th>Finding</th><th>Abn.</th></tr>
              </thead>
              <tbody>
                {encounter.examination_findings.map((f, i) => (
                  <tr key={i} style={f.is_abnormal ? { color: 'var(--danger, #ef4444)' } : {}}>
                    <td>{f.body_system || '—'}</td>
                    <td>{f.body_part || '—'}</td>
                    <td>{f.finding || '—'}</td>
                    <td>{f.is_abnormal ? '⚠' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Orders */}
      {encounter.orders && encounter.orders.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-header" style={{ padding: '8px 14px' }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>
              Orders ({encounter.orders.length})
            </h4>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ fontSize: 12 }}>
              <thead>
                <tr><th>Type</th><th>Order</th><th>Status</th></tr>
              </thead>
              <tbody>
                {encounter.orders.map((o, i) => (
                  <tr key={i}>
                    <td>{o.order_type || '—'}</td>
                    <td>{o.order_name || '—'}</td>
                    <td><span className="badge badge-neutral">{o.status || '—'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Active Problem List */}
      {problem_list && problem_list.filter(p => p.status === 'Active').length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-header" style={{ padding: '8px 14px' }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>
              Active Problems ({problem_list.filter(p => p.status === 'Active').length})
            </h4>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ fontSize: 12 }}>
              <thead>
                <tr><th>Problem</th><th>ICD-10</th><th>Severity</th></tr>
              </thead>
              <tbody>
                {problem_list.filter(p => p.status === 'Active').map((p, i) => (
                  <tr key={i}>
                    <td>{p.description || '—'}</td>
                    <td className="mono">{p.icd10_code || '—'}</td>
                    <td>{p.severity || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

window.MEncounterScreen = MEncounterScreen;
