// Billing & Claims screen — wired to medic_plus.api.daystar_health.get_invoices.
// Shows Sales Invoices scoped to the active practice's ERPNext Company.
// Appointments that reference an invoice are linked in the row.

const BILLING_STORAGE_KEY = "daystar.billing.filters";
const BILLING_STATUS_OPTIONS = ["Unpaid", "Overdue", "Paid", "Draft"];

function _billYear() {
  return new Date().getFullYear();
}

function _billYearStart() {
  return `${_billYear()}-01-01`;
}

function _todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function _loadBillingFilters() {
  try {
    const raw = window.sessionStorage.getItem(BILLING_STORAGE_KEY);
    if (raw) {
      const p = JSON.parse(raw);
      return {
        dateFrom: p.dateFrom || _billYearStart(),
        dateTo: p.dateTo || _todayStr(),
        status: Array.isArray(p.status) && p.status.length ? p.status : [],
      };
    }
  } catch (_) {}
  return { dateFrom: _billYearStart(), dateTo: _todayStr(), status: [] };
}

function _saveBillingFilters(f) {
  try { window.sessionStorage.setItem(BILLING_STORAGE_KEY, JSON.stringify(f)); } catch (_) {}
}

function _statusBadgeClass(status) {
  if (status === "Paid") return "badge-success";
  if (status === "Overdue") return "badge-danger";
  if (status === "Unpaid") return "badge-warn";
  return "badge-neutral";
}

function _fmt(amount, currency) {
  const sym = currency === "ZAR" ? "R" : (currency || "");
  return `${sym} ${Number(amount || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function BillingStatTile({ label, value, sub, color }) {
  return (
    <div className="card" style={{ padding: "18px 20px", flex: 1, minWidth: 160 }}>
      <div style={{ fontSize: 11.5, color: "var(--text-muted)", fontWeight: 500, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", color: color || "var(--text-color)", fontFamily: "var(--font-mono)" }}>{value}</div>
      {sub && <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function BillingSkeleton() {
  return (
    <div data-testid="billing-skeleton" style={{ padding: 20 }}>
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} style={{ display: "flex", gap: 12, padding: "12px 0", borderBottom: i < 4 ? "1px solid var(--border)" : "none" }}>
          {[80, 140, 90, 100, 90, 70].map((w, j) => (
            <div key={j} style={{ width: w, height: 13, background: "var(--bg-subtle)", borderRadius: 4, animation: "pulse 1.6s infinite" }} />
          ))}
        </div>
      ))}
    </div>
  );
}

function MBillingScreen({ go }) {
  const init = _loadBillingFilters();

  const [dateFrom, setDateFrom] = mUseState(init.dateFrom);
  const [dateTo, setDateTo] = mUseState(init.dateTo);
  const [statusList, setStatusList] = mUseState(init.status);

  const [debDateFrom, setDebDateFrom] = mUseState(init.dateFrom);
  const [debDateTo, setDebDateTo] = mUseState(init.dateTo);
  const [debStatusList, setDebStatusList] = mUseState(init.status);

  const PAGE_SIZE = 50;
  const [limitStart, setLimitStart] = mUseState(0);
  const [state, setState] = mUseState({ status: "loading", rows: [], total: 0, summary: null, error: null });

  // Debounce filter changes 300ms.
  mUseEffect(() => {
    const f = { dateFrom, dateTo, status: statusList };
    const t = setTimeout(() => {
      setDebDateFrom(dateFrom);
      setDebDateTo(dateTo);
      setDebStatusList(statusList);
      setLimitStart(0);
      _saveBillingFilters(f);
    }, 300);
    return () => clearTimeout(t);
  }, [dateFrom, dateTo, statusList.join(",")]);

  // Fetch when debounced values or page changes.
  mUseEffect(() => {
    let cancelled = false;
    setState(s => ({ ...s, status: "loading", error: null }));

    const apiFilters = { date_from: debDateFrom, date_to: debDateTo };
    if (debStatusList.length) apiFilters.status = debStatusList;

    window.meridianApi
      .call("medic_plus.api.daystar_health.get_invoices", {
        filters: apiFilters,
        limit_start: limitStart,
        limit_page_length: PAGE_SIZE,
      })
      .then(res => {
        if (cancelled) return;
        setState({ status: "ready", rows: res.rows || [], total: res.total || 0, summary: res.summary || null, error: null });
      })
      .catch(err => {
        if (cancelled) return;
        const msg = err.message || "Could not load invoices.";
        setState({ status: "error", rows: [], total: 0, summary: null, error: msg });
        window.meridianApi.showError(msg);
      });

    return () => { cancelled = true; };
  }, [debDateFrom, debDateTo, debStatusList.join(","), limitStart]);

  const toggleStatus = (s) => {
    setStatusList(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  };

  const { rows, total, summary } = state;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(limitStart / PAGE_SIZE) + 1;
  const currency = rows.length ? rows[0].currency : "ZAR";

  return (
    <div className="page fade-in" data-testid="billing-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", letterSpacing: "-0.02em" }}>Billing & Claims</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }} data-testid="billing-summary">
            {state.status === "ready" ? `${total} invoice${total === 1 ? "" : "s"}` : "Loading…"}
          </p>
        </div>
      </div>

      {/* Summary tiles */}
      {summary && (
        <div style={{ display: "flex", gap: 12, marginBottom: "var(--gap)", flexWrap: "wrap" }}>
          <BillingStatTile
            label="Invoiced"
            value={_fmt(summary.total_invoiced, currency)}
          />
          <BillingStatTile
            label="Paid"
            value={_fmt(summary.total_paid, currency)}
            color="var(--success, #16a34a)"
          />
          <BillingStatTile
            label="Outstanding"
            value={_fmt(summary.total_outstanding, currency)}
            color={summary.total_outstanding > 0 ? "var(--danger, #dc2626)" : undefined}
            sub={summary.total_outstanding > 0 ? "Requires collection" : "All settled"}
          />
        </div>
      )}

      {/* Toolbar */}
      <div className="card" style={{ marginBottom: "var(--gap)", padding: 14 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ width: 148 }}>
            <label style={{ fontSize: 11.5, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>From</label>
            <window.MDatePicker data-testid="billing-date-from" value={dateFrom} onChange={setDateFrom} placeholder="YYYY-MM-DD" />
          </div>
          <div style={{ width: 148 }}>
            <label style={{ fontSize: 11.5, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>To</label>
            <window.MDatePicker data-testid="billing-date-to" value={dateTo} onChange={setDateTo} placeholder="YYYY-MM-DD" />
          </div>
          <div>
            <label style={{ fontSize: 11.5, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Status</label>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {BILLING_STATUS_OPTIONS.map(s => (
                <button
                  key={s}
                  data-testid={`billing-status-${s.toLowerCase()}`}
                  onClick={() => toggleStatus(s)}
                  className={`btn btn-sm ${statusList.includes(s) ? "btn-primary" : "btn-secondary"}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card">
        {state.status === "loading" && <BillingSkeleton />}
        {state.status === "error" && (
          <div data-testid="billing-error" style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
            {state.error}
          </div>
        )}
        {state.status === "ready" && rows.length === 0 && (
          <div data-testid="billing-empty" style={{ padding: 56, textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 8 }}>No invoices in this period.</div>
            <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Invoices are created automatically when a consultation is billed in ERPNext.</div>
          </div>
        )}
        {state.status === "ready" && rows.length > 0 && (
          <>
            <div style={{ overflowX: "auto" }}>
              <table className="table" data-testid="billing-table">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Date</th>
                    <th>Patient</th>
                    <th>Appointment</th>
                    <th style={{ textAlign: "right" }}>Amount</th>
                    <th style={{ textAlign: "right" }}>Outstanding</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(inv => (
                    <tr key={inv.name} data-testid="billing-row">
                      <td className="mono" style={{ fontSize: 12 }}>{inv.name}</td>
                      <td className="mono" style={{ fontSize: 12 }}>{inv.posting_date || "—"}</td>
                      <td style={{ fontWeight: 500 }}>
                        {inv.patient ? (
                          <button
                            className="btn btn-ghost btn-xs"
                            style={{ fontWeight: 500, padding: 0 }}
                            onClick={() => go("patient", inv.patient)}
                          >
                            {inv.patient_name || inv.patient}
                          </button>
                        ) : "—"}
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {inv.appointment ? (
                          <button
                            className="btn btn-ghost btn-xs"
                            style={{ color: "var(--text-muted)" }}
                            onClick={() => go("encounter", inv.appointment)}
                          >
                            {inv.appointment_date || inv.appointment}
                            {inv.appointment_type ? ` · ${inv.appointment_type}` : ""}
                          </button>
                        ) : "—"}
                      </td>
                      <td className="mono" style={{ textAlign: "right", fontWeight: 500 }}>
                        {_fmt(inv.grand_total, inv.currency)}
                      </td>
                      <td className="mono" style={{ textAlign: "right", color: inv.outstanding_amount > 0 ? "var(--danger, #dc2626)" : "var(--text-muted)" }}>
                        {inv.outstanding_amount > 0 ? _fmt(inv.outstanding_amount, inv.currency) : "—"}
                      </td>
                      <td>
                        <span className={`badge ${_statusBadgeClass(inv.status)}`}>{inv.status || "—"}</span>
                      </td>
                      <td>
                        <a
                          href={`/accounting/sales-invoice/${inv.name}`}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-ghost btn-xs"
                          title="Open in Desk"
                        >
                          ↗
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8, padding: "10px 16px", borderTop: "1px solid var(--border)" }}>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  Page {currentPage} of {totalPages} · {total} invoices
                </span>
                <button
                  className="btn btn-secondary btn-xs"
                  disabled={limitStart === 0}
                  onClick={() => setLimitStart(Math.max(0, limitStart - PAGE_SIZE))}
                >
                  ← Prev
                </button>
                <button
                  className="btn btn-secondary btn-xs"
                  disabled={limitStart + PAGE_SIZE >= total}
                  onClick={() => setLimitStart(limitStart + PAGE_SIZE)}
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

window.MBillingScreen = MBillingScreen;
