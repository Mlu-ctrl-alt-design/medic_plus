// Daystar Health — "What's New" release notes modal.
//
// Rendered by App() when medic_plus.api.release_notes.get_unseen_release_notes
// returns one or more published Release Note records the user has not yet
// acknowledged. Dismissal is recorded server-side so the modal does not
// reappear on the next login.

function MReleaseNotesModal({ notes, onClose }) {
  const { useState, useEffect } = React;
  const [closing, setClosing] = useState(false);

  // Lock background scroll while the modal is open.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  if (!notes || notes.length === 0) return null;

  const handleClose = async () => {
    if (closing) return;
    setClosing(true);
    try {
      await window.meridianApi.call(
        "medic_plus.api.release_notes.mark_release_notes_seen"
      );
    } catch (e) {
      // Non-fatal: if the acknowledgement fails the modal simply reappears
      // on the next login. Don't block the user from dismissing it.
      console.error("[release-notes] mark seen failed", e);
    }
    onClose();
  };

  const overlay = {
    position: "fixed",
    inset: 0,
    background: "rgba(15, 23, 42, 0.55)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 20,
    zIndex: 1000,
  };
  const modal = {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-lg)",
    boxShadow: "var(--shadow-lg)",
    width: "100%",
    maxWidth: 520,
    maxHeight: "85vh",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  };

  return (
    <div style={overlay} onClick={handleClose} data-testid="release-notes-overlay">
      <div
        style={modal}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="What's new"
        data-testid="release-notes-modal"
      >
        <div style={{ padding: "24px 24px 16px", borderBottom: "1px solid var(--border)" }}>
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--accent-text)",
              marginBottom: 6,
            }}
          >
            What's New
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--text)" }}>
            Latest updates to Daystar Health
          </div>
        </div>

        <div style={{ padding: "8px 24px", overflowY: "auto" }}>
          {notes.map((note) => (
            <div
              key={note.name}
              data-testid="release-notes-entry"
              style={{ padding: "16px 0", borderBottom: "1px solid var(--border)" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span
                  data-testid="release-notes-title"
                  style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}
                >
                  {note.title}
                </span>
                {note.version ? (
                  <span
                    data-testid="release-notes-version"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      fontFamily: "var(--font-mono)",
                      color: "var(--text-dim)",
                      background: "var(--bg-subtle)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      padding: "2px 7px",
                    }}
                  >
                    {note.version}
                  </span>
                ) : null}
              </div>
              {note.published_on ? (
                <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 8 }}>
                  {note.published_on}
                </div>
              ) : null}
              <div
                className="rn-content"
                data-testid="release-notes-body"
                style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.6 }}
                dangerouslySetInnerHTML={{ __html: note.body || "" }}
              />
            </div>
          ))}
        </div>

        <div
          style={{
            padding: "16px 24px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            justifyContent: "flex-end",
          }}
        >
          <button
            className="btn btn-primary"
            onClick={handleClose}
            disabled={closing}
            data-testid="release-notes-dismiss"
          >
            {closing ? "Saving…" : "Got it"}
          </button>
        </div>
      </div>
    </div>
  );
}

window.MReleaseNotesModal = MReleaseNotesModal;
