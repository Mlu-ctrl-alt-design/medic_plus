// Phase 1D: Prescription Panel
//
// MPrescriptionPanel — manage a Drug Prescription child-table in the context
// of a Patient Encounter.
//
// Props:
//   patient         string   — Patient name (for live allergy checks)
//   prescriber      string   — Healthcare Practitioner name (for Schedule checks)
//   rows            array    — controlled drug-prescription rows
//   onChange        fn(rows) — called on any row mutation
//   disabled        bool     — lock the panel (e.g. encounter is submitted)
//
// Each row: { nappi_code_value, drug_name, schedule, strength, dosage_form,
//             dosage, period, custom_repeats_authorised, custom_repeats_remaining,
//             custom_generic_substitution_allowed, _override_reason }
//
// The panel calls check_prescription_safety on every NAPPI change and renders
// orange warning badges per row.  When a warning badge is clicked an override
// reason textarea opens; once filled the badge turns grey ("Override noted").

const EMPTY_RX_ROW = () => ({
  nappi_code_value: '',
  drug_name: '',
  schedule: '',
  strength: '',
  dosage_form: '',
  dosage: '',
  period: '',
  custom_repeats_authorised: 0,
  custom_generic_substitution_allowed: 0,
  _override_reason: '',
  _warnings: [],
  _override_open: false,
});

function MPrescriptionRow({ row, idx, patient, prescriber, onUpdate, onRemove, disabled }) {
  const api = window.meridianApi || {};

  // Fetch Drug Master metadata when NAPPI CV changes
  React.useEffect(() => {
    if (!row.nappi_code_value) return;
    let cancelled = false;
    api.call('medic_plus.api.daystar_health.get_drug_master_by_nappi', {
      nappi_code_value: row.nappi_code_value,
    }).then((dm) => {
      if (cancelled || !dm) return;
      onUpdate(idx, {
        drug_name: dm.drug_name || row.drug_name,
        schedule: dm.schedule || '',
        strength: dm.strength || '',
        dosage_form: dm.dosage_form || '',
      });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [row.nappi_code_value]);

  // Live allergy/schedule warnings when patient + nappi CV are set
  React.useEffect(() => {
    if (!row.nappi_code_value || !patient) {
      onUpdate(idx, { _warnings: [] });
      return;
    }
    let cancelled = false;
    api.call('medic_plus.api.daystar_health.check_prescription_safety', {
      patient,
      nappi_code_values: JSON.stringify([row.nappi_code_value]),
    }).then((ws) => {
      if (!cancelled) onUpdate(idx, { _warnings: ws || [] });
    }).catch(() => {
      if (!cancelled) onUpdate(idx, { _warnings: [] });
    });
    return () => { cancelled = true; };
  }, [row.nappi_code_value, patient]);

  const hasUncovered = row._warnings.length > 0 && !row._override_reason;
  const hasCovered   = row._warnings.length > 0 && !!row._override_reason;

  const inputStyle = { fontSize: 12, padding: '4px 8px', borderRadius: 4,
    border: '1px solid var(--border)', background: 'var(--input-bg, #fff)',
    color: 'var(--text-dark)', width: '100%', boxSizing: 'border-box' };
  const labelStyle = { fontSize: 11, color: 'var(--text-muted)', display: 'block',
    marginBottom: 2 };

  return (
    <div
      data-testid={`rx-row-${idx}`}
      style={{
        border: `1px solid ${hasUncovered ? 'var(--warning, #f59e0b)' : 'var(--border)'}`,
        borderRadius: 8, padding: 12, marginBottom: 10,
        background: hasUncovered ? 'var(--warning-soft, #fffbeb)' : 'var(--surface)',
        position: 'relative',
      }}
    >
      {!disabled && (
        <button
          type="button"
          data-testid={`rx-row-remove-${idx}`}
          onClick={() => onRemove(idx)}
          aria-label={`Remove drug ${idx + 1}`}
          style={{ position: 'absolute', top: 8, right: 8, background: 'none', border: 'none',
            cursor: 'pointer', fontSize: 14, color: 'var(--text-muted)', lineHeight: 1 }}
          title="Remove drug"
        >✕</button>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
        <div>
          <label style={labelStyle}>NAPPI Medicine *</label>
          <window.MNappiPicker
            value={row.nappi_code_value}
            testid={`rx-nappi-${idx}`}
            onChange={({ code, display }) =>
              onUpdate(idx, { nappi_code_value: `${code}-NAPPI`, drug_name: display })
            }
          />
        </div>
        <div>
          <label style={labelStyle}>Drug Name</label>
          <input
            type="text"
            data-testid={`rx-drugname-${idx}`}
            value={row.drug_name}
            onChange={(e) => onUpdate(idx, { drug_name: e.target.value })}
            style={inputStyle}
            disabled={disabled}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 8 }}>
        <div>
          <label style={labelStyle}>Schedule</label>
          <input
            type="text"
            data-testid={`rx-sched-${idx}`}
            value={row.schedule}
            readOnly
            style={{ ...inputStyle, background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}
          />
        </div>
        <div>
          <label style={labelStyle}>Strength</label>
          <input
            type="text"
            value={row.strength}
            onChange={(e) => onUpdate(idx, { strength: e.target.value })}
            style={inputStyle}
            disabled={disabled}
          />
        </div>
        <div>
          <label style={labelStyle}>Dosage Form</label>
          <input
            type="text"
            value={row.dosage_form}
            onChange={(e) => onUpdate(idx, { dosage_form: e.target.value })}
            style={inputStyle}
            disabled={disabled}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8, marginBottom: 8 }}>
        <div>
          <label style={labelStyle}>Dosage</label>
          <input
            type="text"
            data-testid={`rx-dosage-${idx}`}
            value={row.dosage}
            onChange={(e) => onUpdate(idx, { dosage: e.target.value })}
            placeholder="e.g. 1 tablet BD"
            style={inputStyle}
            disabled={disabled}
          />
        </div>
        <div>
          <label style={labelStyle}>Duration</label>
          <input
            type="text"
            value={row.period}
            onChange={(e) => onUpdate(idx, { period: e.target.value })}
            placeholder="e.g. 7 days"
            style={inputStyle}
            disabled={disabled}
          />
        </div>
        <div>
          <label style={labelStyle}>Repeats Authorised</label>
          <input
            type="number"
            min="0"
            data-testid={`rx-repeats-${idx}`}
            value={row.custom_repeats_authorised}
            onChange={(e) => onUpdate(idx, { custom_repeats_authorised: Number(e.target.value) })}
            style={inputStyle}
            disabled={disabled}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 16 }}>
          <input
            type="checkbox"
            id={`rx-gensub-${idx}`}
            checked={!!row.custom_generic_substitution_allowed}
            onChange={(e) => onUpdate(idx, { custom_generic_substitution_allowed: e.target.checked ? 1 : 0 })}
            disabled={disabled}
          />
          <label htmlFor={`rx-gensub-${idx}`} style={{ fontSize: 11, cursor: 'pointer' }}>
            Generic sub
          </label>
        </div>
      </div>

      {row._warnings.length > 0 && (
        <div style={{ marginTop: 6 }}>
          {row._warnings.map((w, wi) => (
            <span
              key={wi}
              data-testid={`rx-warning-badge-${idx}-${wi}`}
              title={w.message}
              style={{
                display: 'inline-block', fontSize: 10, padding: '2px 8px',
                borderRadius: 12, marginRight: 6, marginBottom: 4, cursor: 'pointer',
                background: hasCovered ? 'var(--text-muted)' : 'var(--warning, #f59e0b)',
                color: '#fff', fontWeight: 600,
              }}
              onClick={() => onUpdate(idx, { _override_open: !row._override_open })}
            >
              {hasCovered ? '✓ Override noted' : `⚠ ${w.type === 'drug_allergy' ? 'Allergy' : w.type === 'schedule_rule' ? 'Schedule' : 'Interaction'}`}
            </span>
          ))}
        </div>
      )}

      {row._warnings.length > 0 && (row._override_open || hasUncovered) && (
        <div
          data-testid={`rx-override-${idx}`}
          style={{
            marginTop: 8, padding: 8, background: 'var(--warning-soft, #fffbeb)',
            border: '1px solid var(--warning, #f59e0b)', borderRadius: 6,
          }}
        >
          <label style={{ ...labelStyle, fontWeight: 600, color: '#92400e' }}>
            Override reason (required to proceed) *
          </label>
          <textarea
            data-testid={`rx-override-reason-${idx}`}
            rows={2}
            value={row._override_reason}
            onChange={(e) => onUpdate(idx, { _override_reason: e.target.value })}
            placeholder="Clinical justification for overriding the warning…"
            style={{ ...inputStyle, resize: 'vertical', minHeight: 48 }}
            disabled={disabled}
          />
          {row._warnings.map((w, wi) => (
            <p key={wi} style={{ fontSize: 10, color: '#92400e', margin: '4px 0 0' }}>
              {w.message}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function MPrescriptionPanel({ patient, prescriber, rows, onChange, disabled = false }) {
  const addRow = () => onChange([...rows, EMPTY_RX_ROW()]);

  const updateRow = (idx, patch) => {
    const updated = rows.map((r, i) => i === idx ? { ...r, ...patch } : r);
    onChange(updated);
  };

  const removeRow = (idx) => onChange(rows.filter((_, i) => i !== idx));

  const hasUncoveredWarnings = rows.some(
    (r) => r._warnings && r._warnings.length > 0 && !r._override_reason
  );

  return (
    <div data-testid="prescription-panel">
      {rows.length === 0 && (
        <div
          data-testid="rx-empty"
          style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 12,
            padding: '16px 0', borderRadius: 8, border: '1px dashed var(--border)' }}
        >
          No medications added yet.
        </div>
      )}

      {rows.map((row, idx) => (
        <MPrescriptionRow
          key={idx}
          row={row}
          idx={idx}
          patient={patient}
          prescriber={prescriber}
          onUpdate={updateRow}
          onRemove={removeRow}
          disabled={disabled}
        />
      ))}

      {!disabled && (
        <button
          type="button"
          data-testid="rx-add-drug"
          onClick={addRow}
          className="btn btn-outline btn-sm"
          style={{ marginTop: 4 }}
        >
          + Add drug
        </button>
      )}

      {hasUncoveredWarnings && (
        <div
          data-testid="rx-uncovered-warning-notice"
          role="alert"
          aria-live="polite"
          style={{
            marginTop: 10, padding: '8px 12px', background: 'var(--warning-soft, #fffbeb)',
            border: '1px solid var(--warning, #f59e0b)', borderRadius: 6,
            fontSize: 12, color: '#92400e', fontWeight: 500,
          }}
        >
          ⚠ One or more safety warnings require an override reason before saving.
        </div>
      )}
    </div>
  );
}

window.MPrescriptionPanel = MPrescriptionPanel;
