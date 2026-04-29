// Patients list — wired to /api/resource/Patient via meridianApi.resource.
// Server-side search, sort, pagination. PQC scopes results to the user's Practice.

const PATIENTS_FIELDS = [
  "name", "patient_name", "sex", "dob", "status", "mobile", "email", "custom_practice",
];
const PAGE_SIZE_KEY = "daystar.patients.pageSize";
const PAGE_SIZE_DEFAULT = 25;
const PAGE_SIZE_OPTIONS = [25, 50, 100];

function MPatientsScreen({ go }) {
  const [query, setQuery] = mUseState("");
  const [debouncedQuery, setDebouncedQuery] = mUseState("");
  const [sort, setSort] = mUseState({ key: "patient_name", dir: "asc" });
  const [pageSize, setPageSize] = mUseState(() => {
    const stored = window.sessionStorage.getItem(PAGE_SIZE_KEY);
    const v = parseInt(stored, 10);
    return PAGE_SIZE_OPTIONS.includes(v) ? v : PAGE_SIZE_DEFAULT;
  });
  const [page, setPage] = mUseState(0);
  const [state, setState] = mUseState({ status: "loading", rows: [], total: 0, error: null });

  // Debounce search to 300ms.
  mUseEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // Reset page when filters or page-size change so the user doesn't land on
  // an out-of-range page.
  mUseEffect(() => { setPage(0); }, [debouncedQuery, pageSize]);

  // Fetch when any input changes.
  mUseEffect(() => {
    let cancelled = false;
    setState(s => ({ ...s, status: "loading", error: null }));

    const params = {
      fields: PATIENTS_FIELDS,
      order_by: `${sort.key} ${sort.dir}`,
      limit_start: page * pageSize,
      limit_page_length: pageSize,
    };
    if (debouncedQuery) {
      const term = `%${debouncedQuery}%`;
      params.or_filters = [
        ["patient_name", "like", term],
        ["mobile", "like", term],
        ["email", "like", term],
      ];
    }

    Promise.all([
      window.meridianApi.resource("Patient", params),
      window.meridianApi.call("frappe.client.get_count", {
        doctype: "Patient",
        filters: debouncedQuery ? null : undefined,
        // get_count doesn't take or_filters directly; fall back to a separate
        // call with the same or_filters via frappe.client.get_list with
        // limit_page_length=0 if needed. For now we use a simple count call.
      }).catch(() => null),
    ]).then(([resp, _count]) => {
      if (cancelled) return;
      const rows = resp && resp.data ? resp.data : (Array.isArray(resp) ? resp : []);
      // Fall back to a worst-case total: if the page is full, more may exist.
      // We'll improve this below using a dedicated count call.
      setState({ status: "ready", rows, total: rows.length + page * pageSize, error: null });
    }).catch((err) => {
      if (cancelled) return;
      setState({ status: "error", rows: [], total: 0, error: err.message || "Could not load patients." });
      window.meridianApi.showError(err.message || "Could not load patients.");
    });

    return () => { cancelled = true; };
  }, [debouncedQuery, sort, page, pageSize]);

  // Refetch the real total count in parallel with the rows so the footer is
  // accurate. We ask Frappe for a count limited to the same filters.
  const [total, setTotal] = mUseState(null);
  mUseEffect(() => {
    let cancelled = false;
    const term = debouncedQuery ? `%${debouncedQuery}%` : null;
    const args = { doctype: "Patient" };
    if (term) {
      args.filters = JSON.stringify([
        ["Patient", "patient_name", "like", term],
      ]);
      // get_count doesn't support or_filters; instead use a list with limit=0
      // and we'll consume the response length. The simplest accurate path:
      // query a wide page and count returned rows.
    }
    // Two paths: with and without search.
    if (!term) {
      window.meridianApi.call("frappe.client.get_count", { doctype: "Patient" })
        .then(c => { if (!cancelled) setTotal(typeof c === "number" ? c : null); })
        .catch(() => { if (!cancelled) setTotal(null); });
    } else {
      // Approximate: count via or_filters by pulling the matching ids only.
      window.meridianApi.resource("Patient", {
        fields: ["name"],
        or_filters: [
          ["patient_name", "like", term],
          ["mobile", "like", term],
          ["email", "like", term],
        ],
        limit_page_length: 0,  // 0 = unlimited
      }).then(resp => {
        if (cancelled) return;
        const rows = resp && resp.data ? resp.data : (Array.isArray(resp) ? resp : []);
        setTotal(rows.length);
      }).catch(() => { if (!cancelled) setTotal(null); });
    }
    return () => { cancelled = true; };
  }, [debouncedQuery]);

  const rows = state.rows;
  const totalKnown = total != null ? total : state.total;
  const startRow = page * pageSize + (rows.length ? 1 : 0);
  const endRow = page * pageSize + rows.length;
  const hasNext = total != null ? (page + 1) * pageSize < total : rows.length === pageSize;
  const hasPrev = page > 0;

  const onPageSizeChange = (e) => {
    const v = parseInt(e.target.value, 10);
    setPageSize(v);
    window.sessionStorage.setItem(PAGE_SIZE_KEY, String(v));
  };

  const toggleSort = (key) => {
    setSort(s => s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" });
    setPage(0);
  };

  const SortHead = ({ k, children, align }) => (
    <th onClick={() => toggleSort(k)} style={{ cursor: "pointer", textAlign: align || "left" }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        {children}
        {sort.key === k && (sort.dir === "asc" ? <window.MIcons.Up size={11} /> : <window.MIcons.Down size={11} />)}
      </span>
    </th>
  );

  return (
    <div className="page fade-in" data-testid="patients-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", letterSpacing: "-0.02em" }}>Patients</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }} data-testid="patients-total-summary">
            {totalKnown != null ? `${totalKnown} patient${totalKnown === 1 ? "" : "s"}` : "Loading…"}
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "var(--gap)" }}>
        <div style={{ padding: 14, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <div className="search" style={{ flex: 1, minWidth: 240 }}>
            <window.MIcons.Search size={15} />
            <input
              data-testid="patients-search"
              placeholder="Search by name, mobile, or email…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        <div style={{ overflowX: "auto" }}>
          {state.status === "loading" && <PatientsSkeleton />}
          {state.status === "error" && (
            <div className="card-pad" data-testid="patients-error" style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
              {state.error}
            </div>
          )}
          {state.status === "ready" && rows.length === 0 && (
            <div data-testid="patients-empty-state" style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              {debouncedQuery
                ? `No patients match "${debouncedQuery}".`
                : "No patients in this practice yet."}
            </div>
          )}
          {state.status === "ready" && rows.length > 0 && (
            <table className="table" data-testid="patients-table">
              <thead>
                <tr>
                  <SortHead k="patient_name">Patient</SortHead>
                  <SortHead k="dob" align="right">Age</SortHead>
                  <th>Sex</th>
                  <th>Status</th>
                  <th>Contact</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(p => (
                  <tr key={p.name} data-testid="patients-row" onClick={() => go("patient", p.name)} style={{ cursor: "pointer" }}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div className="avatar avatar-sm" style={{ width: 32, height: 32, fontSize: 11 }}>
                          {(p.patient_name || p.name || "?").split(" ").map(n => n[0]).join("").slice(0, 2)}
                        </div>
                        <div>
                          <div style={{ fontWeight: 500 }}>{p.patient_name || p.name}</div>
                        </div>
                      </div>
                    </td>
                    <td className="mono" style={{ textAlign: "right" }}>{ageFromDob(p.dob)}</td>
                    <td>{p.sex || "—"}</td>
                    <td><span className={`badge ${p.status === "Active" ? "badge-success" : "badge-neutral"}`}>{p.status || "—"}</span></td>
                    <td style={{ fontSize: 12, color: "var(--text-muted)" }}>{p.email || p.mobile || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12, fontSize: 12.5, color: "var(--text-muted)" }}>
          <span>Rows per page</span>
          <select
            data-testid="patients-page-size"
            className="select"
            style={{ width: 70, height: 28, fontSize: 12 }}
            value={pageSize}
            onChange={onPageSizeChange}
          >
            {PAGE_SIZE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <span data-testid="patients-pagination-summary" style={{ marginLeft: "auto" }}>
            {rows.length === 0 ? "0 of 0" : `${startRow} – ${endRow} of ${totalKnown != null ? totalKnown : "?"}`}
          </span>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              data-testid="patients-prev"
              className="btn btn-secondary btn-sm"
              style={{ width: 28, padding: 0 }}
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={!hasPrev}
            >
              <window.MIcons.ChevronLeft size={14} />
            </button>
            <button
              data-testid="patients-next"
              className="btn btn-secondary btn-sm"
              style={{ width: 28, padding: 0 }}
              onClick={() => setPage(p => p + 1)}
              disabled={!hasNext}
            >
              <window.MIcons.ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PatientsSkeleton() {
  return (
    <div data-testid="patients-skeleton" style={{ padding: 20 }}>
      {[0, 1, 2, 3].map(i => (
        <div key={i} style={{ display: "flex", gap: 12, alignItems: "center", padding: "12px 0", borderBottom: i < 3 ? "1px solid var(--border)" : "none" }}>
          <div style={{ width: 32, height: 32, borderRadius: 16, background: "var(--bg-subtle)", animation: "pulse 1.6s infinite" }} />
          <div style={{ flex: 1, height: 14, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
          <div style={{ width: 80, height: 14, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
        </div>
      ))}
    </div>
  );
}

function ageFromDob(dob) {
  if (!dob) return "—";
  const birth = new Date(dob);
  if (isNaN(birth)) return "—";
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const m = now.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < birth.getDate())) age -= 1;
  return age >= 0 ? age : "—";
}

window.MPatientsScreen = MPatientsScreen;
