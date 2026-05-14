// MTimePicker — branded 24-hour time picker for the daystar-health portal.
//
//   <window.MTimePicker
//     value="HH:MM"                // 24-hour, "" when empty
//     onChange={(v) => ...}        // receives string, NOT an event
//     onBlur={() => ...}
//     step={15}                    // minute granularity in the popover (default 15)
//     disabled={false}
//     placeholder="HH:MM"
//     aria-label="..."
//     data-testid="..."
//     className="..."              // appended to the input class list
//     style={{...}}                // applied to the wrapper
//   />
//
// Popover portal'd to <body> for the same stacking-context reason as MDatePicker.

const { useState: tpUseState, useEffect: tpUseEffect, useRef: tpUseRef, useMemo: tpUseMemo } = React;

const TP_TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

function tpPad(n) { return n < 10 ? `0${n}` : `${n}`; }
function tpParse(value) {
  if (!value || !TP_TIME_RE.test(value)) return null;
  const [h, m] = value.split(":").map(Number);
  return { h, m };
}

function MTimePicker(props) {
  const {
    value, onChange, onBlur,
    step = 15,
    disabled,
    placeholder = "HH:MM",
    className, style,
    ...rest
  } = props;

  const [text, setText] = tpUseState(value || "");
  const [open, setOpen] = tpUseState(false);
  const [popoverRect, setPopoverRect] = tpUseState({ top: 0, left: 0, width: 220 });

  const wrapperRef = tpUseRef(null);
  const inputRef = tpUseRef(null);
  const popoverRef = tpUseRef(null);
  const hourColRef = tpUseRef(null);
  const minuteColRef = tpUseRef(null);

  tpUseEffect(() => {
    if (document.activeElement !== inputRef.current) {
      setText(value || "");
    }
  }, [value]);

  const minutes = tpUseMemo(() => {
    const out = [];
    for (let m = 0; m < 60; m += step) out.push(m);
    return out;
  }, [step]);

  const hours = tpUseMemo(() => {
    const out = [];
    for (let h = 0; h < 24; h++) out.push(h);
    return out;
  }, []);

  const reposition = () => {
    const el = wrapperRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.max(rect.width, 220);
    const popH = 280;
    let top = rect.bottom + 6;
    if (top + popH > window.innerHeight && rect.top - 6 - popH > 0) {
      top = rect.top - 6 - popH;
    }
    let left = rect.left;
    if (left + width > window.innerWidth - 8) left = window.innerWidth - 8 - width;
    if (left < 8) left = 8;
    setPopoverRect({ top: top + window.scrollY, left: left + window.scrollX, width });
  };

  tpUseEffect(() => {
    if (!open) return;
    reposition();
    // Scroll selected hour/minute into view.
    setTimeout(() => {
      const parts = tpParse(text || value);
      if (!parts) return;
      const h = hourColRef.current?.querySelector(`[data-h="${parts.h}"]`);
      const m = minuteColRef.current?.querySelector(`[data-m="${parts.m}"]`);
      h && h.scrollIntoView && h.scrollIntoView({ block: "center" });
      m && m.scrollIntoView && m.scrollIntoView({ block: "center" });
    }, 0);
    const onScrollOrResize = () => reposition();
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open]);

  tpUseEffect(() => {
    if (!open) return;
    const onDocDown = (e) => {
      if (wrapperRef.current?.contains(e.target)) return;
      if (popoverRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
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

  const commit = (hh, mm) => {
    const iso = `${tpPad(hh)}:${tpPad(mm)}`;
    setText(iso);
    onChange && onChange(iso);
  };

  const pickHour = (h) => {
    const parts = tpParse(text || value);
    const m = parts ? parts.m : 0;
    commit(h, m);
  };
  const pickMinute = (m) => {
    const parts = tpParse(text || value);
    const h = parts ? parts.h : new Date().getHours();
    commit(h, m);
    setOpen(false);
    inputRef.current?.focus();
  };

  const onInputChange = (e) => {
    const raw = e.target.value;
    setText(raw);
    if (raw === "") onChange && onChange("");
    else if (TP_TIME_RE.test(raw)) onChange && onChange(raw);
  };

  const onInputBlur = (e) => {
    const parsed = tpParse(text);
    if (!parsed && text !== "") setText(value || "");
    onBlur && onBlur(e);
  };

  const openIfClosed = () => {
    if (disabled) return;
    if (!open) setOpen(true);
  };

  const current = tpParse(text || value);

  const popover = open ? ReactDOM.createPortal(
    <div
      ref={popoverRef}
      className="mtp-popover"
      role="dialog"
      aria-label="Choose time"
      style={{ top: popoverRect.top, left: popoverRect.left, width: popoverRect.width }}
    >
      <div className="mtp-cols">
        <div className="mtp-col" ref={hourColRef} role="listbox" aria-label="Hour">
          {hours.map((h) => {
            const isSel = current && current.h === h;
            return (
              <button
                key={h}
                type="button"
                role="option"
                aria-selected={isSel || undefined}
                data-h={h}
                className={`mtp-cell${isSel ? " mtp-cell-selected" : ""}`}
                onClick={() => pickHour(h)}
              >
                {tpPad(h)}
              </button>
            );
          })}
        </div>
        <div className="mtp-col" ref={minuteColRef} role="listbox" aria-label="Minute">
          {minutes.map((m) => {
            const isSel = current && current.m === m;
            return (
              <button
                key={m}
                type="button"
                role="option"
                aria-selected={isSel || undefined}
                data-m={m}
                className={`mtp-cell${isSel ? " mtp-cell-selected" : ""}`}
                onClick={() => pickMinute(m)}
              >
                {tpPad(m)}
              </button>
            );
          })}
        </div>
      </div>
      <div className="mtp-footer">
        <button
          type="button"
          className="mdp-foot-btn"
          onClick={() => {
            const now = new Date();
            const h = now.getHours();
            const m = Math.round(now.getMinutes() / step) * step;
            commit(h, m % 60 === 60 ? 0 : m);
            setOpen(false);
            inputRef.current?.focus();
          }}
        >
          Now
        </button>
        <button
          type="button"
          className="mdp-foot-btn"
          onClick={() => {
            setText("");
            onChange && onChange("");
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
    <div className={`mtp${disabled ? " mtp-disabled" : ""}`} ref={wrapperRef} style={style}>
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        pattern="\d{2}:\d{2}"
        autoComplete="off"
        spellCheck={false}
        className={`input mtp-input ${className || ""}`}
        placeholder={placeholder}
        value={text}
        onChange={onInputChange}
        onBlur={onInputBlur}
        onClick={() => { if (!open) openIfClosed(); }}
        onKeyDown={(e) => { if (e.key === "ArrowDown" && !open) { e.preventDefault(); openIfClosed(); } }}
        disabled={disabled}
        {...rest}
      />
      <button
        type="button"
        className="mtp-icon-btn"
        aria-label="Open clock"
        tabIndex={-1}
        onClick={() => (open ? setOpen(false) : openIfClosed())}
        disabled={disabled}
      >
        <window.MIcons.Clock size={15} />
      </button>
      {popover}
    </div>
  );
}

window.MTimePicker = MTimePicker;
