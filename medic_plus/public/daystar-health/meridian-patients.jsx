// Patients listing
function MPatientsScreen({ go }) {
  const all = window.MH_DATA.PATIENTS;
  const [query, setQuery] = mUseState('');
  const [risk, setRisk] = mUseState('All');
  const [status, setStatus] = mUseState('All');
  const [provider, setProvider] = mUseState('All');
  const [sort, setSort] = mUseState({ key: 'name', dir: 'asc' });
  const [selected, setSelected] = mUseState(new Set());

  const providers = ['All', ...Array.from(new Set(all.map(p => p.primary)))];

  const filtered = mUseMemo(() => {
    let r = all.filter(p => (
      (!query || p.name.toLowerCase().includes(query.toLowerCase()) || p.mrn.includes(query) || p.id.toLowerCase().includes(query.toLowerCase())) &&
      (risk === 'All' || p.risk === risk) &&
      (status === 'All' || p.status === status) &&
      (provider === 'All' || p.primary === provider)
    ));
    r.sort((a, b) => {
      const av = a[sort.key], bv = b[sort.key];
      if (typeof av === 'string') return sort.dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      return sort.dir === 'asc' ? av - bv : bv - av;
    });
    return r;
  }, [all, query, risk, status, provider, sort]);

  const toggleSort = (k) => setSort(s => s.key === k ? { key: k, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key: k, dir: 'asc' });
  const SortHead = ({ k, children, align }) => (
    <th onClick={() => toggleSort(k)} style={{ cursor: 'pointer', textAlign: align || 'left' }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        {children}
        {sort.key === k && (sort.dir === 'asc' ? <window.MIcons.Up size={11} /> : <window.MIcons.Down size={11} />)}
      </span>
    </th>
  );

  const toggleSel = (id) => {
    const s = new Set(selected);
    if (s.has(id)) s.delete(id); else s.add(id);
    setSelected(s);
  };

  return (
    <div className="page fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.02em' }}>Patients</h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>{filtered.length} of {all.length} patients · 1,284 active in practice</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm"><window.MIcons.Download size={14} /> Export</button>
          <button className="btn btn-primary btn-sm"><window.MIcons.Plus size={14} /> Register patient</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 'var(--gap)' }}>
        <div style={{ padding: 14, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="search" style={{ flex: 1, minWidth: 240 }}>
            <window.MIcons.Search size={15} />
            <input placeholder="Search by name, MRN, or ID…" value={query} onChange={e => setQuery(e.target.value)} />
          </div>
          <select className="select" style={{ width: 'auto', minWidth: 130 }} value={provider} onChange={e => setProvider(e.target.value)}>
            {providers.map(p => <option key={p}>{p === 'All' ? 'All providers' : p}</option>)}
          </select>
          <select className="select" style={{ width: 'auto', minWidth: 110 }} value={risk} onChange={e => setRisk(e.target.value)}>
            {['All', 'Low', 'Moderate', 'High'].map(r => <option key={r}>{r === 'All' ? 'All risk' : r}</option>)}
          </select>
          <select className="select" style={{ width: 'auto', minWidth: 110 }} value={status} onChange={e => setStatus(e.target.value)}>
            {['All', 'Stable', 'Watch', 'Urgent'].map(s => <option key={s}>{s === 'All' ? 'All status' : s}</option>)}
          </select>
          <button className="btn btn-secondary btn-sm"><window.MIcons.Filter size={14} /> More</button>
        </div>

        {selected.size > 0 && (
          <div style={{ padding: '10px 16px', background: 'var(--accent-soft)', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12, fontSize: 13 }}>
            <span style={{ fontWeight: 500, color: 'var(--accent-text)' }}>{selected.size} selected</span>
            <button className="btn btn-secondary btn-sm">Send message</button>
            <button className="btn btn-secondary btn-sm">Schedule</button>
            <button className="btn btn-secondary btn-sm">Add to care plan</button>
            <button onClick={() => setSelected(new Set())} className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }}>Clear</button>
          </div>
        )}

        <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <span className={`checkbox ${selected.size === filtered.length && filtered.length > 0 ? 'checked' : ''}`} onClick={() => setSelected(selected.size === filtered.length ? new Set() : new Set(filtered.map(p => p.id)))}>
                    {selected.size === filtered.length && filtered.length > 0 && <window.MIcons.Check size={11} strokeWidth={3} />}
                  </span>
                </th>
                <SortHead k="name">Patient</SortHead>
                <SortHead k="mrn">MRN</SortHead>
                <SortHead k="age" align="right">Age</SortHead>
                <th>Conditions</th>
                <th>Allergies</th>
                <SortHead k="lastSeen">Last seen</SortHead>
                <SortHead k="risk">Risk</SortHead>
                <SortHead k="status">Status</SortHead>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => (
                <tr key={p.id} onClick={() => go('patient', p.id)}>
                  <td onClick={e => e.stopPropagation()}>
                    <span className={`checkbox ${selected.has(p.id) ? 'checked' : ''}`} onClick={() => toggleSel(p.id)}>
                      {selected.has(p.id) && <window.MIcons.Check size={11} strokeWidth={3} />}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div className="avatar avatar-sm" style={{ width: 32, height: 32, fontSize: 11 }}>{p.name.split(' ').map(n => n[0]).join('')}</div>
                      <div>
                        <div style={{ fontWeight: 500 }}>{p.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{p.sex} · DOB {p.dob} · {p.primary}</div>
                      </div>
                    </div>
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{p.mrn}</td>
                  <td className="mono" style={{ textAlign: 'right' }}>{p.age}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{p.conditions.length === 0 ? <span style={{ color: 'var(--text-dim)' }}>—</span> : p.conditions.slice(0, 2).join(', ')}{p.conditions.length > 2 && <span style={{ color: 'var(--text-dim)' }}> +{p.conditions.length - 2}</span>}</td>
                  <td>{p.allergies.length === 0 ? <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>NKDA</span> : <span className="badge badge-danger">{p.allergies.length}</span>}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{p.lastSeen}</td>
                  <td><span className={`badge ${p.risk === 'High' ? 'badge-danger' : p.risk === 'Moderate' ? 'badge-warn' : 'badge-success'}`}>{p.risk}</span></td>
                  <td><span className={`badge ${p.status === 'Stable' ? 'badge-success' : p.status === 'Watch' ? 'badge-warn' : 'badge-danger'}`}>{p.status}</span></td>
                  <td onClick={e => e.stopPropagation()}>
                    <button className="btn btn-ghost btn-sm" style={{ width: 28, padding: 0 }}><window.MIcons.More size={16} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12, fontSize: 12.5, color: 'var(--text-muted)' }}>
          <span>Rows per page</span>
          <select className="select" style={{ width: 70, height: 28, fontSize: 12 }}><option>10</option><option>25</option></select>
          <span style={{ marginLeft: 'auto' }}>1 – {filtered.length} of {filtered.length}</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button className="btn btn-secondary btn-sm" style={{ width: 28, padding: 0 }}><window.MIcons.ChevronLeft size={14} /></button>
            <button className="btn btn-secondary btn-sm" style={{ width: 28, padding: 0 }}><window.MIcons.ChevronRight size={14} /></button>
          </div>
        </div>
      </div>
    </div>
  );
}

window.MPatientsScreen = MPatientsScreen;
