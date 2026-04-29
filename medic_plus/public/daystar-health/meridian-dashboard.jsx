// Daystar Health Dashboard ("Today") — wired to medic_plus.api.daystar_health.get_dashboard.
// Static MH_DATA mocks have been removed; the screen now hydrates from the
// Practice-scoped endpoint and renders skeletons during load.

function MDashboardScreen({ go }) {
  const [state, setState] = mUseState({ status: 'loading', data: null, error: null });

  mUseEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', data: null, error: null });
    window.meridianApi
      .call('medic_plus.api.daystar_health.get_dashboard')
      .then((data) => { if (!cancelled) setState({ status: 'ready', data, error: null }); })
      .catch((err) => {
        if (cancelled) return;
        setState({ status: 'error', data: null, error: err.message || 'Could not load dashboard.' });
        window.meridianApi.showError(err.message || 'Could not load dashboard.');
      });
    return () => { cancelled = true; };
  }, []);

  if (state.status === 'loading') return <DashboardSkeleton />;
  if (state.status === 'error') return <DashboardError message={state.error} />;
  return <DashboardReady go={go} data={state.data} />;
}

function DashboardSkeleton() {
  return (
    <div className="page fade-in" data-testid="dashboard-skeleton">
      <div style={{ marginBottom: 24 }}>
        <SkeletonBar w={260} h={26} />
        <div style={{ height: 8 }} />
        <SkeletonBar w={360} h={14} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--gap)', marginBottom: 'var(--gap)' }}>
        {[0, 1, 2].map(i => (
          <div key={i} className="kpi-tile">
            <SkeletonBar w={120} h={12} />
            <div style={{ height: 8 }} />
            <SkeletonBar w={80} h={26} />
          </div>
        ))}
      </div>
      <div className="card card-pad"><SkeletonBar w="100%" h={140} /></div>
    </div>
  );
}

function SkeletonBar({ w = '100%', h = 14 }) {
  return <div style={{ width: w, height: h, background: 'var(--bg-subtle)', borderRadius: 4, animation: 'pulse 1.6s infinite' }} />;
}

function DashboardError({ message }) {
  return (
    <div className="page fade-in">
      <div className="card card-pad" data-testid="dashboard-error" style={{ textAlign: 'center', padding: 60 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 8px' }}>Couldn't load dashboard</h2>
        <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>{message}</p>
      </div>
    </div>
  );
}

function DashboardReady({ go, data }) {
  const today = data.today_schedule || [];
  const recent = data.recent_patients || [];
  const week = data.week_volume || [];
  const apptKpi = (data.kpis && data.kpis.today_appointments) || { value: 0, breakdown: {} };
  const activeKpi = (data.kpis && data.kpis.active_patients) || { value: 0 };
  const labKpi = (data.kpis && data.kpis.outstanding_labs) || { value: 0 };
  const subtitleParts = Object.entries(apptKpi.breakdown || {}).map(([k, v]) => `${v} ${k.toLowerCase()}`);
  const subtitleText = subtitleParts.length ? subtitleParts.join(' · ') : 'No appointments today';

  return (
    <div className="page fade-in" data-testid="dashboard-ready">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 data-testid="dashboard-greeting" style={{ fontSize: 22, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.02em' }}>
            {data.greeting}
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>{data.today_label} · {today.length} patients on your schedule today.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <a className="btn btn-secondary btn-sm" href={data.view_full_schedule_url} target="_blank" rel="noreferrer" data-testid="view-full-schedule">
            <window.MIcons.Calendar size={14} /> View full schedule
          </a>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--gap)', marginBottom: 'var(--gap)' }}>
        <KpiTile label="Today's appointments" value={apptKpi.value} subtitle={subtitleText} testId="kpi-today-appointments" />
        <KpiTile label="Active patients" value={activeKpi.value} subtitle="Across the practice" testId="kpi-active-patients" />
        <KpiTile label="Outstanding labs" value={labKpi.value} subtitle="Open or in progress" testId="kpi-outstanding-labs" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 'var(--gap)', marginBottom: 'var(--gap)' }}>
        <TodaysSchedule today={today} go={go} todayLabel={data.today_label} />
        <WeekVolumeCard week={week} />
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recently seen patients</h3>
          <button className="btn btn-ghost btn-sm" onClick={() => go('patients')}>All patients</button>
        </div>
        <div style={{ overflowX: 'auto' }} data-testid="recent-patients">
          {recent.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              No patient encounters yet.
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Patient</th><th>Last visit</th></tr>
              </thead>
              <tbody>
                {recent.map(p => (
                  <tr key={p.id} onClick={() => go('patient', p.id)}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div className="avatar avatar-sm" style={{ width: 28, height: 28, fontSize: 10 }}>
                          {(p.name || '?').split(' ').map(n => n[0]).join('').slice(0, 2)}
                        </div>
                        <div>
                          <div style={{ fontWeight: 500 }}>{p.name || '—'}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                            {p.age != null ? `${p.age}` : '—'} {p.sex || ''}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>{p.last_seen || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function KpiTile({ label, value, subtitle, testId }) {
  return (
    <div className="kpi-tile" data-testid={testId}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{subtitle}</div>
    </div>
  );
}

function TodaysSchedule({ today, go, todayLabel }) {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Today's schedule</h3>
          <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>{todayLabel}</div>
        </div>
      </div>
      <div data-testid="today-schedule">
        {today.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            No appointments scheduled for today.
          </div>
        ) : today.map((a, i) => (
          <div key={a.id} onClick={() => go('patient', a.patient_id)} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 20px', borderBottom: i < today.length - 1 ? '1px solid var(--border)' : 'none', cursor: 'pointer' }}>
            <div style={{ width: 60, flexShrink: 0 }}>
              <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{a.time}</div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>{a.duration} min</div>
            </div>
            <div className="avatar avatar-sm" style={{ width: 32, height: 32, fontSize: 11 }}>
              {(a.patient_name || '?').split(' ').map(n => n[0]).join('').slice(0, 2)}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 500 }}>{a.patient_name}</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{a.reason || '—'} · {a.practitioner}</div>
            </div>
            <span className={`badge ${badgeClass(a.status)}`}>{a.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function badgeClass(status) {
  if (status === 'Confirmed') return 'badge-success';
  if (status === 'Open') return 'badge-info';
  if (status === 'No Show') return 'badge-danger';
  return 'badge-neutral';
}

function WeekVolumeCard({ week }) {
  const total = week.reduce((sum, d) => sum + (d.visits || 0), 0);
  const max = Math.max(1, ...week.map(d => d.visits || 0));
  return (
    <div className="card card-pad">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
        <h3 style={{ fontSize: 13.5, fontWeight: 600, margin: 0 }}>This week's volume</h3>
        <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{total} visits</span>
      </div>
      <svg viewBox="0 0 280 100" style={{ width: '100%', height: 100 }} data-testid="week-volume">
        {week.map((d, i) => {
          const h = ((d.visits || 0) / max) * 70;
          const x = 20 + i * 36;
          return (
            <g key={d.day}>
              <rect x={x} y={80 - h} width="22" height={h} fill="var(--accent)" rx="3" opacity={d.visits ? 1 : 0.3} />
              <text x={x + 11} y="94" textAnchor="middle" fontSize="9" fill="var(--text-dim)" fontFamily="var(--font-mono)">{d.day}</text>
              <text x={x + 11} y={76 - h} textAnchor="middle" fontSize="9" fill="var(--text-muted)" fontFamily="var(--font-mono)">{d.visits || ''}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

window.MDashboardScreen = MDashboardScreen;
