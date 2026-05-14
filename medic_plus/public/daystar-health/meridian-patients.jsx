// Patients list + Register Patient drawer.
// Phase 1A: identifier picker (SAID / Passport / …), race, home language,
// preferred language, POPIA consent for special personal information.

const PATIENTS_FIELDS = [
  "name", "patient_name", "sex", "dob", "status", "mobile", "email", "custom_practice",
];
const PAGE_SIZE_KEY = "daystar.patients.pageSize";
const PAGE_SIZE_DEFAULT = 25;
const PAGE_SIZE_OPTIONS = [25, 50, 100];

const ID_TYPES = ["SAID", "Passport", "Refugee", "Asylum", "BirthCert", "NHID", "Other"];
const RACE_OPTIONS = ["", "African", "Coloured", "Indian or Asian", "White", "Other", "Prefer not to say"];
const LANG_OPTIONS = [
  "", "Afrikaans", "English", "isiNdebele", "isiXhosa", "isiZulu",
  "Sesotho sa Leboa", "Sesotho", "Setswana", "siSwati", "Tshivenda", "Xitsonga", "Other",
];

// ---------------------------------------------------------------------------
// Register Patient drawer
// ---------------------------------------------------------------------------

const BLANK_FORM = {
  first_name: "", last_name: "", sex: "", dob: "", email: "", mobile: "",
  id_type: "SAID", id_value: "",
  race: "", home_language: "", preferred_language: "",
  popia_consent: false,
  duplicate_warning: null,
};

function RegisterPatientDrawer({ open, practice, onClose, onCreated }) {
  const [form, setForm] = mUseState(BLANK_FORM);
  const [saving, setSaving] = mUseState(false);
  const [error, setError] = mUseState(null);

  // Reset state when the drawer reopens so a previous abandoned form
  // doesn't leak into the next session.
  mUseEffect(() => {
    if (open) {
      setForm(BLANK_FORM);
      setError(null);
      setSaving(false);
    }
  }, [open]);

  const set = (key, val) => setForm(f => ({ ...f, [key]: val, duplicate_warning: null }));

  const checkDuplicates = () => {
    if (!form.first_name) return;
    const name = [form.first_name, form.last_name].filter(Boolean).join(" ");
    window.meridianApi.call("medic_plus.api.patient_identity.find_duplicate_patients", {
      patient_name: name,
      practice,
      dob: form.dob || null,
      id_value: form.id_value || null,
    }).then(results => {
      if (results && results.length) {
        setForm(f => ({ ...f, duplicate_warning: results }));
      }
    }).catch(() => {});
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError(null);

    if (form.id_type === "SAID" && !form.popia_consent) {
      setError("POPIA consent is required before capturing an SA ID number.");
      return;
    }

    const identifiers = form.id_value ? [{
      id_type: form.id_type,
      id_value: form.id_value,
      is_primary: 1,
    }] : [];

    setSaving(true);
    window.meridianApi.call("frappe.client.insert", {
      doc: {
        doctype: "Patient",
        first_name: form.first_name,
        last_name: form.last_name || undefined,
        sex: form.sex || "Unknown",
        dob: form.dob || undefined,
        email: form.email || undefined,
        mobile: form.mobile || undefined,
        custom_practice: practice,
        custom_identifiers: identifiers,
        custom_race: form.race || undefined,
        custom_home_language: form.home_language || undefined,
        custom_preferred_language: form.preferred_language || undefined,
        custom_popia_consent_special: form.popia_consent ? 1 : 0,
      },
    }).then(doc => {
      setSaving(false);
      onCreated(doc.name);
    }).catch(err => {
      setSaving(false);
      const msg = (err.message || "").replace(/^[A-Za-z]+Error:\s*/i, "");
      setError(msg || "Could not register patient.");
    });
  };

  return (
    <window.MDrawer
      open={open}
      onClose={onClose}
      title="Register Patient"
      footer={
        <>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={saving}>Cancel</button>
          <button
            type="submit"
            form="register-patient-form"
            className="btn btn-primary btn-sm"
            disabled={saving}
            data-testid="reg-submit"
          >
            {saving ? "Registering…" : "Register Patient"}
          </button>
        </>
      }
    >
      <form id="register-patient-form" onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }} data-testid="register-patient-drawer">

          {/* Duplicate warning */}
          {form.duplicate_warning && (
            <div data-testid="duplicate-warning" style={{ padding: "10px 14px", background: "var(--warning-soft)", border: "1px solid var(--warning)", borderRadius: 8, fontSize: 13 }}>
              ⚠ {form.duplicate_warning.length} potential duplicate{form.duplicate_warning.length > 1 ? "s" : ""} found —
              {" "}{form.duplicate_warning.map(d => d.patient_name).join(", ")}.
              You may still proceed.
            </div>
          )}

          <section>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Demographics</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                First Name *
                <input className="input" required value={form.first_name}
                  onChange={e => set("first_name", e.target.value)}
                  onBlur={checkDuplicates} data-testid="reg-first-name" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Last Name
                <input className="input" value={form.last_name}
                  onChange={e => set("last_name", e.target.value)}
                  onBlur={checkDuplicates} data-testid="reg-last-name" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Sex
                <select className="select" value={form.sex} onChange={e => set("sex", e.target.value)} data-testid="reg-sex">
                  <option value="">— select —</option>
                  <option>Male</option><option>Female</option><option>Other</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Date of Birth
                <input className="input" type="date" value={form.dob}
                  onChange={e => set("dob", e.target.value)}
                  onBlur={checkDuplicates} data-testid="reg-dob" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Email
                <input className="input" type="email" value={form.email} onChange={e => set("email", e.target.value)} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Mobile
                <input className="input" type="tel" value={form.mobile} onChange={e => set("mobile", e.target.value)} />
              </label>
            </div>
          </section>

          <section>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Identifier</div>
            <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                ID Type
                <select className="select" value={form.id_type} onChange={e => set("id_type", e.target.value)} data-testid="reg-id-type">
                  {ID_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                ID Number
                <input className="input" value={form.id_value}
                  onChange={e => set("id_value", e.target.value)}
                  onBlur={checkDuplicates}
                  placeholder={form.id_type === "SAID" ? "13-digit SA ID" : "ID value"}
                  data-testid="reg-id-value" />
              </label>
            </div>
            {form.id_type === "SAID" && (
              <label style={{ display: "flex", alignItems: "flex-start", gap: 8, marginTop: 10, fontSize: 13, cursor: "pointer" }}>
                <input type="checkbox" checked={form.popia_consent}
                  onChange={e => set("popia_consent", e.target.checked)}
                  data-testid="reg-popia-consent"
                  style={{ marginTop: 2 }} />
                <span>
                  I confirm the patient has given informed consent for the collection of their SA ID number and other special personal information under{" "}
                  <strong>POPIA Section 27</strong>.
                </span>
              </label>
            )}
          </section>

          <section>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Language &amp; Background <span style={{ fontSize: 11, fontWeight: 400 }}>(optional)</span></div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Race
                <select className="select" value={form.race} onChange={e => set("race", e.target.value)} data-testid="reg-race">
                  {RACE_OPTIONS.map(r => <option key={r} value={r}>{r || "— select —"}</option>)}
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Home Language
                <select className="select" value={form.home_language} onChange={e => set("home_language", e.target.value)} data-testid="reg-home-language">
                  {LANG_OPTIONS.map(l => <option key={l} value={l}>{l || "— select —"}</option>)}
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Preferred Language
                <select className="select" value={form.preferred_language} onChange={e => set("preferred_language", e.target.value)} data-testid="reg-preferred-language">
                  {LANG_OPTIONS.map(l => <option key={l} value={l}>{l || "— select —"}</option>)}
                </select>
              </label>
            </div>
          </section>

          {error && (
            <div data-testid="reg-error" role="alert" style={{ padding: "10px 14px", background: "var(--danger-soft)", border: "1px solid var(--danger)", borderRadius: 8, color: "#b91c1c", fontSize: 13 }}>
              {error}
            </div>
          )}
      </form>
    </window.MDrawer>
  );
}

function MPatientsScreen({ go }) {
  const [showRegister, setShowRegister] = mUseState(false);
  const [practice, setPractice] = mUseState(null);
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

  // Resolve practice once on mount (needed by RegisterPatientDrawer).
  mUseEffect(() => {
    window.meridianApi.call("medic_plus.api.practice_resolver.get_active_practice")
      .then(p => setPractice(p))
      .catch(() => {});
  }, []);

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
      <RegisterPatientDrawer
        open={showRegister && Boolean(practice)}
        practice={practice}
        onClose={() => setShowRegister(false)}
        onCreated={(name) => {
          setShowRegister(false);
          go("patient", name);
        }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", letterSpacing: "-0.02em" }}>Patients</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }} data-testid="patients-total-summary">
            {totalKnown != null ? `${totalKnown} patient${totalKnown === 1 ? "" : "s"}` : "Loading…"}
          </p>
        </div>
        <button
          className="btn btn-primary btn-sm"
          data-testid="register-patient-btn"
          onClick={() => setShowRegister(true)}
          disabled={!practice}
        >
          + Register Patient
        </button>
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
