// Meridian auth screens — wired to Frappe via window.meridianApi.
function MLoginScreen({ go }) {
  const [email, setEmail] = mUseState('');
  const [pw, setPw] = mUseState('');
  const [show, setShow] = mUseState(false);
  const [loading, setLoading] = mUseState(false);
  const [error, setError] = mUseState(null);
  const Logo = window.MIcons.Logo;

  const submit = async (e) => {
    e.preventDefault();
    if (!email || !pw) {
      setError('Enter your email and password.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await window.meridianApi.login(email, pw);
      // After login, reload so daystar-health.py re-evaluates session and
      // has_practice. The page entry decides where to route from there.
      window.location.href = '/daystar-health';
    } catch (err) {
      setError(err.message || 'Sign-in failed. Check your credentials and try again.');
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card fade-in">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 }}>
          <Logo size={28} />
          <div style={{ lineHeight: 1.1 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>Daystar</div>
            <div style={{ fontSize: 10.5, color: 'var(--text-dim)', letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 500 }}>Health</div>
          </div>
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 6px', letterSpacing: '-0.02em' }}>Sign in to your practice</h1>
        <p style={{ fontSize: 13.5, color: 'var(--text-muted)', margin: '0 0 24px' }}>Secure access to your patients, schedule, and records.</p>

        <form onSubmit={submit}>
          <div className="field">
            <label className="label">Provider email</label>
            <div style={{ position: 'relative' }}>
              <window.MIcons.Mail size={15} style={{ position: 'absolute', left: 12, top: 12, color: 'var(--text-dim)' }} />
              <input
                className="input"
                style={{ paddingLeft: 36 }}
                value={email}
                onChange={e => setEmail(e.target.value)}
                type="text"
                autoComplete="username"
                required
                data-testid="login-email"
              />
            </div>
          </div>
          <div className="field">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <label className="label">Password</label>
              <button type="button" onClick={() => go('recover')} style={{ background: 'none', border: 'none', color: 'var(--accent-text)', fontSize: 12, fontWeight: 500 }}>Forgot?</button>
            </div>
            <div style={{ position: 'relative' }}>
              <window.MIcons.Lock size={15} style={{ position: 'absolute', left: 12, top: 12, color: 'var(--text-dim)' }} />
              <input
                className="input"
                style={{ paddingLeft: 36, paddingRight: 36 }}
                value={pw}
                onChange={e => setPw(e.target.value)}
                type={show ? 'text' : 'password'}
                autoComplete="current-password"
                required
                data-testid="login-password"
              />
              <button
                type="button"
                onClick={() => setShow(!show)}
                aria-label={show ? 'Hide password' : 'Show password'}
                style={{
                  position: 'absolute',
                  right: 6,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 28,
                  height: 28,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: 6,
                  color: 'var(--text-dim)',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {show ? <window.MIcons.EyeOff size={15} /> : <window.MIcons.Eye size={15} />}
              </button>
            </div>
          </div>
          {error && (
            <div
              role="alert"
              data-testid="login-error"
              style={{ padding: '10px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 8, fontSize: 12.5, color: 'var(--danger)', margin: '4px 0 14px' }}
            >
              {error}
            </div>
          )}
          <div style={{ padding: '10px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11.5, color: 'var(--text-muted)', display: 'flex', gap: 8, alignItems: 'flex-start', margin: '4px 0 18px' }}>
            <window.MIcons.Lock size={13} style={{ marginTop: 1, flexShrink: 0 }} />
            <span>Protected health information. Sign-ins are logged for audit. By continuing you agree to the access policy.</span>
          </div>
          <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={loading} data-testid="login-submit">
            {loading ? 'Signing in…' : 'Sign in'} {!loading && <window.MIcons.ArrowRight size={15} />}
          </button>
        </form>
      </div>
    </div>
  );
}

function MRecoverScreen({ go }) {
  const [step, setStep] = mUseState(1);
  const [email, setEmail] = mUseState('');
  const [loading, setLoading] = mUseState(false);
  const [error, setError] = mUseState(null);
  const Logo = window.MIcons.Logo;

  const submit = async (e) => {
    e.preventDefault();
    if (!email) {
      setError('Enter your email.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await window.meridianApi.recoverPassword(email);
      setStep(2);
    } catch (err) {
      // Frappe returns a localised "User not found" or similar; surface it.
      setError(err.message || "We couldn't send a reset link. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card fade-in">
        <button onClick={() => go('login')} className="btn btn-ghost btn-sm" style={{ marginLeft: -8, marginBottom: 16 }}>
          <window.MIcons.ArrowLeft size={14} /> Back to sign in
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
          <Logo size={26} />
          <div style={{ fontSize: 14, fontWeight: 600 }}>Daystar Health</div>
        </div>
        {step === 1 ? (
          <>
            <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 6px', letterSpacing: '-0.02em' }}>Reset your password</h1>
            <p style={{ fontSize: 13.5, color: 'var(--text-muted)', margin: '0 0 24px' }}>Enter your provider email and we'll send a secure recovery link.</p>
            <form onSubmit={submit}>
              <div className="field">
                <label className="label">Provider email</label>
                <input
                  className="input"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  data-testid="recover-email"
                />
              </div>
              {error && (
                <div role="alert" data-testid="recover-error" style={{ padding: '10px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 8, fontSize: 12.5, color: 'var(--danger)', margin: '4px 0 14px' }}>
                  {error}
                </div>
              )}
              <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={loading} data-testid="recover-submit">
                {loading ? 'Sending…' : 'Send recovery link'} {!loading && <window.MIcons.ArrowRight size={15} />}
              </button>
              <p style={{ fontSize: 11.5, color: 'var(--text-dim)', marginTop: 14, textAlign: 'center' }}>
                For security, your account locks after repeated failed attempts. Contact your practice admin if you've been locked out.
              </p>
            </form>
          </>
        ) : (
          <>
            <div style={{ width: 56, height: 56, borderRadius: 14, background: 'var(--accent-soft)', display: 'grid', placeItems: 'center', marginBottom: 18 }}>
              <window.MIcons.Mail size={26} stroke="var(--accent)" />
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 6px', letterSpacing: '-0.02em' }}>Check your inbox</h1>
            <p style={{ fontSize: 13.5, color: 'var(--text-muted)', margin: '0 0 8px' }}>Recovery link sent to:</p>
            <p data-testid="recover-success-email" style={{ fontFamily: 'var(--font-mono)', fontSize: 13, padding: '10px 14px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 8, margin: '0 0 20px' }}>{email}</p>
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '0 0 20px' }}>Link expires shortly. Didn't get it? Check spam or resend.</p>
            <button className="btn btn-secondary btn-block" onClick={() => setStep(1)}>Try a different email</button>
          </>
        )}
      </div>
    </div>
  );
}

function MNoPracticeScreen() {
  const Logo = window.MIcons.Logo;
  return (
    <div className="auth-shell">
      <div className="auth-card fade-in" data-testid="no-practice-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
          <Logo size={26} />
          <div style={{ fontSize: 14, fontWeight: 600 }}>Daystar Health</div>
        </div>
        <div style={{ width: 56, height: 56, borderRadius: 14, background: 'var(--warn-soft)', display: 'grid', placeItems: 'center', marginBottom: 18 }}>
          <window.MIcons.AlertTriangle size={26} stroke="var(--warn)" />
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 6px', letterSpacing: '-0.02em' }}>Practice not linked</h1>
        <p style={{ fontSize: 13.5, color: 'var(--text-muted)', margin: '0 0 18px' }}>Your account isn't linked to a practice. Contact your administrator to be added as a Practice Member.</p>
        <button
          className="btn btn-secondary btn-block"
          onClick={() => window.meridianApi.logout()}
          data-testid="no-practice-signout"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

window.MLoginScreen = MLoginScreen;
window.MRecoverScreen = MRecoverScreen;
window.MNoPracticeScreen = MNoPracticeScreen;
