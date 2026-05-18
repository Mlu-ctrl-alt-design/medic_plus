// Two-step OTP login.

(function() {
  const { useState } = React;

  function PortalLoginScreen({ slug, onSignedIn }) {
    const [step, setStep] = useState("email"); // email | code
    const [email, setEmail] = useState("");
    const [code, setCode] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [info, setInfo] = useState("");

    async function sendCode(e) {
      e.preventDefault();
      setBusy(true); setError("");
      try {
        await window.portalApi.call("medic_plus.api.patient_portal.request_portal_otp", { slug, email });
        setInfo("If the email matches a patient record, we sent you a code.");
        setStep("code");
      } catch (err) {
        setError(err.message);
      } finally { setBusy(false); }
    }

    async function verifyCode(e) {
      e.preventDefault();
      setBusy(true); setError("");
      try {
        const res = await window.portalApi.call("medic_plus.api.patient_portal.verify_portal_otp", { slug, email, code });
        if (res && res.ok) {
          // Hard reload — easiest way to re-fetch boot context with a fresh session.
          window.location.href = `/portal/${slug}`;
          onSignedIn && onSignedIn();
        }
      } catch (err) {
        setError(err.message);
      } finally { setBusy(false); }
    }

    return (
      <div style={{maxWidth: 360, margin: "60px auto", padding: 24}}>
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 4}}>Patient Portal</h1>
        <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 24}}>
          Sign in with the email on file at your practice.
        </div>

        {step === "email" && (
          <form onSubmit={sendCode}>
            <label style={{display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6}}>Email address</label>
            <input
              type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
              className="portal-input" style={{marginBottom: 12}}
            />
            <button className="portal-cta" type="submit" disabled={busy} style={{width: "100%"}}>
              {busy ? "Sending…" : "Send code"}
            </button>
          </form>
        )}

        {step === "code" && (
          <form onSubmit={verifyCode}>
            <label style={{display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6}}>6-digit code</label>
            <input
              type="text" inputMode="numeric" pattern="[0-9]*" maxLength={6} required autoFocus
              value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="portal-input"
              style={{fontSize: 18, letterSpacing: "0.2em", textAlign: "center", marginBottom: 12}}
            />
            <button className="portal-cta" type="submit" disabled={busy || code.length !== 6} style={{width: "100%"}}>
              {busy ? "Verifying…" : "Sign in"}
            </button>
            <button type="button" onClick={() => { setStep("email"); setCode(""); setError(""); }}
              style={{display: "block", width: "100%", marginTop: 12, padding: 8, background: "transparent", border: 0, color: "var(--text-muted)", fontSize: 12, cursor: "pointer"}}>
              Use a different email
            </button>
          </form>
        )}

        {info && <div style={{marginTop: 16, padding: 12, background: "var(--bg-subtle, #f9fafb)", borderRadius: 8, fontSize: 12, color: "var(--text-muted)"}}>{info}</div>}
        {error && <div style={{marginTop: 16, padding: 12, background: "#fef2f2", borderRadius: 8, fontSize: 12, color: "#991b1b"}}>{error}</div>}
      </div>
    );
  }

  window.PortalLoginScreen = PortalLoginScreen;
})();
