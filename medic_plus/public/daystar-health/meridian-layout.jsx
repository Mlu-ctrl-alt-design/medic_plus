// Meridian shared layout
const { useState: mUseState, useMemo: mUseMemo, useEffect: mUseEffect } = React;

function MSidebar({ route, go }) {
  const items = [
    { key: 'dashboard', icon: 'Home', label: 'Today' },
    { key: 'appointments', icon: 'Calendar', label: 'Appointments' },
    { key: 'patients', icon: 'Users', label: 'Patients' },
    { key: 'records', icon: 'ClipBoard', label: 'Medical Records' },
    { key: 'labs', icon: 'Beaker', label: 'Labs & Imaging' },
    { key: 'medications', icon: 'Pill', label: 'Prescriptions' },
    { key: 'billing', icon: 'Tag', label: 'Billing & Claims' },
    { key: 'practice', icon: 'Building', label: 'Practice' },
  ];
  const Logo = window.MIcons.Logo;
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <Logo size={22} />
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
          <span style={{ fontSize: 14, fontWeight: 600, letterSpacing: '-0.01em' }}>Daystar</span>
          <span style={{ fontSize: 10.5, color: 'var(--text-dim)', letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 500 }}>Health</span>
        </div>
        <div style={{ marginLeft: 'auto', width: 22, height: 22, display: 'grid', placeItems: 'center', borderRadius: 6, color: 'var(--text-dim)' }}>
          <window.MIcons.ChevronLeft size={14} />
        </div>
      </div>

      <div className="sidebar-nav">
        <div className="sidebar-section">Today</div>
        {items.slice(0, 2).map(it => {
          const Ic = window.MIcons[it.icon];
          return (
            <button key={it.key} data-testid={`nav-${it.key}`} className={`nav-item ${route === it.key ? 'active' : ''}`} onClick={() => go(it.key)}>
              <Ic size={17} /><span>{it.label}</span>
              {it.count && <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--font-mono)', background: 'var(--accent-soft)', padding: '1px 6px', borderRadius: 4, color: 'var(--accent-text)', fontWeight: 500 }}>{it.count}</span>}
            </button>
          );
        })}
        <div className="sidebar-section">Care</div>
        {items.slice(2, 6).map(it => {
          const Ic = window.MIcons[it.icon];
          return (
            <button key={it.key} data-testid={`nav-${it.key}`} className={`nav-item ${route === it.key ? 'active' : ''}`} onClick={() => go(it.key)}>
              <Ic size={17} /><span>{it.label}</span>
            </button>
          );
        })}
        <div className="sidebar-section">Practice</div>
        {items.slice(6).map(it => {
          const Ic = window.MIcons[it.icon];
          return (
            <button key={it.key} data-testid={`nav-${it.key}`} className={`nav-item ${route === it.key ? 'active' : ''}`} onClick={() => go(it.key)}>
              <Ic size={17} /><span>{it.label}</span>
            </button>
          );
        })}
      </div>

      <div style={{ padding: 12, borderTop: '1px solid var(--border)' }}>
        <button data-testid="nav-profile" className="nav-item" onClick={() => go('profile')}>
          <window.MIcons.Settings size={17} /><span>Account</span>
        </button>
        <button data-testid="nav-signout" className="nav-item" onClick={() => window.meridianApi.logout()}>
          <window.MIcons.Logout size={17} /><span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}

function MTopbar({ go, crumbs = [] }) {
  const api = window.meridianApi || {};
  const [profile, setProfile] = React.useState(api._profile || null);

  React.useEffect(() => {
    if (api._profile || !api.isAuthenticated || !api.hasPractice) return;
    api.call('medic_plus.api.daystar_health.get_my_practitioner_profile')
      .then((p) => { api._profile = p; setProfile(p); })
      .catch(() => {});
  }, []);

  const user = profile?.user || {};
  const practitioner = profile?.practitioner || {};
  const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
  const displayName = fullName ? `Dr. ${fullName}` : (user.email || api.sessionUser || 'User');
  const initialsSource = (user.first_name?.[0] || '') + (user.last_name?.[0] || '');
  const initials = (initialsSource || (user.email?.[0] || '?')).toUpperCase();
  const subtitle = practitioner.department || (practitioner.name ? 'Practitioner' : '');

  return (
    <div className="topbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-muted)' }}>
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            <button onClick={c.go} style={{ background: 'none', border: 'none', color: i === crumbs.length - 1 ? 'var(--text)' : 'var(--text-muted)', fontWeight: i === crumbs.length - 1 ? 500 : 400, fontSize: 13 }}>{c.label}</button>
            {i < crumbs.length - 1 && <window.MIcons.ChevronRight size={12} />}
          </React.Fragment>
        ))}
      </div>
      <div className="search" style={{ marginLeft: 24, width: 380 }}>
        <window.MIcons.Search size={15} />
        <input placeholder="Search patients, MRN, appointments…" />
        <kbd>⌘K</kbd>
      </div>
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
        <button className="btn btn-secondary btn-sm"><window.MIcons.Plus size={14} /> New visit</button>
        <button className="btn btn-ghost btn-sm" style={{ width: 36, padding: 0 }}>
          <window.MIcons.Bell size={17} />
        </button>
        <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 6px' }} />
        <button data-testid="topbar-profile" onClick={() => go('profile')} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'transparent', border: 'none', padding: '4px 8px 4px 4px', borderRadius: 8, cursor: 'pointer' }}>
          {user.user_image ? (
            <img src={user.user_image} alt="" className="avatar avatar-sm" style={{ width: 28, height: 28, borderRadius: '50%', objectFit: 'cover' }} />
          ) : (
            <div className="avatar avatar-sm" style={{ width: 28, height: 28, fontSize: 11 }}>{initials}</div>
          )}
          <div style={{ textAlign: 'left', lineHeight: 1.15 }}>
            <div data-testid="topbar-profile-name" style={{ fontSize: 12.5, fontWeight: 500 }}>{displayName}</div>
            {subtitle && <div data-testid="topbar-profile-subtitle" style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>{subtitle}</div>}
          </div>
          <window.MIcons.ChevronDown size={13} />
        </button>
      </div>
    </div>
  );
}

window.MSidebar = MSidebar;
window.MTopbar = MTopbar;
