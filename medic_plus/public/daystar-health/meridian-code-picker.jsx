// Reusable Code System picker — generalises MIcd10Picker. Debounced
// (250ms) search against any whitelisted search endpoint. Renders a list
// of { code, display } rows; selection fires onChange({ code, display }).
//
// Usage:
//   <window.MCodePicker
//     endpoint="medic_plus.api.daystar_health.search_nappi"
//     placeholder="Search NAPPI…"
//     emptyText="No matching NAPPI codes."
//     testid="nappi-picker"
//     value={code}
//     onChange={({ code, display }) => setForm(...)}
//   />
//
// MIcd10Picker / MNappiPicker / MLoincPicker are thin wrappers below.

function MCodePicker({
  endpoint,
  value,
  onChange,
  placeholder = 'Search…',
  emptyText = 'No matching codes.',
  testid = 'code-picker',
  autoFocus = false,
}) {
  const [query, setQuery] = React.useState(value || '');
  const [debQuery, setDebQuery] = React.useState(value || '');
  const [results, setResults] = React.useState([]);
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const wrapRef = React.useRef(null);

  React.useEffect(() => { setQuery(value || ''); }, [value]);

  React.useEffect(() => {
    const t = setTimeout(() => setDebQuery(query), 250);
    return () => clearTimeout(t);
  }, [query]);

  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    window.meridianApi.call(endpoint, { query: debQuery, limit: 25 })
      .then((rows) => { if (!cancelled) { setResults(rows || []); setLoading(false); } })
      .catch(() => { if (!cancelled) { setResults([]); setLoading(false); } });
    return () => { cancelled = true; };
  }, [debQuery, open, endpoint]);

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
    <div ref={wrapRef} style={{ position: 'relative' }} data-testid={testid}>
      <input
        type="text"
        className="input"
        value={query}
        placeholder={placeholder}
        autoFocus={autoFocus}
        onFocus={() => setOpen(true)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        data-testid={`${testid}-input`}
      />
      {open && (
        <div
          data-testid={`${testid}-results`}
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
            <div style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)' }}>{emptyText}</div>
          )}
          {!loading && results.map((r) => (
            <button
              key={r.name}
              data-testid={`${testid}-row`}
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
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, minWidth: 80 }}>{r.code}</span>
              <span style={{ color: 'var(--text-muted)' }}>{r.display}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function MNappiPicker(props) {
  return (
    <MCodePicker
      endpoint="medic_plus.api.daystar_health.search_nappi"
      placeholder={props.placeholder || 'Search NAPPI…'}
      emptyText="No matching NAPPI codes."
      testid="nappi-picker"
      {...props}
    />
  );
}

function MLoincPicker(props) {
  return (
    <MCodePicker
      endpoint="medic_plus.api.daystar_health.search_loinc"
      placeholder={props.placeholder || 'Search LOINC…'}
      emptyText="No matching LOINC codes."
      testid="loinc-picker"
      {...props}
    />
  );
}

window.MCodePicker = MCodePicker;
window.MNappiPicker = MNappiPicker;
window.MLoincPicker = MLoincPicker;
