// Appointments list — wired to medic_plus.api.daystar_health.get_appointments.
// Filter toolbar: date range, status toggle buttons, practitioner select.
// Clicking a row navigates to the patient detail screen.

const APPT_STORAGE_KEY = "daystar.appointments.filters";
const STATUS_OPTIONS = ["Scheduled", "Open", "Checked In", "Closed", "Cancelled"];

function _todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function _plusDaysStr(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function _loadInitialFilters() {
  try {
    const raw = window.sessionStorage.getItem(APPT_STORAGE_KEY);
    if (raw) {
      const p = JSON.parse(raw);
      return {
        dateFrom: p.dateFrom || _todayStr(),
        dateTo: p.dateTo || _plusDaysStr(7),
        status: Array.isArray(p.status) && p.status.length ? p.status : ["Scheduled", "Open", "Checked In"],
        practitioner: p.practitioner || "",
      };
    }
  } catch (_) {}
  return {
    dateFrom: _todayStr(),
    dateTo: _plusDaysStr(7),
    status: ["Scheduled", "Open", "Checked In"],
    practitioner: "",
  };
}

function _saveFilters(f) {
  try {
    window.sessionStorage.setItem(APPT_STORAGE_KEY, JSON.stringify(f));
  } catch (_) {}
}

function _apptBadgeClass(status) {
  if (status === "Scheduled") return "badge-info";
  if (status === "Open") return "badge-success";
  if (status === "Checked In") return "badge-success";
  if (status === "Cancelled") return "badge-danger";
  return "badge-neutral"; // Closed and anything else
}

function _formatTime(t) {
  if (!t) return "—";
  const parts = String(t).split(":");
  if (parts.length < 2) return t;
  const h = parseInt(parts[0], 10);
  const m = parts[1];
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 || 12;
  return `${h12}:${m} ${ampm}`;
}

const _ACTIVE_STATUSES = new Set(["Scheduled", "Open", "Confirmed"]);

function MAppointmentsScreen({ go }) {
  const init = _loadInitialFilters();

  // Filter state — individual variables mirror the patients.jsx pattern.
  const [dateFrom, setDateFrom] = mUseState(init.dateFrom);
  const [dateTo, setDateTo] = mUseState(init.dateTo);
  const [statusList, setStatusList] = mUseState(init.status);
  const [practitioner, setPractitioner] = mUseState(init.practitioner);

  // Debounced copies that actually drive the fetch.
  const [debDateFrom, setDebDateFrom] = mUseState(init.dateFrom);
  const [debDateTo, setDebDateTo] = mUseState(init.dateTo);
  const [debStatusList, setDebStatusList] = mUseState(init.status);
  const [debPractitioner, setDebPractitioner] = mUseState(init.practitioner);

  const [state, setState] = mUseState({ status: "loading", rows: [], error: null });
  const [practitioners, setPractitioners] = mUseState([]);
  // localRefreshKey bumps after a consultation is started so the list re-fetches.
  const [localRefreshKey, setLocalRefreshKey] = mUseState(0);
  // Tracks which appointment is currently being started (shows spinner on that row).
  const [startingAppt, setStartingAppt] = mUseState(null);

  // 300 ms debounce — mirror the patients-list search pattern.
  mUseEffect(() => {
    const filters = { dateFrom, dateTo, status: statusList, practitioner };
    const t = setTimeout(() => {
      setDebDateFrom(dateFrom);
      setDebDateTo(dateTo);
      setDebStatusList(statusList);
      setDebPractitioner(practitioner);
      _saveFilters(filters);
    }, 300);
    return () => clearTimeout(t);
  // statusList.join is stable as a comparison key because it's a string.
  }, [dateFrom, dateTo, statusList.join(","), practitioner]);

  // Populate practitioner dropdown once on mount (PQC scopes it automatically).
  mUseEffect(() => {
    window.meridianApi.resource("Healthcare Practitioner", {
      fields: ["name", "practitioner_name"],
      limit_page_length: 200,
    }).then(resp => {
      const rows = resp && resp.data ? resp.data : (Array.isArray(resp) ? resp : []);
      setPractitioners(rows);
    }).catch(() => {});
  }, []);

  const handleRowClick = (a) => {
    if (a.encounter) {
      go("encounter", a.encounter);
    } else {
      go("patient", a.patient);
    }
  };

  const handleStart = async (e, apptName) => {
    e.stopPropagation();
    setStartingAppt(apptName);
    try {
      const result = await window.meridianApi.call(
        "medic_plus.api.daystar_health.start_consultation_from_appointment",
        { appointment: apptName }
      );
      setLocalRefreshKey(k => k + 1);
      go("encounter", result.encounter);
    } catch (err) {
      window.meridianApi.showError(err.message || "Could not start consultation.");
    } finally {
      setStartingAppt(null);
    }
  };

  // Fetch appointments whenever debounced filters change.
  mUseEffect(() => {
    let cancelled = false;
    setState(s => ({ ...s, status: "loading", error: null }));

    const apiFilters = {
      date_from: debDateFrom,
      date_to: debDateTo,
      status: debStatusList,
    };
    if (debPractitioner) apiFilters.practitioner = debPractitioner;

    window.meridianApi
      .call("medic_plus.api.daystar_health.get_appointments", { filters: apiFilters })
      .then(rows => {
        if (cancelled) return;
        setState({ status: "ready", rows: Array.isArray(rows) ? rows : [], error: null });
      })
      .catch(err => {
        if (cancelled) return;
        const msg = err.message || "Could not load appointments.";
        setState({ status: "error", rows: [], error: msg });
        window.meridianApi.showError(msg);
      });

    return () => { cancelled = true; };
  }, [debDateFrom, debDateTo, debStatusList.join(","), debPractitioner, localRefreshKey]);

  const toggleStatus = (s) => {
    setStatusList(prev => {
      const next = prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s];
      // Never allow an empty selection — keep the current set if the last item is unchecked.
      return next.length > 0 ? next : prev;
    });
  };

  const rows = state.rows;

  return (
    <div className="page fade-in" data-testid="appointments-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", letterSpacing: "-0.02em" }}>Appointments</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }} data-testid="appointments-summary">
            {state.status === "ready"
              ? `${rows.length} appointment${rows.length === 1 ? "" : "s"}`
              : "Loading…"}
          </p>
        </div>
      </div>

      {/* ── Toolbar ── */}
      <div className="card" style={{ marginBottom: "var(--gap)", padding: 14 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ width: 148 }}>
            <label style={{ fontSize: 11.5, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>From</label>
            <window.MDatePicker
              data-testid="appointments-date-from"
              value={dateFrom}
              onChange={(v) => setDateFrom(v)}
              placeholder="YYYY-MM-DD"
            />
          </div>
          <div style={{ width: 148 }}>
            <label style={{ fontSize: 11.5, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>To</label>
            <window.MDatePicker
              data-testid="appointments-date-to"
              value={dateTo}
              onChange={(v) => setDateTo(v)}
              placeholder="YYYY-MM-DD"
            />
          </div>
          <div>
            <label style={{ fontSize: 11.5, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Status</label>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {STATUS_OPTIONS.map(s => (
                <button
                  key={s}
                  data-testid={`appointments-status-${s.toLowerCase()}`}
                  onClick={() => toggleStatus(s)}
                  className={`btn btn-sm ${statusList.includes(s) ? "btn-primary" : "btn-secondary"}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11.5, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Practitioner</label>
            <select
              data-testid="appointments-practitioner"
              className="select"
              style={{ width: 210 }}
              value={practitioner}
              onChange={e => setPractitioner(e.target.value)}
            >
              <option value="">All practitioners</option>
              {practitioners.map(p => (
                <option key={p.name} value={p.name}>{p.practitioner_name || p.name}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* ── Table ── */}
      <div className="card">
        {state.status === "loading" && <AppointmentsSkeleton />}
        {state.status === "error" && (
          <div data-testid="appointments-error" style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
            {state.error}
          </div>
        )}
        {state.status === "ready" && rows.length === 0 && (
          <div data-testid="appointments-empty-state" style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
            No appointments in this window. Try adjusting the date range or status filters.
          </div>
        )}
        {state.status === "ready" && rows.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table className="table" data-testid="appointments-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Patient</th>
                  <th>Practitioner</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Consultation</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(a => (
                  <tr
                    key={a.name}
                    data-testid="appointments-row"
                    onClick={() => handleRowClick(a)}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="mono">{a.appointment_date || "—"}</td>
                    <td className="mono">{_formatTime(a.appointment_time)}</td>
                    <td style={{ fontWeight: 500 }}>{a.patient_name || a.patient || "—"}</td>
                    <td style={{ color: "var(--text-muted)", fontSize: 13 }}>{a.practitioner_name || a.practitioner || "—"}</td>
                    <td style={{ color: "var(--text-muted)", fontSize: 13 }}>{a.appointment_type || "—"}</td>
                    <td>
                      <span className={`badge ${_apptBadgeClass(a.status)}`}>{a.status || "—"}</span>
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      {a.encounter ? (
                        <button
                          className="btn btn-ghost btn-xs"
                          data-testid={`open-encounter-${a.name}`}
                          onClick={() => go("encounter", a.encounter)}
                        >
                          Open ↗
                        </button>
                      ) : _ACTIVE_STATUSES.has(a.status) ? (
                        <button
                          className="btn btn-primary btn-xs"
                          data-testid={`start-consultation-${a.name}`}
                          disabled={startingAppt === a.name}
                          onClick={e => handleStart(e, a.name)}
                        >
                          {startingAppt === a.name ? "Starting…" : "Start"}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function AppointmentsSkeleton() {
  return (
    <div data-testid="appointments-skeleton" style={{ padding: 20 }}>
      {[0, 1, 2, 3].map(i => (
        <div key={i} style={{ display: "flex", gap: 12, alignItems: "center", padding: "12px 0", borderBottom: i < 3 ? "1px solid var(--border)" : "none" }}>
          <div style={{ width: 90, height: 14, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
          <div style={{ width: 60, height: 14, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
          <div style={{ flex: 1, height: 14, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
          <div style={{ width: 130, height: 14, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
          <div style={{ width: 80, height: 14, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
          <div style={{ width: 75, height: 14, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
        </div>
      ))}
    </div>
  );
}

window.MAppointmentsScreen = MAppointmentsScreen;
