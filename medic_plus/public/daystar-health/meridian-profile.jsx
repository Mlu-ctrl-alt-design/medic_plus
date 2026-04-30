// Profile screen — wired to medic_plus.api.daystar_health.get_my_practitioner_profile.
// Read-only profile this iteration. Security tab handles password change via
// Frappe's standard /api/method/frappe.core.doctype.user.user.update_password.
// Notifications tab is removed from the sidebar (no schema backing).

const PROFILE_TABS = [
  { id: 'account', label: 'Profile', icon: 'Users' },
  { id: 'security', label: 'Sign-in & security', icon: 'Lock' },
];

function MProfileScreen({ go }) {
  const [tab, setTab] = mUseState('account');
  const [state, setState] = mUseState({ status: 'loading', data: null, error: null });

  mUseEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', data: null, error: null });
    window.meridianApi
      .call('medic_plus.api.daystar_health.get_my_practitioner_profile')
      .then(data => { if (!cancelled) setState({ status: 'ready', data, error: null }); })
      .catch(err => {
        if (cancelled) return;
        const msg = err.message || 'Could not load profile.';
        setState({ status: 'error', data: null, error: msg });
        window.meridianApi.showError(msg);
      });
    return () => { cancelled = true; };
  }, []);

  if (state.status === 'loading') return <ProfileSkeleton />;
  if (state.status === 'error') {
    return (
      <div className="page fade-in">
        <div className="card card-pad" data-testid="profile-error" style={{ textAlign: 'center', padding: 60 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 8px' }}>Couldn't load profile</h2>
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>{state.error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page fade-in" data-testid="profile-page">
      <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.02em' }}>Account settings</h1>
      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 20px' }}>Manage your provider profile and sign-in.</p>

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 'var(--gap)' }}>
        <div data-testid="profile-tabs" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {PROFILE_TABS.map(t => {
            const Ic = window.MIcons[t.icon];
            return (
              <button
                key={t.id}
                data-testid={`profile-tab-${t.id}`}
                className={`nav-item ${tab === t.id ? 'active' : ''}`}
                onClick={() => setTab(t.id)}
                style={{ marginBottom: 2 }}
              >
                <Ic size={15} /><span>{t.label}</span>
              </button>
            );
          })}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
          {tab === 'account' && <AccountTab data={state.data} />}
          {tab === 'security' && <SecurityTab data={state.data} />}
        </div>
      </div>
    </div>
  );
}

function AccountTab({ data }) {
  const u = data.user || {};
  const p = data.practitioner || {};
  const initials = [(u.first_name || '?')[0], (u.last_name || '')[0]].filter(Boolean).join('').toUpperCase();
  return (
    <div data-testid="profile-tab-content-account" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
      <div className="card card-pad">
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px' }}>Profile photo</h3>
        <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '0 0 16px' }}>Shown to your team and on patient correspondence.</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div className="avatar" style={{ width: 72, height: 72, fontSize: 24, borderRadius: 18 }}>{initials || '–'}</div>
        </div>
      </div>

      <div className="card card-pad">
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>Provider information</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <ReadOnlyField label="First name" value={u.first_name} testId="profile-first-name" />
          <ReadOnlyField label="Last name" value={u.last_name} testId="profile-last-name" />
          <ReadOnlyField label="Specialty / department" value={p.department} testId="profile-department" />
          <ReadOnlyField label="HPCSA number" value={p.custom_hpcsa_number} mono testId="profile-hpcsa" />
          <ReadOnlyField label="Practice number" value={p.custom_practice_number} mono testId="profile-practice-number" />
          <ReadOnlyField label="Work email" value={u.email} testId="profile-email" />
          <ReadOnlyField label="Phone" value={u.phone} testId="profile-phone" />
        </div>
        <p style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)', fontSize: 11.5, color: 'var(--text-muted)', margin: '16px 0 0' }}>
          Profile details are managed by your practice administrator. Contact them to make changes.
        </p>
      </div>
    </div>
  );
}

function ReadOnlyField({ label, value, mono, testId }) {
  return (
    <div className="field">
      <label className="label">{label}</label>
      <div
        data-testid={testId}
        className={mono ? 'mono' : ''}
        style={{
          padding: '8px 12px',
          background: 'var(--bg-subtle)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          fontSize: 13,
          minHeight: 36,
          display: 'flex',
          alignItems: 'center',
          color: value ? 'var(--text)' : 'var(--text-dim)',
        }}
      >
        {value || '—'}
      </div>
    </div>
  );
}

function SecurityTab({ data }) {
  const [oldPw, setOldPw] = mUseState('');
  const [newPw, setNewPw] = mUseState('');
  const [confirm, setConfirm] = mUseState('');
  const [submitting, setSubmitting] = mUseState(false);
  const [feedback, setFeedback] = mUseState(null);

  const submit = async (e) => {
    e.preventDefault();
    setFeedback(null);
    if (!oldPw || !newPw) {
      setFeedback({ kind: 'error', message: 'Enter your current and new password.' });
      return;
    }
    if (newPw !== confirm) {
      setFeedback({ kind: 'error', message: 'New password and confirmation do not match.' });
      return;
    }
    setSubmitting(true);
    try {
      await window.meridianApi.call('frappe.core.doctype.user.user.update_password', {
        new_password: newPw,
        old_password: oldPw,
        logout_all_sessions: 0,
      });
      setFeedback({ kind: 'success', message: 'Password updated. Use it next time you sign in.' });
      setOldPw(''); setNewPw(''); setConfirm('');
    } catch (err) {
      setFeedback({ kind: 'error', message: err.message || 'Could not update password.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="profile-tab-content-security" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
      <div className="card card-pad">
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px' }}>Password</h3>
        <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '0 0 16px' }}>Choose a new password. You'll stay signed in on this device.</p>
        <form onSubmit={submit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="field">
              <label className="label">Current password</label>
              <input data-testid="profile-current-password" className="input" type="password" value={oldPw} onChange={e => setOldPw(e.target.value)} required />
            </div>
            <div />
            <div className="field">
              <label className="label">New password</label>
              <input data-testid="profile-new-password" className="input" type="password" value={newPw} onChange={e => setNewPw(e.target.value)} required minLength={8} />
            </div>
            <div className="field">
              <label className="label">Confirm new</label>
              <input data-testid="profile-confirm-password" className="input" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required minLength={8} />
            </div>
          </div>
          {feedback && (
            <div
              role="alert"
              data-testid={`profile-password-${feedback.kind}`}
              style={{
                marginTop: 14,
                padding: '10px 12px',
                background: feedback.kind === 'success' ? 'var(--success-soft)' : 'var(--danger-soft)',
                border: `1px solid var(--${feedback.kind === 'success' ? 'success' : 'danger'})`,
                borderRadius: 8,
                fontSize: 12.5,
                color: `var(--${feedback.kind === 'success' ? 'success' : 'danger'})`,
              }}
            >
              {feedback.message}
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            <button data-testid="profile-update-password" type="submit" className="btn btn-primary btn-sm" disabled={submitting}>
              {submitting ? 'Updating…' : 'Update password'}
            </button>
          </div>
        </form>
      </div>

      <div className="card card-pad">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px' }}>Two-factor authentication</h3>
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: 0 }}>
              {data.two_factor_authentication
                ? 'Configured. Manage in the Frappe Desk under My Settings.'
                : 'Not configured. Set up via the Frappe Desk under My Settings.'}
            </p>
          </div>
          <span
            data-testid="profile-2fa-status"
            className={`badge ${data.two_factor_authentication ? 'badge-success' : 'badge-neutral'}`}
          >
            {data.two_factor_authentication ? 'Enabled' : 'Not configured'}
          </span>
        </div>
      </div>
    </div>
  );
}

function ProfileSkeleton() {
  return (
    <div className="page fade-in" data-testid="profile-skeleton">
      <div style={{ width: 220, height: 24, background: 'var(--bg-subtle)', borderRadius: 4, marginBottom: 24, animation: 'pulse 1.6s infinite' }} />
      <div className="card card-pad">
        <div style={{ width: '100%', height: 140, background: 'var(--bg-subtle)', borderRadius: 4, animation: 'pulse 1.6s infinite' }} />
      </div>
    </div>
  );
}

window.MProfileScreen = MProfileScreen;
