// MDatePicker — branded date picker for the daystar-health portal.
//
// API mirrors the spirit of react-aria-components' <DatePicker>:
//   <window.MDatePicker
//     value="YYYY-MM-DD"           // string, "" when empty
//     onChange={(v) => ...}        // receives a string (NOT a synthetic event)
//     onBlur={() => ...}           // fires when the trigger input blurs
//     min="YYYY-MM-DD"             // optional lower bound (inclusive)
//     max="YYYY-MM-DD"             // optional upper bound (inclusive)
//     disabled={false}
//     placeholder="YYYY-MM-DD"
//     aria-label="..."             // forwarded to the input
//     data-testid="..."            // forwarded to the input
//     className="..."              // appended to the input class list
//     style={{...}}                // applied to the wrapper
//   />
//
// Why portal the popover to <body>: the patients page wraps its content in
// `.page.fade-in`, whose keyframes apply `transform: translateY(...)`. Any
// `position: absolute|fixed` descendant would be trapped in that ancestor's
// stacking context and could paint behind sibling cards (see register-patient
// drawer fix). Portalling avoids that class of bug entirely.

const { useState: dpUseState, useEffect: dpUseEffect, useRef: dpUseRef, useMemo: dpUseMemo } = React;

const DP_WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];  // ISO week (Mon-first)
const DP_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function dpPad(n) { return n < 10 ? `0${n}` : `${n}`; }
function dpToISO(y, m, d) { return `${y}-${dpPad(m)}-${dpPad(d)}`; }
function dpParse(value) {
  if (!value || !DP_DATE_RE.test(value)) return null;
  const [y, m, d] = value.split("-").map(Number);
  // Validate with a real Date to catch e.g. 2026-02-30.
  const date = new Date(y, m - 1, d);
  if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d) return null;
  return { y, m, d };
}
function dpDaysInMonth(y, m) { return new Date(y, m, 0).getDate(); }
// Monday = 0 ... Sunday = 6. JS getDay is Sun=0 ... Sat=6.
function dpWeekdayMonFirst(y, m, d) { return (new Date(y, m - 1, d).getDay() + 6) % 7; }

function dpFormatDisplay(value) {
  const parts = dpParse(value);
  if (!parts) return "";
  try {
    return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "2-digit" })
      .format(new Date(parts.y, parts.m - 1, parts.d));
  } catch (e) {
    return value;
  }
}

function dpClampToBounds(parts, min, max) {
  if (!parts) return null;
  const iso = dpToISO(parts.y, parts.m, parts.d);
  if (min && iso < min) return dpParse(min);
  if (max && iso > max) return dpParse(max);
  return parts;
}

function MDatePicker(props) {
  const {
    value, onChange, onBlur,
    min, max, disabled,
    placeholder = "YYYY-MM-DD",
    className, style,
    ...rest
  } = props;

  const [text, setText] = dpUseState(value || "");
  const [open, setOpen] = dpUseState(false);
  const [popoverRect, setPopoverRect] = dpUseState({ top: 0, left: 0, width: 280 });

  // viewMonth is the calendar's cursor — what month grid we render.
  const initialView = dpUseMemo(() => {
    const p = dpParse(value) || dpParse(min) || dpParse(max);
    if (p) return { y: p.y, m: p.m };
    const now = new Date();
    return { y: now.getFullYear(), m: now.getMonth() + 1 };
  }, []);
  const [view, setView] = dpUseState(initialView);

  const wrapperRef = dpUseRef(null);
  const inputRef = dpUseRef(null);
  const popoverRef = dpUseRef(null);

  // Sync external value → local text. Skip while user is typing (input focused)
  // so we don't clobber in-progress edits.
  dpUseEffect(() => {
    if (document.activeElement !== inputRef.current) {
      setText(value || "");
    }
  }, [value]);

  // Position popover under the input each time it opens / on viewport change.
  const reposition = () => {
    const el = wrapperRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.max(rect.width, 280);
    const popH = 320;  // approx; we re-fit below
    let top = rect.bottom + 6;
    if (top + popH > window.innerHeight && rect.top - 6 - popH > 0) {
      top = rect.top - 6 - popH;  // flip above
    }
    let left = rect.left;
    if (left + width > window.innerWidth - 8) left = window.innerWidth - 8 - width;
    if (left < 8) left = 8;
    setPopoverRect({ top: top + window.scrollY, left: left + window.scrollX, width });
  };

  dpUseEffect(() => {
    if (!open) return;
    reposition();
    const onScrollOrResize = () => reposition();
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open]);

  // Close on outside click / Escape.
  dpUseEffect(() => {
    if (!open) return;
    const onDocDown = (e) => {
      if (wrapperRef.current?.contains(e.target)) return;
      if (popoverRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") {
        setOpen(false);
        inputRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDocDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const openWith = () => {
    if (disabled) return;
    const parts = dpParse(text || value);
    if (parts) setView({ y: parts.y, m: parts.m });
    setOpen(true);
  };

  const commit = (iso) => {
    setText(iso);
    onChange && onChange(iso);
  };

  const onInputChange = (e) => {
    const raw = e.target.value;
    setText(raw);
    // Only propagate well-formed values upstream. Garbage stays local until
    // blur, which lets the user finish typing.
    if (raw === "") {
      onChange && onChange("");
    } else if (DP_DATE_RE.test(raw) && dpParse(raw)) {
      onChange && onChange(raw);
    }
  };

  const onInputBlur = (e) => {
    // If text is unparseable, snap back to the canonical value.
    const parsed = dpParse(text);
    if (!parsed && text !== "") {
      setText(value || "");
    }
    onBlur && onBlur(e);
  };

  const pickDay = (y, m, d) => {
    const iso = dpToISO(y, m, d);
    if ((min && iso < min) || (max && iso > max)) return;
    commit(iso);
    setOpen(false);
    inputRef.current?.focus();
  };

  const stepMonth = (delta) => {
    let { y, m } = view;
    m += delta;
    while (m < 1) { m += 12; y -= 1; }
    while (m > 12) { m -= 12; y += 1; }
    setView({ y, m });
  };

  const today = new Date();
  const todayISO = dpToISO(today.getFullYear(), today.getMonth() + 1, today.getDate());
  const selected = dpParse(value);

  // Build the day grid: 6 weeks × 7 days, leading blanks before day 1.
  const grid = dpUseMemo(() => {
    const lead = dpWeekdayMonFirst(view.y, view.m, 1);
    const days = dpDaysInMonth(view.y, view.m);
    const cells = [];
    for (let i = 0; i < lead; i++) cells.push(null);
    for (let d = 1; d <= days; d++) cells.push(d);
    while (cells.length % 7 !== 0) cells.push(null);
    while (cells.length < 42) cells.push(null);  // always render 6 rows
    return cells;
  }, [view.y, view.m]);

  const monthLabel = dpUseMemo(() => {
    try {
      return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "long" })
        .format(new Date(view.y, view.m - 1, 1));
    } catch (e) {
      return `${view.y}-${dpPad(view.m)}`;
    }
  }, [view.y, view.m]);

  const popover = open ? ReactDOM.createPortal(
    <div
      ref={popoverRef}
      className="mdp-popover"
      role="dialog"
      aria-label="Choose date"
      style={{ top: popoverRect.top, left: popoverRect.left, width: popoverRect.width }}
    >
      <div className="mdp-header">
        <button type="button" className="mdp-nav" aria-label="Previous month" onClick={() => stepMonth(-1)}>
          <window.MIcons.ChevronLeft size={14} />
        </button>
        <div className="mdp-month-label" data-testid="mdp-month-label">{monthLabel}</div>
        <button type="button" className="mdp-nav" aria-label="Next month" onClick={() => stepMonth(1)}>
          <window.MIcons.ChevronRight size={14} />
        </button>
      </div>

      <div className="mdp-weekdays">
        {DP_WEEKDAYS.map((w) => <div key={w}>{w}</div>)}
      </div>

      <div className="mdp-grid" role="grid">
        {grid.map((d, i) => {
          if (d == null) return <div key={i} className="mdp-cell mdp-cell-empty" />;
          const iso = dpToISO(view.y, view.m, d);
          const isSelected = selected && selected.y === view.y && selected.m === view.m && selected.d === d;
          const isToday = iso === todayISO;
          const outOfRange = (min && iso < min) || (max && iso > max);
          let cls = "mdp-cell";
          if (isSelected) cls += " mdp-cell-selected";
          if (isToday && !isSelected) cls += " mdp-cell-today";
          if (outOfRange) cls += " mdp-cell-disabled";
          return (
            <button
              key={i}
              type="button"
              role="gridcell"
              aria-selected={isSelected || undefined}
              aria-disabled={outOfRange || undefined}
              className={cls}
              disabled={outOfRange}
              onClick={() => pickDay(view.y, view.m, d)}
              data-testid={isSelected ? "mdp-day-selected" : undefined}
              data-iso={iso}
            >
              {d}
            </button>
          );
        })}
      </div>

      <div className="mdp-footer">
        <button
          type="button"
          className="mdp-foot-btn"
          onClick={() => {
            const t = dpClampToBounds(dpParse(todayISO), min, max);
            if (!t) return;
            const iso = dpToISO(t.y, t.m, t.d);
            setView({ y: t.y, m: t.m });
            commit(iso);
            setOpen(false);
            inputRef.current?.focus();
          }}
        >
          Today
        </button>
        <button
          type="button"
          className="mdp-foot-btn"
          onClick={() => {
            commit("");
            setOpen(false);
            inputRef.current?.focus();
          }}
        >
          Clear
        </button>
      </div>
    </div>,
    document.body
  ) : null;

  return (
    <div className={`mdp${disabled ? " mdp-disabled" : ""}`} ref={wrapperRef} style={style}>
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        pattern="\d{4}-\d{2}-\d{2}"
        autoComplete="off"
        spellCheck={false}
        className={`input mdp-input ${className || ""}`}
        placeholder={placeholder}
        value={text}
        onChange={onInputChange}
        onBlur={onInputBlur}
        onFocus={() => { /* don't auto-open on focus — typists don't want it */ }}
        onClick={() => { if (!open) openWith(); }}
        onKeyDown={(e) => { if (e.key === "ArrowDown" && !open) { e.preventDefault(); openWith(); } }}
        disabled={disabled}
        {...rest}
      />
      <button
        type="button"
        className="mdp-icon-btn"
        aria-label="Open calendar"
        tabIndex={-1}
        onClick={() => (open ? setOpen(false) : openWith())}
        disabled={disabled}
      >
        <window.MIcons.Calendar size={15} />
      </button>
      {popover}
    </div>
  );
}

window.MDatePicker = MDatePicker;
