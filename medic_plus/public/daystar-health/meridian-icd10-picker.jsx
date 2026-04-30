// Reusable ICD-10 picker. Debounced (250ms) search against
// medic_plus.api.daystar_health.search_icd10. Renders a list of
// { code, display } rows; selection fires onChange({ code, display }).
//
// Usage:
//   <window.MIcd10Picker
//     value={code}
//     onChange={({ code, display }) => setForm(...)}
//     placeholder="Search ICD-10…"
//   />

function MIcd10Picker({ value, onChange, placeholder = 'Search ICD-10…', autoFocus = false }) {
  const [query, setQuery] = React.useState(value || '');
  const [debQuery, setDebQuery] = React.useState(value || '');
  const [results, setResults] = React.useState([]);
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const wrapRef = React.useRef(null);

  React.useEffect(() => { setQuery(value || ''); }, [value]);

  // 250ms debounce on query.
  React.useEffect(() => {
    const t = setTimeout(() => setDebQuery(query), 250);
    return () => clearTimeout(t);
  }, [query]);

  // Fetch on debounced query change while open.
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    window.meridianApi.call('medic_plus.api.daystar_health.search_icd10', { query: debQuery, limit: 25 })
      .then((rows) => { if (!cancelled) { setResults(rows || []); setLoading(false); } })
      .catch(() => { if (!cancelled) { setResults([]); setLoading(false); } });
    return () => { cancelled = true; };
  }, [debQuery, open]);

  // Click-outside closes the dropdown.
  React.useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const select = (row) => {
    setQuery(row.code);
    setOpen(false);
    if (onChange) onChange({ code: row.code, display: row.display });
  };

  return (
    <div ref={wrapRef} style={{ position: 'relative' }} data-testid="icd10-picker">
      <input
        type="text"
        className="input"
        value={query}
        placeholder={placeholder}
        autoFocus={autoFocus}
        onFocus={() => setOpen(true)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        data-testid="icd10-picker-input"
      />
      {open && (
        <div
          data-testid="icd10-picker-results"
          style={{
            position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 40,
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 8, marginTop: 4, maxHeight: 240, overflowY: 'auto',
            boxShadow: 'var(--shadow-md, 0 4px 12px rgba(15,23,42,0.08))',
          }}
        >
          {loading && (
            <div style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)' }}>Searching…</div>
          )}
          {!loading && results.length === 0 && (
            <div style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)' }}>No matching ICD-10 codes.</div>
          )}
          {!loading && results.map((r) => (
            <button
              key={r.name}
              data-testid="icd10-picker-row"
              type="button"
              onClick={() => select(r)}
              style={{
                width: '100%', textAlign: 'left', display: 'flex', gap: 12,
                padding: '8px 12px', background: 'transparent', border: 'none',
                cursor: 'pointer', fontSize: 12,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-subtle)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
            >
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, minWidth: 70 }}>{r.code}</span>
              <span style={{ color: 'var(--text-muted)' }}>{r.display}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

window.MIcd10Picker = MIcd10Picker;
