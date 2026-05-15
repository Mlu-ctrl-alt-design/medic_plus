// My Calendar — weekly view for the logged-in practitioner.
// Shows recurring schedule (working hours), booked appointments and
// personal time blocks side-by-side.  Doctors can add and remove blocks.
// Backed by medic_plus.api.calendar.*

const HOUR_HEIGHT = 60;     // px per hour in the day column
const CAL_START   = 7;      // display from 07:00
const CAL_END     = 19;     // display to   19:00
const TOTAL_H     = (CAL_END - CAL_START) * HOUR_HEIGHT;
const HOURS       = Array.from({ length: CAL_END - CAL_START }, (_, i) => CAL_START + i);
const DAY_NAMES   = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
const DAY_SHORT   = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function _weekMonday(from = new Date()) {
  const d = new Date(from);
  const dow = d.getDay(); // 0=Sun
  d.setDate(d.getDate() - (dow === 0 ? 6 : dow - 1));
  d.setHours(0, 0, 0, 0);
  return d;
}
function _isoDate(d) { return d.toISOString().slice(0, 10); }
function _timeToMin(t) {
  if (!t) return 0;
  const p = String(t).split(':');
  return parseInt(p[0], 10) * 60 + parseInt(p[1] || 0, 10);
}
function _minToPx(m) { return (m / 60) * HOUR_HEIGHT; }
function _topPx(t) { return _minToPx(_timeToMin(t) - CAL_START * 60); }
function _fmtTime(t) {
  if (!t) return '';
  const p = String(t).split(':');
  const h = parseInt(p[0], 10), m = p[1];
  return `${h % 12 || 12}:${m} ${h >= 12 ? 'PM' : 'AM'}`;
}
function _fmtDate(isoStr) {
  if (!isoStr) return '';
  const [y, mo, d] = isoStr.split('-').map(Number);
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    .format(new Date(y, mo - 1, d));
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CalSkeleton() {
  return (
    <div data-testid="calendar-skeleton" style={{ display: 'flex', gap: 8, padding: 20 }}>
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} style={{ flex: 1, height: 400, background: 'var(--bg-subtle)', borderRadius: 4, animation: 'pulse 1.6s infinite' }} />
      ))}
    </div>
  );
}

function NoPractitionerBanner({ deskUrl }) {
  return (
    <div className="card" style={{ padding: 32, textAlign: 'center' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>📅</div>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>No practitioner profile linked</h3>
      <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16, maxWidth: 420, margin: '0 auto 16px' }}>
        Your user account isn&apos;t linked to a Healthcare Practitioner record yet.
        Ask your Practice Admin to set your User ID in your practitioner profile,
        then refresh this page.
      </p>
      {deskUrl && (
        <a href={deskUrl} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">
          Open in Desk ↗
        </a>
      )}
    </div>
  );
}

// Appointment chip — absolutely positioned in the day column
function ApptChip({ appt, go }) {
  const topMin = _timeToMin(appt.appointment_time) - CAL_START * 60;
  if (topMin < 0) return null;
  const durMin = appt.duration || 30;
  const height = Math.max(_minToPx(durMin) - 2, 20);
  const isClose = appt.status === 'Closed';
  const accent = isClose ? '#16a34a' : '#2563eb';

  return (
    <div
      title={`${_fmtTime(appt.appointment_time)} — ${appt.patient_name} (${appt.status})`}
      style={{
        position: 'absolute',
        top: _minToPx(topMin),
        left: 2, right: 2, height,
        borderRadius: 4, padding: '2px 6px',
        background: `${accent}18`,
        border: `1px solid ${accent}55`,
        cursor: 'pointer', overflow: 'hidden',
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
      }}
      onClick={() => appt.encounter ? go('encounter', appt.encounter) : go('patient', appt.patient)}
    >
      <span style={{ fontSize: 10, fontWeight: 600, color: accent, lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {_fmtTime(appt.appointment_time)}
      </span>
      {height > 28 && (
        <span style={{ fontSize: 10, color: accent, opacity: 0.85, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {appt.patient_name}
        </span>
      )}
    </div>
  );
}

// Block chip — absolutely positioned or full-day banner
function BlockChip({ block, onDelete, deleting }) {
  const remove = (e) => { e.stopPropagation(); onDelete(block.name); };

  if (block.is_all_day) {
    return (
      <div style={{
        position: 'absolute', top: 2, left: 2, right: 2, bottom: 2,
        borderRadius: 4, padding: '4px 6px',
        background: 'rgba(107,114,128,0.1)',
        border: '1px dashed rgba(107,114,128,0.5)',
        display: 'flex', flexDirection: 'column', gap: 2,
      }}>
        <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)' }}>Blocked</span>
        {block.reason && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)', opacity: 0.8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {block.reason}
          </span>
        )}
        <button
          type="button"
          disabled={deleting}
          onClick={remove}
          title="Remove block"
          style={{ position: 'absolute', top: 2, right: 4, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 14, lineHeight: 1, padding: 0 }}
        >
          ×
        </button>
      </div>
    );
  }

  const topMin = _timeToMin(block.from_time) - CAL_START * 60;
  const durMin = _timeToMin(block.to_time) - _timeToMin(block.from_time);
  if (topMin < 0 || durMin <= 0) return null;
  const height = Math.max(_minToPx(durMin) - 2, 18);

  return (
    <div
      title={block.reason ? `Blocked: ${block.reason}` : 'Blocked'}
      style={{
        position: 'absolute',
        top: _minToPx(topMin), left: 2, right: 2, height,
        borderRadius: 4, padding: '2px 6px',
        background: 'rgba(107,114,128,0.13)',
        border: '1px solid rgba(107,114,128,0.4)',
        display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden',
      }}
    >
      <span style={{ fontSize: 10, color: 'var(--text-muted)', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        🚫 {block.reason || 'Blocked'}
      </span>
      <button
        type="button"
        disabled={deleting}
        onClick={remove}
        title="Remove block"
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 13, lineHeight: 1, padding: 0, flexShrink: 0 }}
      >
        ×
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Block-time modal
// ---------------------------------------------------------------------------
function BlockModal({ onClose, onSave, saving, defaultDate }) {
  const [form, setForm] = mUseState({
    block_date: defaultDate || _isoDate(new Date()),
    end_date: '',
    is_all_day: false,
    from_time: '',
    to_time: '',
    reason: '',
  });

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(form);
  };

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="card" style={{ width: 380, maxWidth: '95vw', padding: 24 }}>
        <h3 style={{ margin: '0 0 18px', fontSize: 16, fontWeight: 600 }}>Block Time</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Date *</label>
            <window.MDatePicker value={form.block_date} onChange={v => set('block_date', v)} placeholder="YYYY-MM-DD" />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>End Date <span style={{ opacity: 0.6 }}>(leave blank for single-day)</span></label>
            <window.MDatePicker value={form.end_date} onChange={v => set('end_date', v)} placeholder="YYYY-MM-DD" min={form.block_date} />
          </div>
          <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <input id="cal_allday" type="checkbox" checked={form.is_all_day} onChange={e => set('is_all_day', e.target.checked)} />
            <label htmlFor="cal_allday" style={{ fontSize: 13, cursor: 'pointer' }}>All day</label>
          </div>
          {!form.is_all_day && (
            <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>From *</label>
                <input type="time" className="input" value={form.from_time} required onChange={e => set('from_time', e.target.value)} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>To *</label>
                <input type="time" className="input" value={form.to_time} required onChange={e => set('to_time', e.target.value)} />
              </div>
            </div>
          )}
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Reason <span style={{ opacity: 0.6 }}>(optional)</span></label>
            <input
              type="text"
              className="input"
              placeholder="e.g. CME, Annual leave, Personal…"
              value={form.reason}
              onChange={e => set('reason', e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving || !form.block_date}>
              {saving ? 'Saving…' : 'Block Time'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------
function MCalendarScreen({ go }) {
  const [weekStart, setWeekStart] = mUseState(() => _isoDate(_weekMonday()));
  const [calData, setCalData] = mUseState(null);
  const [status, setStatus] = mUseState('loading');   // loading | no-practitioner | ready | error
  const [error, setError] = mUseState(null);
  const [showBlock, setShowBlock] = mUseState(false);
  const [blockSaving, setBlockSaving] = mUseState(false);
  const [deletingBlock, setDeletingBlock] = mUseState(null);
  const [clickedDate, setClickedDate] = mUseState(null);

  const fetchWeek = (ws) => {
    setStatus('loading');
    setError(null);
    window.meridianApi
      .call('medic_plus.api.calendar.get_calendar_week', { week_start: ws })
      .then(data => { setCalData(data); setStatus('ready'); })
      .catch(err => {
        const msg = err.message || '';
        if (msg.includes('No Healthcare Practitioner')) {
          setStatus('no-practitioner');
        } else {
          setError(msg || 'Could not load calendar.');
          setStatus('error');
        }
      });
  };

  mUseEffect(() => { fetchWeek(weekStart); }, [weekStart]);

  const goWeek = (delta) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + delta * 7);
    setWeekStart(_isoDate(d));
  };

  const goToday = () => setWeekStart(_isoDate(_weekMonday()));

  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + i);
    return d;
  });

  const todayIso = _isoDate(new Date());

  // Index calData by date
  const apptsByDate = {};
  const blocksByDate = {};
  if (calData) {
    (calData.appointments || []).forEach(a => {
      (apptsByDate[a.appointment_date] = apptsByDate[a.appointment_date] || []).push(a);
    });
    (calData.blocks || []).forEach(b => {
      (blocksByDate[b.block_date] = blocksByDate[b.block_date] || []).push(b);
    });
  }

  const schedByDay = {};
  if (calData) {
    (calData.schedule || []).forEach(s => {
      (schedByDay[s.day] = schedByDay[s.day] || []).push(s);
    });
  }

  const handleBlockSave = async (form) => {
    setBlockSaving(true);
    try {
      await window.meridianApi.call('medic_plus.api.calendar.create_time_block', {
        block_date: form.block_date,
        end_date: form.end_date || form.block_date,
        from_time: form.is_all_day ? null : form.from_time,
        to_time: form.is_all_day ? null : form.to_time,
        reason: form.reason,
        is_all_day: form.is_all_day ? 1 : 0,
      });
      setShowBlock(false);
      fetchWeek(weekStart);
    } catch (err) {
      window.meridianApi.showError(err.message || 'Could not create block.');
    } finally {
      setBlockSaving(false);
    }
  };

  const handleDeleteBlock = async (blockName) => {
    setDeletingBlock(blockName);
    try {
      await window.meridianApi.call('medic_plus.api.calendar.delete_time_block', { block_name: blockName });
      fetchWeek(weekStart);
    } catch (err) {
      window.meridianApi.showError(err.message || 'Could not remove block.');
    } finally {
      setDeletingBlock(null);
    }
  };

  const weekLabel = (() => {
    if (!weekStart) return '';
    const start = new Date(weekStart);
    const end = new Date(weekStart);
    end.setDate(end.getDate() + 6);
    return `${_fmtDate(_isoDate(start))} – ${_fmtDate(_isoDate(end))}`;
  })();

  return (
    <div className="page fade-in" data-testid="calendar-page">
      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.02em' }}>My Calendar</h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>
            {status === 'ready' && calData
              ? calData.practitioner_name || calData.practitioner
              : status === 'loading' ? 'Loading…' : ''}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => goWeek(-1)} aria-label="Previous week">← Prev</button>
          <button className="btn btn-secondary btn-sm" onClick={goToday}>Today</button>
          <button className="btn btn-secondary btn-sm" onClick={() => goWeek(1)} aria-label="Next week">Next →</button>
          {status === 'ready' && (
            <button className="btn btn-primary btn-sm" onClick={() => { setClickedDate(null); setShowBlock(true); }}>
              + Block Time
            </button>
          )}
        </div>
      </div>

      {/* week label */}
      <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>{weekLabel}</p>

      {/* ── States ── */}
      {status === 'no-practitioner' && (
        <NoPractitionerBanner />
      )}
      {status === 'error' && (
        <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* ── Calendar grid ── */}
      <div className="card" style={{ overflowX: 'auto' }}>
        {status === 'loading' && <CalSkeleton />}
        {status === 'ready' && (
          <div style={{ display: 'flex', minWidth: 680 }}>
            {/* Time gutter */}
            <div style={{ width: 50, flexShrink: 0, paddingTop: 52, boxSizing: 'border-box' }}>
              {HOURS.map(h => (
                <div key={h} style={{
                  height: HOUR_HEIGHT, boxSizing: 'border-box',
                  display: 'flex', alignItems: 'flex-start', paddingTop: 3,
                  paddingRight: 8, fontSize: 10.5, color: 'var(--text-muted)',
                  textAlign: 'right', userSelect: 'none',
                }}>
                  {String(h).padStart(2, '0')}:00
                </div>
              ))}
            </div>

            {/* Day columns */}
            {weekDays.map((day) => {
              const dateStr = _isoDate(day);
              const dayName = DAY_NAMES[day.getDay()];
              const isToday = dateStr === todayIso;
              const appts = apptsByDate[dateStr] || [];
              const blocks = blocksByDate[dateStr] || [];
              const schedSlots = schedByDay[dayName] || [];

              return (
                <div
                  key={dateStr}
                  style={{ flex: 1, minWidth: 0, borderLeft: '1px solid var(--border-color)' }}
                >
                  {/* Day header */}
                  <div style={{
                    height: 52, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    borderBottom: '1px solid var(--border-color)',
                    background: isToday ? 'var(--accent-soft, #eff6ff)' : 'transparent',
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                    onClick={() => { setClickedDate(dateStr); setShowBlock(true); }}
                    title={`Block time on ${dateStr}`}
                  >
                    <span style={{ fontSize: 10.5, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {DAY_SHORT[day.getDay()]}
                    </span>
                    <span style={{
                      fontSize: 18, fontWeight: isToday ? 700 : 500, lineHeight: 1.2,
                      color: isToday ? 'var(--accent, #2563eb)' : 'var(--text-color)',
                    }}>
                      {day.getDate()}
                    </span>
                  </div>

                  {/* Day body */}
                  <div style={{ position: 'relative', height: TOTAL_H }}>
                    {/* Hour lines */}
                    {HOURS.map((_, hi) => (
                      <div key={hi} style={{
                        position: 'absolute', top: hi * HOUR_HEIGHT, left: 0, right: 0,
                        height: 1, background: 'var(--border-color)', opacity: 0.5, pointerEvents: 'none',
                      }} />
                    ))}

                    {/* Half-hour lines */}
                    {HOURS.map((_, hi) => (
                      <div key={`h${hi}`} style={{
                        position: 'absolute', top: hi * HOUR_HEIGHT + HOUR_HEIGHT / 2,
                        left: 0, right: 0, height: 1,
                        background: 'var(--border-color)', opacity: 0.25, pointerEvents: 'none',
                      }} />
                    ))}

                    {/* Working-hours background */}
                    {schedSlots.map((s, si) => {
                      const topMin = _timeToMin(s.from_time) - CAL_START * 60;
                      const durMin = _timeToMin(s.to_time) - _timeToMin(s.from_time);
                      if (topMin < 0 || durMin <= 0) return null;
                      return (
                        <div key={si} style={{
                          position: 'absolute',
                          top: _minToPx(topMin), left: 0, right: 0,
                          height: _minToPx(durMin),
                          background: 'rgba(37,99,235,0.04)',
                          borderLeft: '2px solid rgba(37,99,235,0.18)',
                          pointerEvents: 'none',
                        }} />
                      );
                    })}

                    {/* Time blocks */}
                    {blocks.map(b => (
                      <BlockChip
                        key={b.name}
                        block={b}
                        onDelete={handleDeleteBlock}
                        deleting={deletingBlock === b.name}
                      />
                    ))}

                    {/* Appointments */}
                    {appts.map(a => (
                      <ApptChip key={a.name} appt={a} go={go} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Legend ── */}
      {status === 'ready' && (
        <div style={{ display: 'flex', gap: 20, marginTop: 10, fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 12, height: 12, borderRadius: 2, background: 'rgba(37,99,235,0.12)', border: '1px solid rgba(37,99,235,0.4)', display: 'inline-block' }} />
            Appointment
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 12, height: 12, borderRadius: 2, background: 'rgba(107,114,128,0.13)', border: '1px solid rgba(107,114,128,0.4)', display: 'inline-block' }} />
            Blocked
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 12, height: 12, borderRadius: 2, background: 'rgba(37,99,235,0.04)', borderLeft: '2px solid rgba(37,99,235,0.18)', display: 'inline-block' }} />
            Working hours (from schedule)
          </span>
          <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>
            Click any day header to block that day
          </span>
        </div>
      )}

      {/* ── Block-time modal ── */}
      {showBlock && (
        <BlockModal
          defaultDate={clickedDate || _isoDate(new Date())}
          saving={blockSaving}
          onClose={() => setShowBlock(false)}
          onSave={handleBlockSave}
        />
      )}
    </div>
  );
}

window.MCalendarScreen = MCalendarScreen;
