// Help & Support screen — lets practice members raise and track support issues
// against the platform. Backed by the ERPNext Issue doctype scoped to the
// active Practice via medic_plus.api.support.

const _HELP_STATUS_COLORS = {
  Open:     { bg: '#ecfdf5', text: '#059669', border: '#6ee7b7' },
  Replied:  { bg: '#eff6ff', text: '#2563eb', border: '#93c5fd' },
  'On Hold':{ bg: '#fffbeb', text: '#d97706', border: '#fcd34d' },
  Resolved: { bg: '#f5f3ff', text: '#7c3aed', border: '#c4b5fd' },
  Closed:   { bg: '#f9fafb', text: '#6b7280', border: '#d1d5db' },
};

function _helpStatusStyle(status) {
  const c = _HELP_STATUS_COLORS[status] || _HELP_STATUS_COLORS.Closed;
  return {
    background: c.bg, color: c.text,
    border: `1px solid ${c.border}`,
    borderRadius: 12, padding: '2px 9px',
    fontSize: 11.5, fontWeight: 600, whiteSpace: 'nowrap', display: 'inline-block',
  };
}

function _helpFmtDate(val) {
  if (!val) return '';
  const d = new Date(val);
  return d.toLocaleDateString('en-ZA', { day: '2-digit', month: 'short', year: 'numeric' });
}

function _helpFmtDateTime(val) {
  if (!val) return '';
  const d = new Date(val);
  return d.toLocaleString('en-ZA', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ─── Skeletons ────────────────────────────────────────────────────────────────

function HelpSkel({ w = '100%', h = 13 }) {
  return (
    <div style={{ width: w, height: h, background: 'var(--bg-subtle)', borderRadius: 4, animation: 'pulse 1.6s infinite' }} />
  );
}

function HelpListSkeleton() {
  return (
    <div style={{ padding: '0 0' }}>
      {[0,1,2,3,4].map(i => (
        <div key={i} style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <HelpSkel w="70%" h={14} />
          <div style={{ display: 'flex', gap: 8 }}>
            <HelpSkel w={56} h={11} />
            <HelpSkel w={80} h={11} />
          </div>
        </div>
      ))}
    </div>
  );
}

function HelpDetailSkeleton() {
  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <HelpSkel w="60%" h={18} />
      <HelpSkel w="40%" h={12} />
      <div style={{ height: 12 }} />
      <HelpSkel w="100%" h={12} />
      <HelpSkel w="90%" h={12} />
      <HelpSkel w="75%" h={12} />
    </div>
  );
}

// ─── New Issue Modal ───────────────────────────────────────────────────────────

function NewIssueModal({ onClose, onCreated }) {
  const [subject, setSubject] = mUseState('');
  const [description, setDescription] = mUseState('');
  const [submitting, setSubmitting] = mUseState(false);
  const [error, setError] = mUseState('');

  const submit = () => {
    if (!subject.trim() || !description.trim()) {
      setError('Subject and description are required.');
      return;
    }
    setError('');
    setSubmitting(true);
    window.meridianApi
      .call('medic_plus.api.support.create_issue', { subject, description })
      .then(() => { onCreated(); onClose(); })
      .catch((e) => { setError(e.message || 'Failed to submit. Please try again.'); setSubmitting(false); });
  };

  // Close on Escape
  mUseEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ width: '100%', maxWidth: 520, background: 'var(--bg)', borderRadius: 14, boxShadow: '0 20px 60px rgba(0,0,0,0.18)', overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em' }}>New Support Issue</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', display: 'grid', placeItems: 'center', borderRadius: 6, padding: 4 }}>
            <window.MIcons.X size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 6 }}>Subject <span style={{ color: 'var(--danger, #ef4444)' }}>*</span></label>
            <input
              type="text"
              value={subject}
              onChange={e => setSubject(e.target.value)}
              placeholder="Brief description of the issue"
              style={{ width: '100%', boxSizing: 'border-box', padding: '8px 12px', fontSize: 13.5, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg)', color: 'var(--text)', outline: 'none' }}
              onFocus={e => e.target.style.borderColor = 'var(--accent)'}
              onBlur={e => e.target.style.borderColor = 'var(--border)'}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 6 }}>Description <span style={{ color: 'var(--danger, #ef4444)' }}>*</span></label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Please describe the issue in detail — steps to reproduce, what you expected, and what actually happened."
              rows={6}
              style={{ width: '100%', boxSizing: 'border-box', padding: '8px 12px', fontSize: 13.5, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg)', color: 'var(--text)', outline: 'none', resize: 'vertical', fontFamily: 'inherit' }}
              onFocus={e => e.target.style.borderColor = 'var(--accent)'}
              onBlur={e => e.target.style.borderColor = 'var(--border)'}
            />
          </div>
          {error && (
            <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '8px 12px', fontSize: 12.5, color: '#dc2626' }}>{error}</div>
          )}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '12px 20px', borderTop: '1px solid var(--border)' }}>
          <button onClick={onClose} className="btn btn-secondary btn-sm" disabled={submitting}>Cancel</button>
          <button onClick={submit} className="btn btn-primary btn-sm" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit Issue'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Issue Detail Panel ────────────────────────────────────────────────────────

function IssueDetail({ issue, onBack, onStatusChanged }) {
  const [detail, setDetail] = mUseState(null);
  const [status, setStatus] = mUseState(issue.status);
  const [loading, setLoading] = mUseState(true);
  const [actioning, setActioning] = mUseState(false);

  mUseEffect(() => {
    let cancelled = false;
    setLoading(true);
    setDetail(null);
    window.meridianApi
      .call('medic_plus.api.support.get_issue_detail', { issue_name: issue.name })
      .then((d) => { if (!cancelled) { setDetail(d); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [issue.name]);

  const changeStatus = (newStatus) => {
    setActioning(true);
    window.meridianApi
      .call('medic_plus.api.support.update_issue_status', { issue_name: issue.name, status: newStatus })
      .then(() => { setStatus(newStatus); onStatusChanged(issue.name, newStatus); setActioning(false); })
      .catch((e) => { window.meridianApi.showError(e.message || 'Could not update status.'); setActioning(false); });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Detail header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {onBack && (
          <button onClick={onBack} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', display: 'grid', placeItems: 'center', borderRadius: 6, padding: 4 }}>
            <window.MIcons.Menu size={16} />
          </button>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, letterSpacing: '-0.01em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{issue.subject}</div>
          <div style={{ fontSize: 11.5, color: 'var(--text-dim)', marginTop: 1 }}>{issue.name} · {_helpFmtDate(issue.creation)}</div>
        </div>
        <span style={_helpStatusStyle(status)}>{status}</span>
        {status !== 'Closed' ? (
          <button
            className="btn btn-secondary btn-sm"
            disabled={actioning}
            onClick={() => changeStatus('Closed')}
            style={{ whiteSpace: 'nowrap' }}
          >{actioning ? '…' : 'Close'}</button>
        ) : (
          <button
            className="btn btn-secondary btn-sm"
            disabled={actioning}
            onClick={() => changeStatus('Open')}
            style={{ whiteSpace: 'nowrap' }}
          >{actioning ? '…' : 'Reopen'}</button>
        )}
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {loading && <HelpDetailSkeleton />}

        {!loading && detail && (
          <>
            {/* Original description */}
            <div style={{ background: 'var(--bg-subtle)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-dim)', marginBottom: 8 }}>Description</div>
              <div
                style={{ fontSize: 13.5, color: 'var(--text)', lineHeight: 1.6 }}
                dangerouslySetInnerHTML={{ __html: detail.issue.description || '<em style="color:var(--text-dim)">No description provided.</em>' }}
              />
            </div>

            {/* Thread */}
            {detail.thread && detail.thread.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-dim)' }}>Replies</div>
                {detail.thread.map((msg, i) => {
                  const isInbound = msg.sent_or_received === 'Received';
                  return (
                    <div key={i} style={{ borderRadius: 10, padding: '12px 14px', border: '1px solid var(--border)', background: isInbound ? 'var(--accent-soft, #eff6ff)' : 'var(--bg-subtle)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 12.5, fontWeight: 500 }}>{msg.sender_full_name || msg.sender}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{_helpFmtDateTime(msg.creation)}</span>
                      </div>
                      <div
                        style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.55 }}
                        dangerouslySetInnerHTML={{ __html: msg.content || '' }}
                      />
                    </div>
                  );
                })}
              </div>
            )}

            {(!detail.thread || detail.thread.length === 0) && (
              <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-dim)', fontSize: 13 }}>
                No replies yet. Our support team will respond shortly.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ─── Main Screen ───────────────────────────────────────────────────────────────

const HELP_STATUS_TABS = ['All', 'Open', 'Replied', 'On Hold', 'Resolved', 'Closed'];

function MHelpScreen() {
  const [issues, setIssues] = mUseState([]);
  const [listStatus, setListStatus] = mUseState('loading');  // 'loading' | 'ready' | 'error'
  const [activeTab, setActiveTab] = mUseState('All');
  const [selected, setSelected] = mUseState(null);
  const [showNew, setShowNew] = mUseState(false);
  const [mobileView, setMobileView] = mUseState('list');  // 'list' | 'detail'

  const loadIssues = () => {
    setListStatus('loading');
    window.meridianApi
      .call('medic_plus.api.support.get_issues')
      .then((data) => { setIssues(data || []); setListStatus('ready'); })
      .catch((e) => { setListStatus('error'); window.meridianApi.showError(e.message || 'Could not load issues.'); });
  };

  mUseEffect(() => { loadIssues(); }, []);

  const filtered = activeTab === 'All' ? issues : issues.filter(i => i.status === activeTab);

  const handleSelect = (issue) => {
    setSelected(issue);
    setMobileView('detail');
  };

  const handleBack = () => {
    setSelected(null);
    setMobileView('list');
  };

  const handleStatusChanged = (issueName, newStatus) => {
    setIssues(prev => prev.map(i => i.name === issueName ? { ...i, status: newStatus } : i));
    setSelected(prev => prev && prev.name === issueName ? { ...prev, status: newStatus } : prev);
  };

  const handleCreated = () => { loadIssues(); };

  return (
    <div className="page fade-in" style={{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Page title bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 20px 12px', flexShrink: 0 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em', margin: 0 }}>Help &amp; Support</h1>
        <button className="btn btn-primary btn-sm" onClick={() => setShowNew(true)} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <window.MIcons.Plus size={14} /> New Issue
        </button>
      </div>

      {/* Two-column layout */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', borderTop: '1px solid var(--border)' }}>

        {/* ── List column ── */}
        <div style={{
          display: (mobileView === 'list' || window.innerWidth >= 768) ? 'flex' : 'none',
          flexDirection: 'column',
          width: selected ? '340px' : '100%',
          minWidth: selected ? '280px' : undefined,
          borderRight: selected ? '1px solid var(--border)' : 'none',
          overflow: 'hidden',
          flexShrink: 0,
        }}>
          {/* Status filter tabs */}
          <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', padding: '0 12px', overflowX: 'auto', flexShrink: 0 }}>
            {HELP_STATUS_TABS.map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '10px 10px',
                  fontSize: 12.5, fontWeight: activeTab === tab ? 600 : 400,
                  color: activeTab === tab ? 'var(--accent-text, #2563eb)' : 'var(--text-muted)',
                  borderBottom: activeTab === tab ? '2px solid var(--accent, #2563eb)' : '2px solid transparent',
                  whiteSpace: 'nowrap', transition: 'color 0.15s',
                }}
              >{tab}</button>
            ))}
          </div>

          {/* Issue rows */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {listStatus === 'loading' && <HelpListSkeleton />}
            {listStatus === 'ready' && filtered.length === 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 180, color: 'var(--text-dim)', gap: 10 }}>
                <window.MIcons.LifeBuoy size={32} />
                <span style={{ fontSize: 13 }}>No issues found</span>
              </div>
            )}
            {listStatus === 'ready' && filtered.map(issue => (
              <div
                key={issue.name}
                onClick={() => handleSelect(issue)}
                style={{
                  padding: '13px 16px', borderBottom: '1px solid var(--border)',
                  cursor: 'pointer', transition: 'background 0.1s',
                  background: selected?.name === issue.name ? 'var(--accent-soft, #eff6ff)' : 'transparent',
                }}
                onMouseEnter={e => { if (selected?.name !== issue.name) e.currentTarget.style.background = 'var(--bg-hover, var(--bg-subtle))'; }}
                onMouseLeave={e => { if (selected?.name !== issue.name) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 5 }}>
                  <span style={{ flex: 1, fontSize: 13.5, fontWeight: 500, lineHeight: 1.35, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                    {issue.subject}
                  </span>
                  <span style={_helpStatusStyle(issue.status)}>{issue.status}</span>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{_helpFmtDate(issue.creation)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Detail column ── */}
        {selected ? (
          <div style={{ flex: 1, overflow: 'hidden', display: (mobileView === 'detail' || window.innerWidth >= 768) ? 'block' : 'none' }}>
            <IssueDetail
              issue={selected}
              onBack={handleBack}
              onStatusChanged={handleStatusChanged}
            />
          </div>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)', flexDirection: 'column', gap: 10 }}>
            <window.MIcons.LifeBuoy size={38} />
            <span style={{ fontSize: 13 }}>Select an issue to view details</span>
          </div>
        )}
      </div>

      {showNew && <NewIssueModal onClose={() => setShowNew(false)} onCreated={handleCreated} />}
    </div>
  );
}

window.MHelpScreen = MHelpScreen;
