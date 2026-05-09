// MTextArea — branded textarea for the daystar-health portal.
//
//   <window.MTextArea
//     value={form.hopi}
//     onChange={(v) => update('hopi', v)}    // receives string, NOT an event
//     onBlur={() => ...}
//     label="Description"
//     hint="This is a hint text to help the user."
//     isRequired={false}
//     placeholder="..."
//     rows={3}
//     disabled={false}
//     autoFocus={false}
//     aria-label="..."
//     data-testid="..."
//     className="..."             // appended to the textarea class list
//     style={{...}}                // applied to the wrapper
//   />
//
// Visual style matches the branded MDatePicker / MTimePicker: same border,
// focus ring, label typography. Resizes vertically by default. No
// auto-resize (use a fixed `rows` count). Hint text gets `aria-describedby`
// so screen readers announce it after the label.

const { useId: taUseId } = React;

let _taIdCounter = 0;
function taFallbackId() {
  _taIdCounter += 1;
  return `mta-${_taIdCounter}`;
}

function MTextArea(props) {
  const {
    value, onChange, onBlur,
    label, hint, isRequired,
    placeholder = "",
    rows = 3,
    disabled, autoFocus,
    id: idProp,
    className, style,
    ...rest
  } = props;

  // useId is React 18+; fall back for safety in case of older react bundles.
  const generatedId = (taUseId ? taUseId() : null) || React.useMemo(() => taFallbackId(), []);
  const id = idProp || `mta-${generatedId}`;
  const hintId = hint ? `${id}-hint` : undefined;

  const userAriaDescribedBy = rest["aria-describedby"];
  const ariaDescribedBy = [hintId, userAriaDescribedBy].filter(Boolean).join(" ") || undefined;

  const handleChange = (e) => {
    if (onChange) onChange(e.target.value);
  };

  return (
    <div className={`mta${disabled ? " mta-disabled" : ""}`} style={style}>
      {label && (
        <label className="mta-label" htmlFor={id}>
          {label}
          {isRequired && <span className="mta-required" aria-hidden="true">*</span>}
        </label>
      )}
      <textarea
        id={id}
        className={`mta-input ${className || ""}`}
        rows={rows}
        placeholder={placeholder}
        value={value ?? ""}
        onChange={handleChange}
        onBlur={onBlur}
        disabled={disabled}
        autoFocus={autoFocus}
        aria-required={isRequired || undefined}
        {...rest}
        aria-describedby={ariaDescribedBy}
      />
      {hint && <div id={hintId} className="mta-hint">{hint}</div>}
    </div>
  );
}

window.MTextArea = MTextArea;
