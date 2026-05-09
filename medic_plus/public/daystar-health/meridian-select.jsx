// MSelect — branded dropdown listbox for the daystar-health portal.
//
//   <window.MSelect
//     value="..."                       // current value (string)
//     onChange={(v) => ...}             // receives the new value, NOT an event
//     options={[{ value, label }, ...]}  // option list
//     placeholder="Select…"             // shown when value is empty
//     searchable={false}                // adds a filter input in the popover
//     disabled={false}
//     aria-label="..."
//     data-testid="..."                 // forwarded to the trigger button
//     className="..."                   // appended to the trigger class list
//     style={{...}}                     // applied to the wrapper
//   />
//
// Popover is portal'd to <body> to avoid stacking-context traps from animated
// ancestors (see register-patient drawer fix).

const { useState: msUseState, useEffect: msUseEffect, useRef: msUseRef, useMemo: msUseMemo } = React;

function MSelect(props) {
  const {
    value, onChange, options = [],
    placeholder = "Select…",
    searchable = false,
    disabled,
    className, style,
    ...rest
  } = props;

  const [open, setOpen] = msUseState(false);
  const [filter, setFilter] = msUseState("");
  const [highlight, setHighlight] = msUseState(0);
  const [popoverRect, setPopoverRect] = msUseState({ top: 0, left: 0, width: 280 });

  const wrapperRef = msUseRef(null);
  const triggerRef = msUseRef(null);
  const popoverRef = msUseRef(null);
  const searchRef = msUseRef(null);
  const itemRefs = msUseRef([]);

  const visibleOptions = msUseMemo(() => {
    if (!searchable || !filter.trim()) return options;
    const f = filter.trim().toLowerCase();
    return options.filter(o => (o.label || o.value || "").toLowerCase().includes(f));
  }, [options, filter, searchable]);

  const selected = msUseMemo(() => options.find(o => o.value === value), [options, value]);

  const reposition = () => {
    const el = wrapperRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.max(rect.width, 220);
    const popH = Math.min(360, 60 + visibleOptions.length * 32);
    let top = rect.bottom + 6;
    if (top + popH > window.innerHeight && rect.top - 6 - popH > 0) {
      top = rect.top - 6 - popH;
    }
    let left = rect.left;
    if (left + width > window.innerWidth - 8) left = window.innerWidth - 8 - width;
    if (left < 8) left = 8;
    setPopoverRect({ top: top + window.scrollY, left: left + window.scrollX, width });
  };

  msUseEffect(() => {
    if (!open) return;
    reposition();
    // Set highlight to selected option (or first visible)
    const idx = Math.max(0, visibleOptions.findIndex(o => o.value === value));
    setHighlight(idx === -1 ? 0 : idx);
    if (searchable) {
      // Defer focus so the popover is mounted.
      setTimeout(() => searchRef.current?.focus(), 0);
    }
    const onScrollOrResize = () => reposition();
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open]);

  msUseEffect(() => {
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
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDocDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Keep highlighted item in view while arrowing.
  msUseEffect(() => {
    if (!open) return;
    const node = itemRefs.current[highlight];
    if (node && node.scrollIntoView) node.scrollIntoView({ block: "nearest" });
  }, [highlight, open]);

  // Reset filter and highlight when popover closes.
  msUseEffect(() => {
    if (!open) {
      setFilter("");
      setHighlight(0);
    }
  }, [open]);

  const openIfClosed = () => {
    if (disabled) return;
    if (!open) setOpen(true);
  };

  const commit = (opt) => {
    onChange && onChange(opt.value);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const onTriggerKey = (e) => {
    if (disabled) return;
    if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
      e.preventDefault();
      openIfClosed();
    }
  };

  const onListKey = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight(h => Math.min(visibleOptions.length - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight(h => Math.max(0, h - 1));
    } else if (e.key === "Home") {
      e.preventDefault();
      setHighlight(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setHighlight(visibleOptions.length - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const opt = visibleOptions[highlight];
      if (opt) commit(opt);
    }
  };

  const popover = open ? ReactDOM.createPortal(
    <div
      ref={popoverRef}
      className="msel-popover"
      role="listbox"
      style={{ top: popoverRect.top, left: popoverRect.left, width: popoverRect.width }}
      onKeyDown={onListKey}
    >
      {searchable && (
        <div className="msel-search">
          <input
            ref={searchRef}
            className="input"
            type="text"
            aria-label="Filter options"
            placeholder="Search…"
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setHighlight(0); }}
            onKeyDown={onListKey}
            data-testid="msel-search"
          />
        </div>
      )}
      <div className="msel-list" role="presentation">
        {visibleOptions.length === 0 && (
          <div className="msel-empty">No matches</div>
        )}
        {visibleOptions.map((opt, i) => {
          const isSelected = opt.value === value;
          const isHighlight = i === highlight;
          let cls = "msel-item";
          if (isSelected) cls += " msel-item-selected";
          if (isHighlight) cls += " msel-item-highlight";
          return (
            <button
              key={opt.value || `__${i}`}
              ref={(el) => (itemRefs.current[i] = el)}
              type="button"
              role="option"
              aria-selected={isSelected || undefined}
              className={cls}
              onMouseEnter={() => setHighlight(i)}
              onClick={() => commit(opt)}
              data-testid={isSelected ? "msel-item-selected" : undefined}
            >
              <span className="msel-item-label">{opt.label != null ? opt.label : opt.value}</span>
              {isSelected && <span className="msel-item-check">✓</span>}
            </button>
          );
        })}
      </div>
    </div>,
    document.body
  ) : null;

  const displayLabel = selected ? (selected.label != null ? selected.label : selected.value) : "";

  return (
    <div
      className={`msel${disabled ? " msel-disabled" : ""}`}
      ref={wrapperRef}
      style={style}
    >
      <button
        ref={triggerRef}
        type="button"
        className={`input msel-trigger ${className || ""}`}
        onClick={() => (open ? setOpen(false) : openIfClosed())}
        onKeyDown={onTriggerKey}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        {...rest}
      >
        <span className={`msel-value${displayLabel ? "" : " msel-placeholder"}`}>
          {displayLabel || placeholder}
        </span>
        <span className="msel-chevron" aria-hidden>
          <window.MIcons.ChevronDown size={14} />
        </span>
      </button>
      {popover}
    </div>
  );
}

window.MSelect = MSelect;
