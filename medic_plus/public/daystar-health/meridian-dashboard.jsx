// Daystar Health Dashboard ("Today")
function MDashboardScreen({ go }) {
  const appts = window.MH_DATA.TODAY_APPTS;
  const patients = window.MH_DATA.PATIENTS;

  const kpis = [
    { label: 'Today\'s appointments', value: '12', sub: '3 checked in · 1 in room', trend: [8, 10, 12, 9, 11, 13, 12], color: '#2563eb' },
    { label: 'Active patients', value: '1,284', sub: '+18 this month', trend: [50, 53, 56, 60, 63, 66, 70], color: '#10b981' },
    { label: 'Outstanding labs', value: '23', sub: '4 critical results', trend: [18, 20, 19, 22, 21, 24, 23], color: '#f59e0b' },
    { label: 'Pending refills', value: '38', sub: '12 awaiting review', trend: [30, 32, 36, 34, 40, 38, 38], color: '#8b5cf6' },
  ];

  const week = [
    { d: 'Mon', visits: 18 }, { d: 'Tue', visits: 22 }, { d: 'Wed', visits: 19 },
    { d: 'Thu', visits: 24 }, { d: 'Fri', visits: 21 }, { d: 'Sat', visits: 8 }, { d: 'Sun', visits: 0 },
  ];

  return (
    <div className="page fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.02em' }}>
            Good morning, Dr. Patel
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>Wednesday, April 29 · {appts.length} patients on your schedule today.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm"><window.MIcons.Calendar size={14} /> View full schedule</button>
          <button className="btn btn-primary btn-sm"><window.MIcons.Plus size={14} /> New appointment</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--gap)', marginBottom: 'var(--gap)' }}>
        {kpis.map((k, i) => (
          <div key={i} className="kpi-tile">
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value">{k.value}</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
              <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{k.sub}</span>
              <div style={{ width: 70 }}><window.Sparkline data={k.trend} color={k.color} height={26} /></div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 'var(--gap)', marginBottom: 'var(--gap)' }}>
        {/* Today's schedule */}
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Today's schedule</h3>
              <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>Wed, Apr 29 · Dr. Patel & Dr. Okafor</div>
            </div>
            <div className="segment">
              <button className="active">Day</button>
              <button>Week</button>
              <button>Month</button>
            </div>
          </div>
          <div>
            {appts.map((a, i) => (
              <div key={i} onClick={() => go('patient', a.id)} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 20px', borderBottom: i < appts.length - 1 ? '1px solid var(--border)' : 'none', cursor: 'pointer' }}>
                <div style={{ width: 60, flexShrink: 0 }}>
                  <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{a.time}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>{a.dur} min</div>
                </div>
                <div style={{ width: 3, height: 36, background: a.kind === 'urgent' ? 'var(--danger)' : a.kind === 'followup' ? 'var(--info)' : 'var(--accent)', borderRadius: 2 }} />
                <div className="avatar avatar-sm" style={{ width: 32, height: 32, fontSize: 11 }}>
                  {a.patient.split(' ').map(n => n[0]).join('')}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 500 }}>{a.patient}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{a.reason} · {a.provider} · {a.room}</div>
                </div>
                <span className={`badge ${a.status === 'In room' ? 'badge-info' : a.status === 'Checked in' ? 'badge-success' : 'badge-neutral'}`}>{a.status}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right column: alerts + week chart */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Needs attention</h3>
              <span className="badge badge-warn">5</span>
            </div>
            <div>
              {[
                { icon: 'AlertTriangle', tone: 'urgent', who: 'James Whitaker', what: 'BP 142/94 — above target', when: '20 min ago', id: 'MH-10341' },
                { icon: 'Beaker', tone: 'watch', who: 'Eleanor Chen', what: 'A1c result requires review', when: '1h ago', id: 'MH-10042' },
                { icon: 'Pill', tone: 'watch', who: 'Robert Kim', what: 'Refill request: Tiotropium', when: '2h ago', id: 'MH-10744' },
                { icon: 'Mail', tone: 'normal', who: 'Marcus Rivera', what: 'Sent inhaler technique question', when: '3h ago', id: 'MH-10118' },
              ].map((a, i, arr) => {
                const Ic = window.MIcons[a.icon];
                const tone = a.tone === 'urgent' ? '#ef4444' : a.tone === 'watch' ? '#f59e0b' : '#3b82f6';
                return (
                  <div key={i} onClick={() => go('patient', a.id)} style={{ display: 'flex', gap: 10, padding: '12px 16px', borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none', cursor: 'pointer' }}>
                    <div style={{ width: 28, height: 28, borderRadius: 8, background: a.tone === 'urgent' ? 'var(--danger-soft)' : a.tone === 'watch' ? 'var(--warn-soft)' : 'var(--info-soft)', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                      <Ic size={14} stroke={tone} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, fontWeight: 500 }}>{a.who}</div>
                      <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{a.what}</div>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{a.when}</div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card card-pad">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
              <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: 0 }}>This week's volume</h3>
              <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>112 visits</span>
            </div>
            <svg viewBox="0 0 280 100" style={{ width: '100%', height: 100 }}>
              {week.map((d, i) => {
                const max = Math.max(...week.map(w => w.visits)) || 1;
                const h = (d.visits / max) * 70;
                const x = 20 + i * 36;
                return (
                  <g key={i}>
                    <rect x={x} y={80 - h} width="22" height={h} fill="var(--accent)" rx="3" opacity={i === 2 ? 1 : 0.55} />
                    <text x={x + 11} y="94" textAnchor="middle" fontSize="9" fill="var(--text-dim)" fontFamily="var(--font-mono)">{d.d}</text>
                    <text x={x + 11} y={76 - h} textAnchor="middle" fontSize="9" fill="var(--text-muted)" fontFamily="var(--font-mono)">{d.visits || ''}</text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      </div>

      {/* Bottom: recent patients */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recently seen patients</h3>
          <button className="btn btn-ghost btn-sm" onClick={() => go('patients')}>All patients</button>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr><th>Patient</th><th>MRN</th><th>Last visit</th><th>Conditions</th><th>Risk</th><th>Status</th><th>Next appt</th></tr>
            </thead>
            <tbody>
              {patients.slice(0, 6).map(p => (
                <tr key={p.id} onClick={() => go('patient', p.id)}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div className="avatar avatar-sm" style={{ width: 28, height: 28, fontSize: 10 }}>{p.name.split(' ').map(n => n[0]).join('')}</div>
                      <div>
                        <div style={{ fontWeight: 500 }}>{p.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{p.age} {p.sex} · {p.primary}</div>
                      </div>
                    </div>
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{p.mrn}</td>
                  <td>{p.lastSeen}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{p.conditions.slice(0, 2).join(', ') || '—'}</td>
                  <td><span className={`badge ${p.risk === 'High' ? 'badge-danger' : p.risk === 'Moderate' ? 'badge-warn' : 'badge-success'}`}>{p.risk}</span></td>
                  <td><span className={`badge ${p.status === 'Stable' ? 'pill-stable' : p.status === 'Watch' ? 'pill-watch' : 'pill-urgent'}`} style={{ background: p.status === 'Stable' ? 'var(--success-soft)' : p.status === 'Watch' ? 'var(--warn-soft)' : 'var(--danger-soft)' }}>{p.status}</span></td>
                  <td className="mono" style={{ fontSize: 12 }}>{p.nextAppt}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

window.MDashboardScreen = MDashboardScreen;
