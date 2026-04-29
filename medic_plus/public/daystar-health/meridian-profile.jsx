// Profile (provider account)
function MProfileScreen({ go }) {
  const [tab, setTab] = mUseState('account');
  const [form, setForm] = mUseState({
    firstName: 'Sanjay', lastName: 'Patel', email: 's.patel@daystarhealth.co',
    phone: '(415) 555-0142', npi: '1234567890', specialty: 'Family Medicine',
    title: 'Attending Physician',
  });
  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div className="page fade-in">
      <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.02em' }}>Account settings</h1>
      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 20px' }}>Manage your provider profile, sign-in, and preferences.</p>

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 'var(--gap)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[
            { id: 'account', label: 'Profile', icon: 'Users' },
            { id: 'security', label: 'Sign-in & security', icon: 'Lock' },
            { id: 'notifications', label: 'Notifications', icon: 'Bell' },
          ].map(t => {
            const Ic = window.MIcons[t.icon];
            return (
              <button key={t.id} className={`nav-item ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)} style={{ marginBottom: 2 }}>
                <Ic size={15} /><span>{t.label}</span>
              </button>
            );
          })}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
          {tab === 'account' && (
            <>
              <div className="card card-pad">
                <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px' }}>Profile photo</h3>
                <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '0 0 16px' }}>Shown to your team and on patient correspondence.</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div className="avatar" style={{ width: 72, height: 72, fontSize: 24, borderRadius: 18 }}>SP</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-secondary btn-sm">Upload new</button>
                    <button className="btn btn-ghost btn-sm">Remove</button>
                  </div>
                </div>
              </div>

              <div className="card card-pad">
                <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>Provider information</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <div className="field"><label className="label">First name</label><input className="input" value={form.firstName} onChange={e => upd('firstName', e.target.value)} /></div>
                  <div className="field"><label className="label">Last name</label><input className="input" value={form.lastName} onChange={e => upd('lastName', e.target.value)} /></div>
                  <div className="field"><label className="label">Title</label><input className="input" value={form.title} onChange={e => upd('title', e.target.value)} /></div>
                  <div className="field"><label className="label">Specialty</label><input className="input" value={form.specialty} onChange={e => upd('specialty', e.target.value)} /></div>
                  <div className="field"><label className="label">Work email</label><input className="input" type="email" value={form.email} onChange={e => upd('email', e.target.value)} /></div>
                  <div className="field"><label className="label">Phone</label><input className="input" value={form.phone} onChange={e => upd('phone', e.target.value)} /></div>
                  <div className="field"><label className="label">NPI number</label><input className="input mono" value={form.npi} onChange={e => upd('npi', e.target.value)} /></div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                  <button className="btn btn-ghost btn-sm">Cancel</button>
                  <button className="btn btn-primary btn-sm">Save changes</button>
                </div>
              </div>
            </>
          )}

          {tab === 'security' && (
            <>
              <div className="card card-pad">
                <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px' }}>Password</h3>
                <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '0 0 16px' }}>Last changed 47 days ago. Practice policy requires rotation every 90 days.</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <div className="field"><label className="label">Current password</label><input className="input" type="password" defaultValue="••••••••" /></div>
                  <div />
                  <div className="field"><label className="label">New password</label><input className="input" type="password" /></div>
                  <div className="field"><label className="label">Confirm new</label><input className="input" type="password" /></div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                  <button className="btn btn-primary btn-sm">Update password</button>
                </div>
              </div>
              <div className="card card-pad">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px' }}>Two-factor authentication</h3>
                    <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: 0 }}>Required for HIPAA compliance. Currently using authenticator app.</p>
                  </div>
                  <span className="badge badge-success">Enabled</span>
                </div>
              </div>
            </>
          )}

          {tab === 'notifications' && (
            <div className="card card-pad">
              <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>Notification preferences</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {[
                  { label: 'Critical lab results', sub: 'Notify me immediately when a result is flagged critical', on: true },
                  { label: 'New patient messages', sub: 'Patient portal messages requiring a response', on: true },
                  { label: 'Refill requests', sub: 'Pharmacy and patient-initiated refill requests', on: true },
                  { label: 'Daily schedule digest', sub: 'Email summary of tomorrow\'s appointments at 6 PM', on: false },
                ].map((n, i, arr) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: 14, borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <div>
                      <div style={{ fontSize: 13.5, fontWeight: 500 }}>{n.label}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{n.sub}</div>
                    </div>
                    <div className={`switch ${n.on ? 'on' : ''}`}><div className="dot" /></div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

window.MProfileScreen = MProfileScreen;
