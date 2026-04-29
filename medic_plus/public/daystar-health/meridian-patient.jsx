// Patient detail
function MPatientScreen({ go, patientId }) {
  const p = window.MH_DATA.PATIENTS.find(x => x.id === patientId) || window.MH_DATA.PATIENTS[0];
  const [tab, setTab] = mUseState('overview');
  const visits = window.MH_DATA.VISITS_FOR(p.id);
  const labs = window.MH_DATA.LABS_FOR(p.id);
  const meds = window.MH_DATA.MEDS_FOR(p.id);
  const notes = window.MH_DATA.NOTES_FOR(p.id);
  const trend = window.MH_DATA.VITALS_TREND_FOR(p.id);

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'visits', label: 'Visits', count: visits.length },
    { id: 'vitals', label: 'Vitals' },
    { id: 'medications', label: 'Medications', count: meds.length },
    { id: 'labs', label: 'Labs', count: labs.length },
    { id: 'notes', label: 'Notes', count: notes.length },
  ];

  return (
    <div className="page fade-in">
      {/* Header */}
      <div style={{ display: 'flex', gap: 18, alignItems: 'flex-start', marginBottom: 20 }}>
        <div className="avatar" style={{ width: 64, height: 64, fontSize: 22, borderRadius: 16 }}>
          {p.name.split(' ').map(n => n[0]).join('')}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <h1 style={{ fontSize: 22, fontWeight: 600, margin: 0, letterSpacing: '-0.02em' }}>{p.name}</h1>
            <span className={`badge ${p.status === 'Stable' ? 'badge-success' : p.status === 'Watch' ? 'badge-warn' : 'badge-danger'}`}>{p.status}</span>
            <span className={`badge ${p.risk === 'High' ? 'badge-danger' : p.risk === 'Moderate' ? 'badge-warn' : 'badge-neutral'}`}>{p.risk} risk</span>
            {p.allergies.length > 0 && <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><window.MIcons.AlertTriangle size={11} /> Allergy alert</span>}
          </div>
          <div style={{ display: 'flex', gap: 18, fontSize: 12.5, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <span><span className="mono">{p.mrn}</span></span>
            <span>{p.age} yrs · {p.sex}</span>
            <span>DOB {p.dob}</span>
            <span>{p.insurance}</span>
            <span>PCP: {p.primary}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm"><window.MIcons.Mail size={14} /> Message</button>
          <button className="btn btn-secondary btn-sm"><window.MIcons.Calendar size={14} /> Schedule</button>
          <button className="btn btn-primary btn-sm"><window.MIcons.Plus size={14} /> Start visit</button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: 'var(--gap)' }}>
        {tabs.map(t => (
          <button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            {t.label}{t.count != null && <span style={{ fontSize: 11, color: 'var(--text-dim)', marginLeft: 6 }}>{t.count}</span>}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--gap)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
            {/* Vitals snapshot */}
            <div className="card card-pad">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
                <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: 0 }}>Latest vitals</h3>
                <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>Recorded Apr 21, 2026</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14 }}>
                {[
                  { label: 'BP', value: p.vitals.bp, unit: 'mmHg', tone: p.vitals.bp.split('/')[0] > 130 ? 'warn' : 'ok' },
                  { label: 'HR', value: p.vitals.hr, unit: 'bpm', tone: 'ok' },
                  { label: 'SpO₂', value: p.vitals.spo2, unit: '%', tone: p.vitals.spo2 < 95 ? 'warn' : 'ok' },
                  { label: 'Weight', value: p.vitals.weight, unit: '', tone: 'ok' },
                  { label: 'BMI', value: p.vitals.bmi, unit: '', tone: p.vitals.bmi > 25 ? 'warn' : 'ok' },
                ].map((v, i) => (
                  <div key={i} style={{ paddingLeft: i > 0 ? 14 : 0, borderLeft: i > 0 ? '1px solid var(--border)' : 'none' }}>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{v.label}</div>
                    <div style={{ fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', letterSpacing: '-0.02em', color: v.tone === 'warn' ? '#b45309' : 'var(--text)' }}>{v.value}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>{v.unit}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* BP trend */}
            <div className="card card-pad">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
                <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: 0 }}>Blood pressure — last 12 visits</h3>
                <div style={{ display: 'flex', gap: 12, fontSize: 11.5 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: '#2563eb' }} />Systolic</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: '#94a3b8' }} />Diastolic</span>
                </div>
              </div>
              <svg viewBox="0 0 480 160" style={{ width: '100%', height: 160 }}>
                {/* gridlines */}
                {[40, 60, 80, 100, 120].map((y, i) => (
                  <g key={i}>
                    <line x1="40" x2="470" y1={y} y2={y} stroke="var(--border)" strokeDasharray="2 3" />
                    <text x="32" y={y + 3} textAnchor="end" fontSize="9" fill="var(--text-dim)" fontFamily="var(--font-mono)">{160 - y}</text>
                  </g>
                ))}
                {/* target band */}
                <rect x="40" y={160 - 130} width="430" height="20" fill="#10b981" opacity="0.08" />
                {/* lines */}
                {(() => {
                  const sx = (i) => 40 + i * (430 / 11);
                  const sy = (v) => 160 - v;
                  const path = (arr) => arr.map((v, i) => `${i === 0 ? 'M' : 'L'} ${sx(i)} ${sy(v)}`).join(' ');
                  return (
                    <>
                      <path d={path(trend.bp_sys)} fill="none" stroke="#2563eb" strokeWidth="2" />
                      <path d={path(trend.bp_dia)} fill="none" stroke="#94a3b8" strokeWidth="2" />
                      {trend.bp_sys.map((v, i) => <circle key={'s'+i} cx={sx(i)} cy={sy(v)} r="2.5" fill="#2563eb" />)}
                      {trend.bp_dia.map((v, i) => <circle key={'d'+i} cx={sx(i)} cy={sy(v)} r="2.5" fill="#94a3b8" />)}
                    </>
                  );
                })()}
              </svg>
            </div>

            {/* Recent visits */}
            <div className="card">
              <div className="card-header"><h3 className="card-title">Recent visits</h3><button className="btn btn-ghost btn-sm" onClick={() => setTab('visits')}>All visits</button></div>
              <div>
                {visits.slice(0, 3).map((v, i) => (
                  <div key={i} style={{ padding: '14px 20px', borderBottom: i < 2 ? '1px solid var(--border)' : 'none' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 500 }}>{v.reason}</div>
                      <div className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{v.date}</div>
                    </div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-dim)', marginBottom: 6 }}>{v.type} · {v.provider}</div>
                    <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{v.notes}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
            {/* Contact */}
            <div className="card card-pad">
              <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: '0 0 12px' }}>Contact</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12.5 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--text-dim)' }}>Phone</span><span className="mono">{p.phone}</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--text-dim)' }}>Email</span><span>{p.email}</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--text-dim)' }}>Insurance</span><span>{p.insurance}</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--text-dim)' }}>Last seen</span><span className="mono">{p.lastSeen}</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--text-dim)' }}>Next appt</span><span className="mono" style={{ color: 'var(--accent-text)', fontWeight: 500 }}>{p.nextAppt}</span></div>
              </div>
            </div>

            {/* Conditions */}
            <div className="card card-pad">
              <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: '0 0 10px' }}>Active conditions</h3>
              {p.conditions.length === 0 ? (
                <div style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>None on file.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {p.conditions.map((c, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12.5 }}>
                      <window.MIcons.Heart size={13} stroke="var(--accent)" />
                      <span style={{ flex: 1 }}>{c}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Allergies */}
            <div className="card card-pad">
              <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: '0 0 10px' }}>Allergies</h3>
              {p.allergies.length === 0 ? (
                <div style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>NKDA — No known drug allergies.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {p.allergies.map((a, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: 'var(--danger-soft)', borderRadius: 6, fontSize: 12.5, color: '#b91c1c' }}>
                      <window.MIcons.AlertTriangle size={13} />
                      <span style={{ flex: 1, fontWeight: 500 }}>{a}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'visits' && (
        <div className="card">
          <div className="card-header"><h3 className="card-title">Visit history</h3><button className="btn btn-primary btn-sm"><window.MIcons.Plus size={14} /> New visit</button></div>
          <div>
            {visits.map((v, i) => (
              <div key={i} style={{ padding: '16px 20px', borderBottom: i < visits.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <div>
                    <span style={{ fontSize: 14, fontWeight: 500 }}>{v.reason}</span>
                    <span className="badge badge-neutral" style={{ marginLeft: 8 }}>{v.type}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{v.date} · {v.provider}</div>
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{v.notes}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'vitals' && (
        <div className="card card-pad">
          <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: '0 0 14px' }}>Vitals trends</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap)' }}>
            {[
              { label: 'Heart rate (bpm)', data: trend.hr, color: '#ef4444' },
              { label: 'Weight (lb)', data: trend.weight, color: '#8b5cf6' },
            ].map((s, i) => (
              <div key={i} className="card card-pad">
                <h4 style={{ fontSize: 12.5, fontWeight: 500, margin: '0 0 10px', color: 'var(--text-muted)' }}>{s.label}</h4>
                <window.Sparkline data={s.data} color={s.color} height={80} />
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'medications' && (
        <div className="card">
          <div className="card-header"><h3 className="card-title">Active medications</h3><button className="btn btn-primary btn-sm"><window.MIcons.Plus size={14} /> Prescribe</button></div>
          <table className="table">
            <thead><tr><th>Medication</th><th>Dose</th><th>Frequency</th><th>Class</th><th>Started</th><th>Refills</th><th>Status</th></tr></thead>
            <tbody>
              {meds.map((m, i) => (
                <tr key={i}>
                  <td><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><window.MIcons.Pill size={14} stroke="var(--accent)" /><span style={{ fontWeight: 500 }}>{m.name}</span></div></td>
                  <td className="mono">{m.dose}</td>
                  <td style={{ fontSize: 12.5 }}>{m.freq}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12.5 }}>{m.class}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{m.start}</td>
                  <td className="mono">{m.refills}</td>
                  <td><span className="badge badge-success">{m.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'labs' && (
        <div className="card">
          <div className="card-header"><h3 className="card-title">Lab results — Apr 21, 2026</h3><button className="btn btn-secondary btn-sm"><window.MIcons.Download size={14} /> Export PDF</button></div>
          <table className="table">
            <thead><tr><th>Test</th><th style={{ textAlign: 'right' }}>Value</th><th>Unit</th><th>Reference</th><th>Status</th></tr></thead>
            <tbody>
              {labs.map((l, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 500 }}>{l.name}</td>
                  <td className="mono" style={{ textAlign: 'right', fontWeight: 600, color: l.status === 'High' ? '#b45309' : l.status === 'Low' ? '#1d4ed8' : 'var(--text)' }}>{l.value}</td>
                  <td style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{l.unit}</td>
                  <td className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{l.range}</td>
                  <td><span className={`badge ${l.status === 'Normal' ? 'badge-success' : l.status === 'High' ? 'badge-warn' : 'badge-info'}`}>{l.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'notes' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
          <div className="card card-pad">
            <textarea className="textarea" rows="3" placeholder="Add a clinical note…" style={{ marginBottom: 10 }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn btn-secondary btn-sm">Save draft</button>
              <button className="btn btn-primary btn-sm">Sign & save</button>
            </div>
          </div>
          {notes.map((n, i) => (
            <div key={i} className="card card-pad">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div className="avatar avatar-sm" style={{ width: 26, height: 26, fontSize: 10 }}>{n.author.split(' ').map(s => s[0]).join('').slice(0, 2)}</div>
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{n.author}</span>
                </div>
                <span className="mono" style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{n.when}</span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55 }}>{n.body}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

window.MPatientScreen = MPatientScreen;
