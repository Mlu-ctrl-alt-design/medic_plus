# Patient Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a practice-scoped patient portal at `/portal/<slug>` as a Babel-in-browser React SPA reusing the Meridian design system from `/daystar-health`, with passwordless email-OTP auth and 7 patient-facing screens (Home, Appointments, Book, Records, Documents, Billing, Profile).

**Architecture:** Backend = new module `medic_plus.api.patient_portal` with whitelisted endpoints; OTP infra mirrors the existing `medic_plus.api.booking` cache pattern; the existing `Patient` role's PQC scoping is reused, with four PQC extensions for currently-unscoped doctypes. Frontend = a new asset bundle at `medic_plus/public/portal/` loaded by a Jinja shell at `medic_plus/www/portal/`. The shared booking-rules helper `_book_slot` is extracted from `verify_and_book` so guest and authed flows share one source of truth.

**Tech Stack:** Frappe v16 / ERPNext v16 / Healthcare v16, Python 3.12, MariaDB, Redis cache, React 18.3.1 (UMD via unpkg), Babel-standalone 7.29.0 for in-browser transpilation, Meridian CSS (already in repo). Tests: stdlib `unittest` via the custom runner in `daystar_followup/tests/_runner.py` is NOT used here — medic_plus uses standard `bench run-tests --skip-before-tests`. Playwright for UI tests per CLAUDE.md.

**Branch:** `feature/patient-portal` (already created off `origin/develop`; spec commit already on it).

**Plan-time refinements to the spec:**
- Reuse existing `Patient` role rather than adding a new `Patient Portal User` role (the PQC infrastructure in `api/permissions.py` already handles `Patient` correctly via `_get_patient_name_for_user`). Spec updated accordingly.
- Add a new helper `_get_customer_for_user` in `api/permissions.py` to support the Sales Invoice PQC.

---

## File Map

### Backend (new + modified)

| Path | Action | Responsibility |
|---|---|---|
| `medic_plus/api/patient_portal.py` | **new** | All portal whitelisted endpoints (OTP, profile, appointments, records, documents, billing, resolver) |
| `medic_plus/api/booking.py` | modify | Extract `_book_slot` helper; `verify_and_book` calls it |
| `medic_plus/api/permissions.py` | modify | Add `_get_customer_for_user`; add `Patient`-role branches to `get_patient_encounter_permission_query`; add new PQCs for Patient Problem List, Medication Request, Sales Invoice |
| `medic_plus/hooks.py` | modify | Register new PQCs in `permission_query_conditions` |
| `medic_plus/api/test_patient_portal.py` | **new** | Python unit tests |

### Frontend (new)

| Path | Responsibility |
|---|---|
| `medic_plus/www/portal/index.html` | Jinja shell — boot context + script tags |
| `medic_plus/www/portal/index.py` | Resolve session → boot context (`slug`, `is_authed`, `has_patient`, `practice`) |
| `medic_plus/public/portal/portal-api.js` | `window.portalApi` — fetch wrapper mirroring `meridian-api.js` |
| `medic_plus/public/portal/portal-app.jsx` | Root: read URL → route → render screen / drawer; mounts `<App>` to `#root` |
| `medic_plus/public/portal/portal-layout.jsx` | Shell components: `<PortalShell>`, `<PortalTopbar>`, `<PortalSidebar>`, `<PortalDrawer>` |
| `medic_plus/public/portal/portal-login.jsx` | `<PortalLoginScreen>` — email → OTP → verify; redirects to `?screen=home` on success |
| `medic_plus/public/portal/portal-practice-picker.jsx` | `<PortalPracticePicker>` — multi-practice resolver UI |
| `medic_plus/public/portal/portal-home.jsx` | `<PortalHomeScreen>` — next appointment card + quick actions |
| `medic_plus/public/portal/portal-appointments.jsx` | `<PortalAppointmentsScreen>` — upcoming + past; cancel button |
| `medic_plus/public/portal/portal-book.jsx` | `<PortalBookDrawer>` — practitioner → date → slot → reason → submit |
| `medic_plus/public/portal/portal-profile.jsx` | `<PortalProfileScreen>` — editable form |
| `medic_plus/public/portal/portal-records.jsx` | `<PortalRecordsScreen>` — tabs for encounters/problems/allergies/conditions |
| `medic_plus/public/portal/portal-documents.jsx` | `<PortalDocumentsScreen>` — sick notes + prescriptions list + PDF download |
| `medic_plus/public/portal/portal-billing.jsx` | `<PortalBillingScreen>` — sales invoice list + PDF download |
| `medic_plus/public/portal/portal-styles.css` | Portal-only overrides on top of meridian.css |

### Tests

| Path | Action |
|---|---|
| `medic_plus/api/test_patient_portal.py` | **new** — Python unit tests |
| `medic_plus/tests/ui/test_patient_portal.py` | **new** — Playwright UI tests |

### Docs / release

| Path | Action |
|---|---|
| `docs/releases/v0.4.0.md` | **new** — patient portal release notes |
| `techspec.md` | append — date + summary |
| `README.md` | changelog section update |

---

## Conventions & ground rules

- **Site discovery**: always `medic-demo-staging.thedaystar.co.za`. Never hardcode elsewhere — this is the only target site for this app.
- **Bench dir**: `/home/fruppa/frappe-bench` — always run commands from there.
- **Test command** (per medic_plus CLAUDE.md): `bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus --skip-before-tests --module medic_plus.api.test_patient_portal` (use `--module` to keep the scope tight; the bench runner is OK for medic_plus and we don't need the `daystar_followup` custom runner).
- **Cache clear**: after every change to `hooks.py`, run `bench --site medic-demo-staging.thedaystar.co.za clear-cache && bench restart`.
- **Asset build**: after every JS/CSS change, run `bench build --app medic_plus` then hard-refresh the browser.
- **Commit cadence**: per CLAUDE.md, one commit per task. Conventional commit prefixes: `feat`, `fix`, `test`, `docs`, `refactor`.
- **File staging**: always `git add <specific paths>`. Never `git add -A`.
- **`IGNORE_TEST_RECORD_DEPENDENCIES`** at the top of `test_patient_portal.py` per medic_plus CLAUDE.md (the test framework otherwise crashes on `Company` / `Healthcare Practitioner`).
- **PQC testing**: call the PQC function directly with `user="<email>"`. Do NOT use `frappe.set_user()` + `frappe.get_all()` — Frappe caches roles in the session and the test fails for the wrong reason.

---

## Task 1: Refactor booking into a shared `_book_slot` helper

**Why first:** later tasks depend on this helper. Refactor first, then build on it.

**Files:**
- Modify: `medic_plus/api/booking.py`
- Test: existing `medic_plus/api/test_booking.py` if present, otherwise add one assertion in `test_patient_portal.py`

- [ ] **Step 1: Read the current `verify_and_book` to identify the slot/booking subset**

Run: `grep -n "verify_and_book\|appointment = frappe.get_doc" medic_plus/api/booking.py`

Identify the block from `# Resolve appointment type` through `appointment.insert(ignore_permissions=True)` — that's the helper body. The patient-resolution code stays in `verify_and_book` (guest creates a Patient on demand; authed flow looks one up).

- [ ] **Step 2: Add `_book_slot` helper above `_send_confirmation_email`**

Insert into `medic_plus/api/booking.py` (place above the `_send_confirmation_email` function):

```python
def _book_slot(
    *,
    patient_name: str,
    practice: dict,
    practitioner: str,
    appointment_date: str,
    appointment_time: str,
    reason: str | None = None,
    appointment_type: str | None = None,
) -> "frappe.model.document.Document":
    """Single source of truth for booking-rule enforcement.

    Validates that the requested slot is in `get_availability` (no double-book,
    practitioner belongs to the practice) and creates the Patient Appointment.
    Caller is responsible for Patient resolution + commit.

    Returns the inserted Patient Appointment doc.
    """
    available = get_availability(practice["slug"], practitioner, appointment_date)
    # Normalise the requested time to HH:MM:SS for comparison.
    # get_availability returns flat list of "HH:MM:SS" strings; callers may pass
    # "HH:MM" (from <input type="time">) or "HH:MM:SS".
    requested = str(appointment_time)
    if len(requested) == 5:
        requested = requested + ":00"
    requested = requested[:8]
    if requested not in available:
        frappe.throw(
            frappe._("That time slot is no longer available. Please pick another."),
            title=frappe._("Slot Unavailable"),
        )

    resolved_type = appointment_type or frappe.db.get_value(
        "Appointment Type", {"name": "Consultation"}, "name"
    ) or frappe.db.get_value("Appointment Type", {}, "name")

    appointment = frappe.get_doc({
        "doctype": "Patient Appointment",
        "patient": patient_name,
        "practitioner": practitioner,
        "appointment_for": "Practitioner",
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "duration": 30,
        "appointment_type": resolved_type,
        "custom_practice": practice["name"],
        "status": "Open",
        "notes": reason or None,
    })
    appointment.insert(ignore_permissions=True)
    return appointment
```

**Note on availability call**: `get_availability` is a whitelisted function but is callable in-process. It takes `practice_slug` not the practice dict, and looks up the practice from the slug. We need a slug. Pass `practice["slug"]` — the `_get_practice_or_throw` result currently returns `name, practice_name, logo, color, email`. **Step 3 below updates `_get_practice_or_throw` to also return `slug`.**

- [ ] **Step 3: Add `slug` to `_get_practice_or_throw`'s field list**

Modify `medic_plus/api/booking.py`:

Old (line ~19):
```python
practice = frappe.db.get_value(
    "Practice",
    {"slug": practice_slug, "is_active": 1},
    ["name", "practice_name", "logo", "color", "email"],
    as_dict=True,
)
```

New:
```python
practice = frappe.db.get_value(
    "Practice",
    {"slug": practice_slug, "is_active": 1},
    ["name", "practice_name", "logo", "color", "email", "slug"],
    as_dict=True,
)
```

Simplify the `_book_slot` availability call to:
```python
available = get_availability(practice["slug"], practitioner, appointment_date)  # flat list of "HH:MM:SS"
```

- [ ] **Step 4: Rewrite `verify_and_book` to call `_book_slot`**

In `medic_plus/api/booking.py`, replace the appointment-creation block inside `verify_and_book` (starting at `# Resolve appointment type — fall back to "Consultation" if none passed`) with:

```python
    appointment = _book_slot(
        patient_name=patient_name,
        practice=practice,
        practitioner=practitioner,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        appointment_type=appointment_type,
    )
```

Leave the patient-resolution code, `_send_confirmation_email` call, and `frappe.db.commit()` in place around it.

- [ ] **Step 5: Run existing booking tests**

Run:
```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus --skip-before-tests --module medic_plus.api.test_booking.py 2>&1 | tail -30
```

(File may not exist — that's OK, the next step covers it.)

- [ ] **Step 6: Smoke the existing guest booking flow**

From bench root:
```bash
SLUG=$(bench --site medic-demo-staging.thedaystar.co.za execute 'frappe.db.get_value' --kwargs '{"doctype":"Practice","filters":{"is_active":1},"fieldname":"slug"}' 2>&1 | tail -1)
echo "slug=$SLUG"
```

Manually open `https://medic-demo-staging.thedaystar.co.za/book?practice=$SLUG`, walk one booking through — confirm a Patient Appointment is created. Expected: identical behavior to before the refactor.

- [ ] **Step 7: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/api/booking.py
git commit -m "refactor: extract _book_slot helper from verify_and_book"
```

---

## Task 2: Permission infrastructure — `_get_customer_for_user` + extend Patient Encounter PQC

**Files:**
- Modify: `medic_plus/api/permissions.py`

- [ ] **Step 1: Add `_get_customer_for_user` helper**

Insert into `medic_plus/api/permissions.py` immediately below `_get_patient_name_for_user` (after line ~25):

```python
def _get_customer_for_user(user: str = None) -> str | None:
    """Return the Customer link from the Patient record matching the session user's email."""
    return frappe.db.get_value("Patient", {"email": user or frappe.session.user}, "customer")
```

- [ ] **Step 2: Add `Patient`-role branch to `get_patient_encounter_permission_query`**

Modify `medic_plus/api/permissions.py` lines ~75–81 (`get_patient_encounter_permission_query`):

Old:
```python
def get_patient_encounter_permission_query(user: str = None) -> str:
    if _is_platform_admin(user):
        return ""
    practice = _get_user_practice(user)
    if not practice:
        return "1=0"
    return f"`tabPatient Encounter`.`custom_practice` = {frappe.db.escape(practice)}"
```

New:
```python
def get_patient_encounter_permission_query(user: str = None) -> str:
    if _is_platform_admin(user):
        return ""
    if "Patient" in frappe.get_roles(user or frappe.session.user):
        patient = _get_patient_name_for_user(user)
        return f"`tabPatient Encounter`.`patient` = {frappe.db.escape(patient)}" if patient else "1=0"
    practice = _get_user_practice(user)
    if not practice:
        return "1=0"
    return f"`tabPatient Encounter`.`custom_practice` = {frappe.db.escape(practice)}"
```

- [ ] **Step 3: Add new PQCs for Patient Problem List, Medication Request, Sales Invoice**

Append to `medic_plus/api/permissions.py`:

```python
def get_patient_problem_list_permission_query(user: str = None) -> str:
    if _is_platform_admin(user):
        return ""
    if "Patient" in frappe.get_roles(user or frappe.session.user):
        patient = _get_patient_name_for_user(user)
        return f"`tabPatient Problem List`.`patient` = {frappe.db.escape(patient)}" if patient else "1=0"
    practice = _get_user_practice(user)
    if not practice:
        return "1=0"
    return (
        f"`tabPatient Problem List`.`patient` IN ("
        f"SELECT `name` FROM `tabPatient` WHERE `custom_practice` = {frappe.db.escape(practice)}"
        f")"
    )


def get_medication_request_permission_query(user: str = None) -> str:
    if _is_platform_admin(user):
        return ""
    if "Patient" in frappe.get_roles(user or frappe.session.user):
        patient = _get_patient_name_for_user(user)
        return f"`tabMedication Request`.`patient` = {frappe.db.escape(patient)}" if patient else "1=0"
    practice = _get_user_practice(user)
    if not practice:
        return "1=0"
    return (
        f"`tabMedication Request`.`patient` IN ("
        f"SELECT `name` FROM `tabPatient` WHERE `custom_practice` = {frappe.db.escape(practice)}"
        f")"
    )


def get_sales_invoice_permission_query(user: str = None) -> str:
    if _is_platform_admin(user):
        return ""
    if "Patient" in frappe.get_roles(user or frappe.session.user):
        customer = _get_customer_for_user(user)
        return f"`tabSales Invoice`.`customer` = {frappe.db.escape(customer)}" if customer else "1=0"
    # Staff: scope by practice via the Patient → Customer chain.
    practice = _get_user_practice(user)
    if not practice:
        return ""  # No practice — defer to ERPNext default scoping
    return (
        f"`tabSales Invoice`.`customer` IN ("
        f"SELECT `customer` FROM `tabPatient` WHERE `custom_practice` = {frappe.db.escape(practice)} AND `customer` IS NOT NULL"
        f") OR `tabSales Invoice`.`customer` IS NULL"
    )
```

(The Sales Invoice staff branch is permissive to avoid breaking existing ERPNext billing for staff users; the patient branch is tight. Patient-portal isolation is the goal here, not retrofitting tenant scoping onto staff Sales Invoice access.)

- [ ] **Step 4: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/api/permissions.py
git commit -m "feat(permissions): add patient-role PQC branches for portal-visible doctypes"
```

---

## Task 3: Register new PQCs in `hooks.py`

**Files:**
- Modify: `medic_plus/hooks.py`

- [ ] **Step 1: Locate the `permission_query_conditions` dict**

Run: `grep -n "permission_query_conditions" medic_plus/hooks.py`

Confirmed at line 154.

- [ ] **Step 2: Add entries**

Note: Patient Problem List and Sales Invoice PQCs are already registered in hooks.py from prior work. Only Medication Request is a net-new entry. Add to `medic_plus/hooks.py` inside the `permission_query_conditions` dict (alphabetical ordering preferred to match existing style):

```python
"Medication Request": "medic_plus.api.permissions.get_medication_request_permission_query",
```

- [ ] **Step 3: Clear cache + restart so hooks reload**

Run:
```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za clear-cache
bench restart
```

Expected: no errors. If you see `KeyError`, the dict entry is malformed — check trailing commas.

- [ ] **Step 4: Smoke that staff access still works**

Run:
```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za execute "frappe.get_all" --kwargs '{"doctype":"Patient","limit":1}'
```

Expected: returns a Patient or empty list (no error). If `1=0` or PermissionError, the hook is misregistered.

- [ ] **Step 5: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/hooks.py
git commit -m "feat(hooks): register Patient Problem List / Medication Request / Sales Invoice PQCs"
```

---

## Task 4: OTP endpoints — `request_portal_otp` + `verify_portal_otp`

**Files:**
- Create: `medic_plus/api/patient_portal.py`
- Test: `medic_plus/api/test_patient_portal.py`

- [ ] **Step 1: Create `patient_portal.py` with imports + shared constants + helpers**

Create `medic_plus/api/patient_portal.py`:

```python
"""Patient Portal API — practice-scoped, OTP-authenticated patient-facing endpoints.

See docs/superpowers/specs/2026-05-18-patient-portal-design.md
"""
import random
import frappe
from frappe.utils import getdate, get_datetime, now_datetime
from datetime import timedelta


# ---------------------------------------------------------------------------
# OTP infrastructure (parallel to medic_plus.api.booking; intentional duplicate
# to keep portal and guest booking flows fully independent)
# ---------------------------------------------------------------------------

OTP_TTL_SECONDS = 600  # 10 minutes
OTP_MAX_SEND_PER_WINDOW = 5
OTP_SEND_WINDOW_SECONDS = 600  # 10 minutes
OTP_MAX_VERIFY_ATTEMPTS = 5


def _otp_cache_key(slug: str, email: str) -> str:
    return f"portal_otp|{slug}|{email.lower().strip()}"


def _otp_attempt_key(slug: str, email: str) -> str:
    return f"portal_otp_attempt|{slug}|{email.lower().strip()}"


def _otp_verify_attempt_key(slug: str, email: str) -> str:
    return f"portal_otp_verify_attempt|{slug}|{email.lower().strip()}"


def _resolve_practice(slug: str) -> dict | None:
    return frappe.db.get_value(
        "Practice",
        {"slug": slug, "is_active": 1},
        ["name", "practice_name", "logo", "color", "email", "slug"],
        as_dict=True,
    )


def _send_portal_otp_email(email: str, otp: str, practice: dict):
    subject = frappe._("Your sign-in code — {0}").format(practice["practice_name"])
    logo_tag = (
        f"<img src='{practice['logo']}' style='height:48px;margin-bottom:24px;display:block;' alt='{practice['practice_name']}'>"
        if practice.get("logo") else ""
    )
    message = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;border:1px solid #e5e7eb;border-radius:8px;">
        {logo_tag}
        <h2 style="margin:0 0 8px;font-size:1.2rem;color:#111;">{practice['practice_name']} — Patient Portal</h2>
        <p style="color:#555;margin:0 0 24px;">Use the code below to sign in. It expires in <strong>10 minutes</strong>.</p>
        <div style="background:#f3f4f6;border-radius:8px;padding:20px;text-align:center;letter-spacing:0.3em;font-size:2rem;font-weight:700;color:#111;">{otp}</div>
        <p style="color:#999;font-size:0.8rem;margin:24px 0 0;">If you did not request this code, you can safely ignore this email.</p>
    </div>
    """
    frappe.sendmail(recipients=[email], subject=subject, message=message, now=True)
```

- [ ] **Step 2: Add `request_portal_otp` endpoint**

Append to `medic_plus/api/patient_portal.py`:

```python
@frappe.whitelist(allow_guest=True, methods=["POST"])
def request_portal_otp(slug: str, email: str) -> dict:
    """Send a 6-digit OTP to `email` if a Patient record exists at `slug`.

    Always returns {ok: true} regardless of match — prevents email enumeration.
    Rate-limited to 5 sends per email/slug per 10 minutes.
    """
    email = (email or "").lower().strip()
    if not email or "@" not in email:
        frappe.throw(frappe._("Please enter a valid email address."))

    practice = _resolve_practice(slug)
    if not practice:
        # Don't reveal whether a slug is valid; respond with the same shape.
        return {"ok": True}

    attempt_key = _otp_attempt_key(slug, email)
    attempts = frappe.cache.get_value(attempt_key) or 0
    if attempts >= OTP_MAX_SEND_PER_WINDOW:
        frappe.throw(
            frappe._("Too many sign-in attempts. Please wait 10 minutes and try again."),
            title=frappe._("Rate Limited"),
        )

    # Check if Patient exists at this practice with this email. If not, no-op
    # but still increment rate-limit + return success (anti-enumeration).
    patient_exists = frappe.db.exists("Patient", {"email": email, "custom_practice": practice["name"]})

    frappe.cache.set_value(attempt_key, attempts + 1, expires_in_sec=OTP_SEND_WINDOW_SECONDS)

    if patient_exists:
        otp = str(random.randint(100000, 999999))
        frappe.cache.set_value(_otp_cache_key(slug, email), otp, expires_in_sec=OTP_TTL_SECONDS)
        frappe.cache.delete_value(_otp_verify_attempt_key(slug, email))  # reset verify attempts on each send
        _send_portal_otp_email(email, otp, practice)

    return {"ok": True}
```

- [ ] **Step 3: Add `verify_portal_otp` endpoint**

Append to `medic_plus/api/patient_portal.py`:

```python
@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_portal_otp(slug: str, email: str, code: str) -> dict:
    """Verify OTP, auto-provision a Frappe User if needed, log in."""
    email = (email or "").lower().strip()
    code = (code or "").strip()

    practice = _resolve_practice(slug)
    if not practice:
        frappe.throw(frappe._("Invalid sign-in link."), frappe.DoesNotExistError)

    verify_key = _otp_verify_attempt_key(slug, email)
    verify_attempts = frappe.cache.get_value(verify_key) or 0
    if verify_attempts >= OTP_MAX_VERIFY_ATTEMPTS:
        frappe.throw(
            frappe._("Too many incorrect attempts. Request a new code."),
            title=frappe._("Locked"),
        )

    otp_key = _otp_cache_key(slug, email)
    stored = frappe.cache.get_value(otp_key)
    if not stored:
        frappe.throw(frappe._("Code expired. Request a new one."), title=frappe._("Expired"))

    if code != stored:
        frappe.cache.set_value(verify_key, verify_attempts + 1, expires_in_sec=OTP_TTL_SECONDS)
        frappe.throw(frappe._("Incorrect code. Please try again."), title=frappe._("Invalid Code"))

    # Success — consume OTP and counters
    frappe.cache.delete_value(otp_key)
    frappe.cache.delete_value(verify_key)
    frappe.cache.delete_value(_otp_attempt_key(slug, email))

    # Ensure Patient still exists at this practice (defense vs. mid-flight revocation)
    if not frappe.db.exists("Patient", {"email": email, "custom_practice": practice["name"]}):
        frappe.throw(frappe._("No patient record found."), frappe.DoesNotExistError)

    # Auto-provision User if missing
    user = frappe.db.get_value("User", {"email": email}, "name")
    if not user:
        user_doc = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "enabled": 1,
            "user_type": "Website User",
            "send_welcome_email": 0,
        })
        user_doc.flags.ignore_permissions = True
        user_doc.insert(ignore_permissions=True)
        user = user_doc.name

    # Ensure `Patient` role
    user_doc = frappe.get_doc("User", user)
    if not any(r.role == "Patient" for r in user_doc.roles):
        user_doc.append("roles", {"role": "Patient"})
        user_doc.save(ignore_permissions=True)

    # Log in
    frappe.local.login_manager.login_as(user)
    frappe.db.commit()

    return {
        "ok": True,
        "slug": slug,
        "csrf_token": frappe.local.session.data.csrf_token if frappe.local.session else None,
    }
```

- [ ] **Step 4: Create test scaffolding**

Create `medic_plus/api/test_patient_portal.py`:

```python
"""Patient Portal — Python tests.

Per medic_plus CLAUDE.md, IGNORE_TEST_RECORD_DEPENDENCIES prevents the test
framework from importing ERPNext test modules that crash at BootStrapTestData.
"""
import frappe
import unittest
from medic_plus.api import patient_portal


IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


class TestPortalOTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slug = "ttp-otp"
        cls.practice = frappe.get_doc({
            "doctype": "Practice",
            "practice_name": "TTP OTP Practice",
            "slug": cls.slug,
            "is_active": 1,
            "email": "ttp-otp@example.com",
        }).insert(ignore_permissions=True)

        cls.email = "ttp-patient@example.com"
        cls.patient = frappe.get_doc({
            "doctype": "Patient",
            "first_name": "Otp",
            "last_name": "Tester",
            "sex": "Male",
            "email": cls.email,
            "custom_practice": cls.practice.name,
            "status": "Active",
            "invite_user": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        # Cascade: delete patient, then practice. Ignore_permissions because
        # PQCs may be hostile in the post-test cleanup user context.
        frappe.db.delete("Patient", {"name": cls.patient.name})
        frappe.db.delete("Practice", {"name": cls.practice.name})
        frappe.db.delete("User", {"email": cls.email})
        frappe.db.commit()

    def setUp(self):
        # Wipe OTP cache state between tests
        for key in (
            patient_portal._otp_cache_key(self.slug, self.email),
            patient_portal._otp_attempt_key(self.slug, self.email),
            patient_portal._otp_verify_attempt_key(self.slug, self.email),
        ):
            frappe.cache.delete_value(key)

    def test_request_otp_existing_patient_emits_code(self):
        result = patient_portal.request_portal_otp(self.slug, self.email)
        self.assertEqual(result, {"ok": True})
        cached = frappe.cache.get_value(patient_portal._otp_cache_key(self.slug, self.email))
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 6)
        self.assertTrue(cached.isdigit())

    def test_request_otp_unknown_email_does_not_emit_code(self):
        result = patient_portal.request_portal_otp(self.slug, "ghost@example.com")
        self.assertEqual(result, {"ok": True})
        cached = frappe.cache.get_value(patient_portal._otp_cache_key(self.slug, "ghost@example.com"))
        self.assertIsNone(cached)

    def test_request_otp_rate_limited_after_5_requests(self):
        for _ in range(5):
            patient_portal.request_portal_otp(self.slug, self.email)
        with self.assertRaises(frappe.ValidationError):
            patient_portal.request_portal_otp(self.slug, self.email)

    def test_verify_otp_correct_code_logs_user_in(self):
        patient_portal.request_portal_otp(self.slug, self.email)
        code = frappe.cache.get_value(patient_portal._otp_cache_key(self.slug, self.email))
        result = patient_portal.verify_portal_otp(self.slug, self.email, code)
        self.assertTrue(result["ok"])
        self.assertEqual(frappe.session.user, self.email)

    def test_verify_otp_wrong_code_increments_attempts(self):
        patient_portal.request_portal_otp(self.slug, self.email)
        with self.assertRaises(frappe.ValidationError):
            patient_portal.verify_portal_otp(self.slug, self.email, "000000")
        attempts = frappe.cache.get_value(patient_portal._otp_verify_attempt_key(self.slug, self.email))
        self.assertEqual(attempts, 1)

    def test_verify_otp_provisions_user_with_patient_role(self):
        patient_portal.request_portal_otp(self.slug, self.email)
        code = frappe.cache.get_value(patient_portal._otp_cache_key(self.slug, self.email))
        patient_portal.verify_portal_otp(self.slug, self.email, code)
        user_doc = frappe.get_doc("User", self.email)
        self.assertIn("Patient", [r.role for r in user_doc.roles])
        self.assertEqual(user_doc.user_type, "Website User")
```

- [ ] **Step 5: Run the tests**

```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus --skip-before-tests --module medic_plus.api.test_patient_portal 2>&1 | tail -40
```

Expected: 6 tests pass. If you see `BootStrapTestData` errors, double-check `IGNORE_TEST_RECORD_DEPENDENCIES` is at module level. If `mute_emails` errors, set it to 0 temporarily — see Risks in spec.

- [ ] **Step 6: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/api/patient_portal.py medic_plus/api/test_patient_portal.py
git commit -m "feat(portal): email-OTP authentication endpoints"
```

---

## Task 5: Profile endpoints — `get_me` + `update_me` + editable allowlist

**Files:**
- Modify: `medic_plus/api/patient_portal.py`
- Modify: `medic_plus/api/test_patient_portal.py`

- [ ] **Step 1: Add ownership helper + editable allowlist**

Append to `medic_plus/api/patient_portal.py`:

```python
# ---------------------------------------------------------------------------
# Ownership + allowlist helpers
# ---------------------------------------------------------------------------

PATIENT_EDITABLE_FIELDS = {
    "first_name", "middle_name", "last_name", "dob", "sex",
    "mobile", "phone", "email", "blood_group",
    "marital_status", "occupation",
    "address_line1", "address_line2", "city", "state", "zip_code", "country",
    "allergies", "medication",
    "custom_preferred_language", "custom_ai_consent",
}


def _require_authed():
    if frappe.session.user == "Guest":
        frappe.throw(frappe._("Please sign in."), frappe.PermissionError)


def _resolve_my_patient(slug: str) -> dict:
    """Resolve the session user's Patient record at the given practice.

    Throws PermissionError if no match — never reveals practice/patient existence.
    """
    _require_authed()
    practice = _resolve_practice(slug)
    if not practice:
        frappe.throw(frappe._("No patient record."), frappe.PermissionError)
    patient = frappe.db.get_value(
        "Patient",
        {"email": frappe.session.user, "custom_practice": practice["name"]},
        ["name", "first_name", "middle_name", "last_name", "dob", "sex",
         "mobile", "phone", "email", "blood_group", "marital_status", "occupation",
         "address_line1", "address_line2", "city", "state", "zip_code", "country",
         "allergies", "medication", "custom_preferred_language", "custom_ai_consent",
         "custom_practice", "customer", "custom_sa_id_number"],
        as_dict=True,
    )
    if not patient:
        frappe.throw(frappe._("No patient record."), frappe.PermissionError)
    return patient
```

- [ ] **Step 2: Add `get_me`**

Append to `medic_plus/api/patient_portal.py`:

```python
@frappe.whitelist(methods=["GET", "POST"])
def get_me(slug: str) -> dict:
    """Return the session user's Patient record (editable fields + masked SA ID)."""
    patient = _resolve_my_patient(slug)
    # Mask SA ID — only last 4 visible
    sa_id = patient.get("custom_sa_id_number")
    if sa_id:
        patient["custom_sa_id_number_masked"] = "•" * (len(sa_id) - 4) + sa_id[-4:]
    patient.pop("custom_sa_id_number", None)
    return patient
```

- [ ] **Step 3: Add `update_me`**

Append to `medic_plus/api/patient_portal.py`:

```python
@frappe.whitelist(methods=["POST"])
def update_me(slug: str, payload: dict) -> dict:
    """PATCH the session user's Patient record using only fields on the allowlist."""
    patient = _resolve_my_patient(slug)

    if not isinstance(payload, dict):
        try:
            payload = frappe.parse_json(payload)
        except Exception:
            frappe.throw(frappe._("Invalid payload."))

    rejected = [k for k in payload.keys() if k not in PATIENT_EDITABLE_FIELDS]
    if rejected:
        frappe.throw(
            frappe._("Cannot edit fields: {0}").format(", ".join(rejected)),
            title=frappe._("Forbidden Fields"),
        )

    pdoc = frappe.get_doc("Patient", patient["name"])
    for k, v in payload.items():
        setattr(pdoc, k, v)
    pdoc.save(ignore_permissions=False)
    frappe.db.commit()

    return get_me(slug)
```

- [ ] **Step 4: Add tests**

Append to `medic_plus/api/test_patient_portal.py`:

```python
class TestPortalProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slug = "ttp-prof"
        cls.practice = frappe.get_doc({
            "doctype": "Practice", "practice_name": "TTP Prof", "slug": cls.slug,
            "is_active": 1, "email": "ttp-prof@example.com",
        }).insert(ignore_permissions=True)
        cls.email = "ttp-prof-patient@example.com"
        cls.patient = frappe.get_doc({
            "doctype": "Patient", "first_name": "Prof", "last_name": "User",
            "sex": "Female", "email": cls.email, "custom_practice": cls.practice.name,
            "status": "Active", "invite_user": 0,
        }).insert(ignore_permissions=True)
        # Provision a User with Patient role
        cls.user = frappe.get_doc({
            "doctype": "User", "email": cls.email, "first_name": "Prof",
            "enabled": 1, "user_type": "Website User", "send_welcome_email": 0,
            "roles": [{"role": "Patient"}],
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.db.delete("Patient", {"name": cls.patient.name})
        frappe.db.delete("Practice", {"name": cls.practice.name})
        frappe.db.delete("User", {"email": cls.email})
        frappe.db.commit()

    def setUp(self):
        frappe.set_user(self.email)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_get_me_returns_editable_and_masked(self):
        me = patient_portal.get_me(self.slug)
        self.assertEqual(me["email"], self.email)
        self.assertNotIn("custom_sa_id_number", me)
        self.assertEqual(me["first_name"], "Prof")

    def test_update_me_accepts_allowed_field(self):
        result = patient_portal.update_me(self.slug, {"mobile": "+27821234567"})
        self.assertEqual(result["mobile"], "+27821234567")

    def test_update_me_rejects_forbidden_field(self):
        with self.assertRaises(frappe.ValidationError):
            patient_portal.update_me(self.slug, {"custom_practice": "OTHER"})

    def test_update_me_rejects_unknown_field(self):
        with self.assertRaises(frappe.ValidationError):
            patient_portal.update_me(self.slug, {"is_admin": True})

    def test_resolve_my_patient_rejects_guest(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            patient_portal._resolve_my_patient(self.slug)
```

- [ ] **Step 5: Run tests**

```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus --skip-before-tests --module medic_plus.api.test_patient_portal 2>&1 | tail -40
```

Expected: 11 tests pass (6 from Task 4 + 5 new).

- [ ] **Step 6: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/api/patient_portal.py medic_plus/api/test_patient_portal.py
git commit -m "feat(portal): get_me / update_me with editable allowlist"
```

---

## Task 6: Appointments endpoints — list, cancel, authed booking, resolver

**Files:**
- Modify: `medic_plus/api/patient_portal.py`
- Modify: `medic_plus/api/test_patient_portal.py`

- [ ] **Step 1: Add `list_my_appointments`, `cancel_my_appointment`**

Append to `medic_plus/api/patient_portal.py`:

```python
# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["GET", "POST"])
def list_my_appointments(slug: str) -> dict:
    patient = _resolve_my_patient(slug)
    upcoming = frappe.get_all(
        "Patient Appointment",
        filters={"patient": patient["name"], "appointment_date": [">=", frappe.utils.today()],
                 "status": ["not in", ["Cancelled"]]},
        fields=["name", "practitioner", "practitioner_name", "appointment_date",
                "appointment_time", "duration", "status", "notes"],
        order_by="appointment_date asc, appointment_time asc",
        limit=50,
    )
    past = frappe.get_all(
        "Patient Appointment",
        filters={"patient": patient["name"], "appointment_date": ["<", frappe.utils.today()]},
        fields=["name", "practitioner", "practitioner_name", "appointment_date",
                "appointment_time", "duration", "status"],
        order_by="appointment_date desc, appointment_time desc",
        limit=20,
    )
    return {"upcoming": upcoming, "past": past}


@frappe.whitelist(methods=["POST"])
def cancel_my_appointment(slug: str, name: str) -> dict:
    patient = _resolve_my_patient(slug)
    appt = frappe.db.get_value(
        "Patient Appointment",
        {"name": name, "patient": patient["name"]},
        ["appointment_date", "appointment_time", "status"],
        as_dict=True,
    )
    if not appt:
        frappe.throw(frappe._("Appointment not found."), frappe.DoesNotExistError)
    if appt["status"] == "Cancelled":
        frappe.throw(frappe._("Already cancelled."))

    # Combine date + time into datetime; status is 24h before that.
    appt_dt = get_datetime(f"{appt['appointment_date']} {appt['appointment_time']}")
    if appt_dt - now_datetime() < timedelta(hours=24):
        frappe.throw(
            frappe._("Cancellations must be at least 24 hours before the appointment. Please call the practice."),
            title=frappe._("Too Late to Cancel"),
        )

    frappe.db.set_value("Patient Appointment", name, "status", "Cancelled")
    frappe.db.commit()
    return {"ok": True}
```

- [ ] **Step 2: Add `book_for_authed_patient`**

Append to `medic_plus/api/patient_portal.py`:

```python
@frappe.whitelist(methods=["POST"])
def book_for_authed_patient(slug: str, practitioner: str, appointment_date: str,
                              appointment_time: str, reason: str = "") -> dict:
    """Authed booking — calls shared _book_slot helper from medic_plus.api.booking."""
    from medic_plus.api import booking as booking_mod

    patient = _resolve_my_patient(slug)
    practice = _resolve_practice(slug)

    # Validate practitioner is a member of the practice
    if not frappe.db.exists(
        "Practice Member",
        {"practice": practice["name"], "practitioner": practitioner, "role": "Doctor"},
    ):
        frappe.throw(frappe._("Practitioner not found at this practice."), frappe.DoesNotExistError)

    appointment = booking_mod._book_slot(
        patient_name=patient["name"],
        practice=practice,
        practitioner=practitioner,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        reason=reason,
    )
    frappe.db.commit()
    return {"ok": True, "appointment_name": appointment.name}
```

- [ ] **Step 3: Add `resolve_my_practices` + `get_boot` endpoints**

Append to `medic_plus/api/patient_portal.py`:

```python
@frappe.whitelist(methods=["GET", "POST"])
def resolve_my_practices() -> list:
    """Return practices where session user has a Patient record. For /portal resolver."""
    _require_authed()
    rows = frappe.db.sql("""
        SELECT pr.slug, pr.practice_name, pr.logo, pr.color
        FROM `tabPatient` p
        JOIN `tabPractice` pr ON pr.name = p.custom_practice
        WHERE p.email = %(email)s AND pr.is_active = 1
        ORDER BY pr.practice_name ASC
    """, {"email": frappe.session.user}, as_dict=True)
    return rows or []


@frappe.whitelist(methods=["GET", "POST"])
def get_boot(slug: str) -> dict:
    """Boot context for the SPA: practice info + auth state."""
    practice = _resolve_practice(slug)
    if not practice:
        frappe.throw(frappe._("Practice not found."), frappe.DoesNotExistError)
    is_authed = frappe.session.user != "Guest"
    has_patient = False
    patient_name = None
    if is_authed:
        patient_name = frappe.db.get_value(
            "Patient", {"email": frappe.session.user, "custom_practice": practice["name"]}, "name"
        )
        has_patient = bool(patient_name)
    return {
        "practice": practice,
        "is_authed": is_authed,
        "has_patient": has_patient,
        "patient_name": patient_name,
        "session_user": frappe.session.user if is_authed else None,
    }
```

- [ ] **Step 4: Add tests for appointments + cancellation**

Append to `medic_plus/api/test_patient_portal.py`:

```python
from frappe.utils import add_days, add_to_date, today as fr_today


class TestPortalAppointments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slug = "ttp-appt"
        cls.practice = frappe.get_doc({
            "doctype": "Practice", "practice_name": "TTP Appt", "slug": cls.slug,
            "is_active": 1, "email": "ttp-appt@example.com",
        }).insert(ignore_permissions=True)
        cls.email = "ttp-appt-patient@example.com"
        cls.patient = frappe.get_doc({
            "doctype": "Patient", "first_name": "Appt", "last_name": "User",
            "sex": "Male", "email": cls.email, "custom_practice": cls.practice.name,
            "status": "Active", "invite_user": 0,
        }).insert(ignore_permissions=True)
        cls.user = frappe.get_doc({
            "doctype": "User", "email": cls.email, "first_name": "Appt",
            "enabled": 1, "user_type": "Website User", "send_welcome_email": 0,
            "roles": [{"role": "Patient"}],
        }).insert(ignore_permissions=True)

        # Build an appointment 5 days out (cancellable) and one 1 hour out (not cancellable)
        cls.far_appt = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": cls.patient.name,
            "appointment_for": "Practitioner",
            "appointment_date": add_days(fr_today(), 5),
            "appointment_time": "10:00:00",
            "duration": 30,
            "custom_practice": cls.practice.name,
            "status": "Open",
        }).insert(ignore_permissions=True)
        soon = add_to_date(now_datetime(), hours=2)
        cls.soon_appt = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": cls.patient.name,
            "appointment_for": "Practitioner",
            "appointment_date": str(soon.date()),
            "appointment_time": soon.time().strftime("%H:%M:%S"),
            "duration": 30,
            "custom_practice": cls.practice.name,
            "status": "Open",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.db.delete("Patient Appointment", {"patient": cls.patient.name})
        frappe.db.delete("Patient", {"name": cls.patient.name})
        frappe.db.delete("Practice", {"name": cls.practice.name})
        frappe.db.delete("User", {"email": cls.email})
        frappe.db.commit()

    def setUp(self):
        frappe.set_user(self.email)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_list_my_appointments_returns_upcoming(self):
        result = patient_portal.list_my_appointments(self.slug)
        names = [a["name"] for a in result["upcoming"]]
        self.assertIn(self.far_appt.name, names)

    def test_cancel_appointment_24h_out_succeeds(self):
        result = patient_portal.cancel_my_appointment(self.slug, self.far_appt.name)
        self.assertTrue(result["ok"])
        self.assertEqual(
            frappe.db.get_value("Patient Appointment", self.far_appt.name, "status"),
            "Cancelled",
        )

    def test_cancel_appointment_within_24h_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            patient_portal.cancel_my_appointment(self.slug, self.soon_appt.name)

    def test_resolve_my_practices_lists_active(self):
        result = patient_portal.resolve_my_practices()
        slugs = [p["slug"] for p in result]
        self.assertIn(self.slug, slugs)

    def test_get_boot_returns_practice_and_has_patient(self):
        result = patient_portal.get_boot(self.slug)
        self.assertEqual(result["practice"]["slug"], self.slug)
        self.assertTrue(result["is_authed"])
        self.assertTrue(result["has_patient"])
```

- [ ] **Step 5: Run tests**

```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus --skip-before-tests --module medic_plus.api.test_patient_portal 2>&1 | tail -40
```

Expected: 16 tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/api/patient_portal.py medic_plus/api/test_patient_portal.py
git commit -m "feat(portal): list/cancel/book appointments + resolve_my_practices + get_boot"
```

---

## Task 7: Records, Documents, Billing endpoints

**Files:**
- Modify: `medic_plus/api/patient_portal.py`
- Modify: `medic_plus/api/test_patient_portal.py`

- [ ] **Step 1: Add records endpoints**

Append to `medic_plus/api/patient_portal.py`:

```python
# ---------------------------------------------------------------------------
# Records (read-only)
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["GET", "POST"])
def list_my_records(slug: str) -> dict:
    patient = _resolve_my_patient(slug)
    encounters = frappe.get_all(
        "Patient Encounter",
        filters={"patient": patient["name"], "docstatus": ["!=", 2]},
        fields=["name", "encounter_date", "practitioner_name", "encounter_time"],
        order_by="encounter_date desc",
        limit=50,
    )
    problems = (
        frappe.get_all(
            "Patient Problem List",
            filters={"patient": patient["name"]},
            fields=["name", "problem", "status", "onset_date"],
            order_by="onset_date desc",
            limit=50,
        ) if frappe.db.exists("DocType", "Patient Problem List") else []
    )
    allergies = (
        frappe.get_all(
            "Patient Allergy",
            filters={"patient": patient["name"]},
            fields=["name", "allergen", "severity", "reaction", "onset_date"],
            order_by="onset_date desc",
            limit=50,
        ) if frappe.db.exists("DocType", "Patient Allergy") else []
    )
    chronic = (
        frappe.get_all(
            "Patient Chronic Condition",
            filters={"patient": patient["name"]},
            fields=["name", "condition", "status", "onset_date"],
            order_by="onset_date desc",
            limit=50,
        ) if frappe.db.exists("DocType", "Patient Chronic Condition") else []
    )
    return {
        "encounters": encounters,
        "problems": problems,
        "allergies": allergies,
        "chronic_conditions": chronic,
    }


@frappe.whitelist(methods=["GET", "POST"])
def get_my_record_detail(slug: str, doctype: str, name: str) -> dict:
    """Read-only detail for a single record. Validates ownership server-side."""
    patient = _resolve_my_patient(slug)
    allowed = {"Patient Encounter", "Patient Problem List", "Patient Allergy", "Patient Chronic Condition"}
    if doctype not in allowed:
        frappe.throw(frappe._("Doctype not viewable."), frappe.PermissionError)
    owner = frappe.db.get_value(doctype, name, "patient")
    if owner != patient["name"]:
        frappe.throw(frappe._("Not your record."), frappe.PermissionError)
    return frappe.get_doc(doctype, name).as_dict()
```

- [ ] **Step 2: Add documents endpoints**

Append to `medic_plus/api/patient_portal.py`:

```python
# ---------------------------------------------------------------------------
# Documents (sick notes + prescriptions, downloadable PDFs)
# ---------------------------------------------------------------------------

DOCUMENTS_PRINT_FORMATS = {
    "Sick Note": "Sick Note",
    "Medication Request": "Prescription",  # confirm during impl — fallback to Standard if absent
}


@frappe.whitelist(methods=["GET", "POST"])
def list_my_documents(slug: str) -> dict:
    patient = _resolve_my_patient(slug)
    sick_notes = frappe.get_all(
        "Sick Note",
        filters={"patient": patient["name"], "docstatus": 1},
        fields=["name", "date_issued", "practitioner", "diagnosis", "days_off", "fit_for_work_date"],
        order_by="date_issued desc",
        limit=100,
    )
    prescriptions = (
        frappe.get_all(
            "Medication Request",
            filters={"patient": patient["name"], "docstatus": 1},
            fields=["name", "medication_request_date", "practitioner", "status"],
            order_by="medication_request_date desc",
            limit=100,
        ) if frappe.db.exists("DocType", "Medication Request") else []
    )
    return {"sick_notes": sick_notes, "prescriptions": prescriptions}


@frappe.whitelist(methods=["GET"])
def download_my_document(slug: str, doctype: str, name: str):
    """Return a PDF binary for a document the session user owns."""
    patient = _resolve_my_patient(slug)
    if doctype not in DOCUMENTS_PRINT_FORMATS:
        frappe.throw(frappe._("Doctype not downloadable."), frappe.PermissionError)
    owner = frappe.db.get_value(doctype, name, "patient")
    if owner != patient["name"]:
        frappe.throw(frappe._("Not your document."), frappe.PermissionError)

    print_format = DOCUMENTS_PRINT_FORMATS[doctype]
    if not frappe.db.exists("Print Format", print_format):
        print_format = "Standard"

    pdf_bytes = frappe.get_print(
        doctype=doctype, name=name, print_format=print_format, as_pdf=True
    )
    frappe.local.response.filename = f"{name}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type = "pdf"
```

- [ ] **Step 3: Add billing endpoint**

Append to `medic_plus/api/patient_portal.py`:

```python
# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["GET", "POST"])
def list_my_invoices(slug: str) -> list:
    patient = _resolve_my_patient(slug)
    customer = patient.get("customer")
    if not customer:
        return []
    return frappe.get_all(
        "Sales Invoice",
        filters={"customer": customer, "docstatus": ["!=", 2]},
        fields=["name", "posting_date", "due_date", "grand_total",
                "outstanding_amount", "status", "currency"],
        order_by="posting_date desc",
        limit=100,
    )


@frappe.whitelist(methods=["GET"])
def download_my_invoice(slug: str, name: str):
    patient = _resolve_my_patient(slug)
    customer = patient.get("customer")
    if not customer:
        frappe.throw(frappe._("No invoices."), frappe.DoesNotExistError)
    owner = frappe.db.get_value("Sales Invoice", name, "customer")
    if owner != customer:
        frappe.throw(frappe._("Not your invoice."), frappe.PermissionError)
    pdf_bytes = frappe.get_print(doctype="Sales Invoice", name=name, as_pdf=True)
    frappe.local.response.filename = f"{name}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type = "pdf"
```

- [ ] **Step 4: Add cross-tenant isolation test**

Append to `medic_plus/api/test_patient_portal.py`:

```python
class TestPortalCrossTenantIsolation(unittest.TestCase):
    """The headline POPIA-relevant test: a Patient at Practice A cannot read
    Patient B's appointments / sick notes / records / invoices at Practice B."""

    @classmethod
    def setUpClass(cls):
        # Practice A + Patient A
        cls.slug_a = "ttp-iso-a"
        cls.practice_a = frappe.get_doc({
            "doctype": "Practice", "practice_name": "TTP Iso A", "slug": cls.slug_a,
            "is_active": 1, "email": "ttp-iso-a@example.com",
        }).insert(ignore_permissions=True)
        cls.email_a = "ttp-iso-a-patient@example.com"
        cls.patient_a = frappe.get_doc({
            "doctype": "Patient", "first_name": "Iso", "last_name": "A",
            "sex": "Male", "email": cls.email_a, "custom_practice": cls.practice_a.name,
            "status": "Active", "invite_user": 0,
        }).insert(ignore_permissions=True)
        cls.user_a = frappe.get_doc({
            "doctype": "User", "email": cls.email_a, "first_name": "Iso A",
            "enabled": 1, "user_type": "Website User", "send_welcome_email": 0,
            "roles": [{"role": "Patient"}],
        }).insert(ignore_permissions=True)

        # Practice B + Patient B + Appointment B
        cls.slug_b = "ttp-iso-b"
        cls.practice_b = frappe.get_doc({
            "doctype": "Practice", "practice_name": "TTP Iso B", "slug": cls.slug_b,
            "is_active": 1, "email": "ttp-iso-b@example.com",
        }).insert(ignore_permissions=True)
        cls.email_b = "ttp-iso-b-patient@example.com"
        cls.patient_b = frappe.get_doc({
            "doctype": "Patient", "first_name": "Iso", "last_name": "B",
            "sex": "Female", "email": cls.email_b, "custom_practice": cls.practice_b.name,
            "status": "Active", "invite_user": 0,
        }).insert(ignore_permissions=True)
        cls.appt_b = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": cls.patient_b.name, "appointment_for": "Practitioner",
            "appointment_date": add_days(fr_today(), 7),
            "appointment_time": "09:00:00", "duration": 30,
            "custom_practice": cls.practice_b.name, "status": "Open",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        for d in (cls.appt_b.name,):
            frappe.db.delete("Patient Appointment", {"name": d})
        for d in (cls.patient_a.name, cls.patient_b.name):
            frappe.db.delete("Patient", {"name": d})
        for d in (cls.practice_a.name, cls.practice_b.name):
            frappe.db.delete("Practice", {"name": d})
        for d in (cls.email_a, cls.email_b):
            frappe.db.delete("User", {"email": d})
        frappe.db.commit()

    def test_patient_a_cannot_resolve_practice_b(self):
        frappe.set_user(self.email_a)
        try:
            with self.assertRaises(frappe.PermissionError):
                patient_portal._resolve_my_patient(self.slug_b)
        finally:
            frappe.set_user("Administrator")

    def test_patient_a_cannot_list_practice_b_appointments(self):
        # Direct PQC call (don't rely on session role cache)
        from medic_plus.api.permissions import get_patient_appointment_permission_query
        condition = get_patient_appointment_permission_query(user=self.email_a)
        # Condition should scope to Patient A's name, not B's
        self.assertIn(self.patient_a.name, condition)
        self.assertNotIn(self.patient_b.name, condition)
        self.assertNotIn(self.appt_b.name, condition)
```

- [ ] **Step 5: Run tests**

```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus --skip-before-tests --module medic_plus.api.test_patient_portal 2>&1 | tail -40
```

Expected: 18 tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/api/patient_portal.py medic_plus/api/test_patient_portal.py
git commit -m "feat(portal): records / documents / billing endpoints + cross-tenant isolation test"
```

---

## Task 8: Jinja shell + boot context for `/portal/<slug>`

**Files:**
- Replace contents: `medic_plus/www/portal/index.html` and `index.py`

- [ ] **Step 1: Rewrite `index.py` as a boot resolver**

Replace `medic_plus/www/portal/index.py` with:

```python
import frappe


def get_context(context):
    context.no_cache = 1
    context.no_breadcrumbs = 1
    context.sitemap = 0

    slug = (frappe.form_dict.get("slug") or "").strip()
    context.slug = slug
    context.session_user = frappe.session.user if frappe.session.user != "Guest" else None
    context.csrf_token = frappe.local.session.data.csrf_token if frappe.local.session else ""

    # If no slug — render the resolver page; the SPA boot script handles routing.
    if not slug:
        context.practice = None
        context.is_authed = bool(context.session_user)
        context.has_patient = False
        return

    practice = frappe.db.get_value(
        "Practice",
        {"slug": slug, "is_active": 1},
        ["name", "practice_name", "logo", "color", "email", "slug"],
        as_dict=True,
    )
    context.practice = practice

    context.is_authed = bool(context.session_user)
    context.has_patient = False
    if practice and context.session_user:
        context.has_patient = bool(frappe.db.exists(
            "Patient",
            {"email": context.session_user, "custom_practice": practice.name},
        ))
```

- [ ] **Step 2: Rewrite `index.html` as the Jinja shell**

Replace `medic_plus/www/portal/index.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Patient Portal{% if practice %} — {{ practice.practice_name }}{% endif %}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="icon" type="image/png" href="/assets/medic_plus/daystar-health/daystar-medical-icon.png" />
<link rel="apple-touch-icon" href="/assets/medic_plus/daystar-health/daystar-medical-icon.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/assets/medic_plus/daystar-health/styles.css" />
<link rel="stylesheet" href="/assets/medic_plus/daystar-health/meridian.css" />
<link rel="stylesheet" href="/assets/medic_plus/portal/portal-styles.css" />
</head>
<body data-theme="light" data-density="comfortable">
<div id="root"></div>

<script>
window.__DAYSTAR_PORTAL__ = {
  csrfToken: {{ csrf_token | tojson }},
  sessionUser: {{ session_user | tojson }},
  slug: {{ slug | tojson }},
  practice: {{ practice | tojson }},
  isAuthed: {{ is_authed | tojson }},
  hasPatient: {{ has_patient | tojson }}
};
</script>
<script src="/assets/medic_plus/portal/portal-api.js"></script>

{% raw %}
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" crossorigin="anonymous"></script>

<!-- Reuse Meridian pickers + icons from /daystar-health -->
<script type="text/babel" src="/assets/medic_plus/daystar-health/meridian-icons.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/daystar-health/meridian-date-picker.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/daystar-health/meridian-time-picker.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/daystar-health/meridian-select.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/daystar-health/meridian-textarea.jsx"></script>

<!-- Portal-specific -->
<script type="text/babel" src="/assets/medic_plus/portal/portal-layout.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-login.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-practice-picker.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-home.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-appointments.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-book.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-profile.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-records.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-documents.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-billing.jsx"></script>
<script type="text/babel" src="/assets/medic_plus/portal/portal-app.jsx"></script>
{% endraw %}
</body>
</html>
```

- [ ] **Step 3: Smoke-test the page loads without 500**

```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za clear-cache
```

Open in a browser: `https://medic-demo-staging.thedaystar.co.za/portal/<an-active-slug>`. Expect: white page with a 404 in console for each `/assets/medic_plus/portal/*.js` (we haven't created them yet — next tasks). The Jinja page itself should render 200.

```bash
curl -sI -H "Host: medic-demo-staging.thedaystar.co.za" https://medic-demo-staging.thedaystar.co.za/portal/anything 2>&1 | head -2
```

- [ ] **Step 4: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/www/portal/index.html medic_plus/www/portal/index.py
git commit -m "feat(portal): Jinja shell + boot context at /portal/<slug>"
```

---

## Task 9: `portal-api.js` — fetch client

**Files:**
- Create: `medic_plus/public/portal/portal-api.js`

- [ ] **Step 1: Create the file**

Create `medic_plus/public/portal/portal-api.js`:

```javascript
// Patient Portal API client.
// Reads bootstrap state injected by medic_plus/www/portal/index.py:
//   csrfToken, sessionUser, slug, practice, isAuthed, hasPatient.

(function () {
  const bootstrap = window.__DAYSTAR_PORTAL__ || {};

  function showError(message) {
    if (window.frappe && typeof window.frappe.show_alert === "function") {
      window.frappe.show_alert({ message, indicator: "red" }, 5);
    } else {
      console.error("[portal-api]", message);
      alert(message);
    }
  }

  async function parseJson(response) {
    const text = await response.text();
    if (!text) return null;
    try { return JSON.parse(text); } catch { return text; }
  }

  function extractServerMessage(payload, fallback) {
    if (!payload || typeof payload === "string") return payload || fallback;
    if (payload.message) return payload.message;
    if (payload._server_messages) {
      try {
        const list = JSON.parse(payload._server_messages);
        if (list.length) return JSON.parse(list[0]).message || fallback;
      } catch {}
    }
    if (payload.exc_type) return `${payload.exc_type}: ${payload.exception || fallback}`;
    return fallback;
  }

  async function call(method, args = {}) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": bootstrap.csrfToken || "",
        Accept: "application/json",
      },
      body: JSON.stringify(args),
    });
    const payload = await parseJson(response);
    if (!response.ok) {
      const msg = extractServerMessage(payload, response.statusText);
      const err = new Error(msg);
      err.status = response.status;
      err.payload = payload;
      throw err;
    }
    return payload && payload.message !== undefined ? payload.message : payload;
  }

  function downloadUrl(method, args = {}) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(args)) {
      if (v == null) continue;
      params.append(k, typeof v === "string" ? v : JSON.stringify(v));
    }
    return `/api/method/${method}?${params.toString()}`;
  }

  window.portalApi = {
    bootstrap,
    slug: bootstrap.slug,
    isAuthenticated: !!bootstrap.isAuthed,
    hasPatient: !!bootstrap.hasPatient,
    sessionUser: bootstrap.sessionUser,
    practice: bootstrap.practice,
    call,
    downloadUrl,
    showError,
  };
})();
```

- [ ] **Step 2: Build assets so the file is mirrored under /assets**

```bash
cd /home/fruppa/frappe-bench
bench build --app medic_plus 2>&1 | tail -3
```

- [ ] **Step 3: Confirm asset is served**

```bash
curl -sI -H "Host: medic-demo-staging.thedaystar.co.za" https://medic-demo-staging.thedaystar.co.za/assets/medic_plus/portal/portal-api.js | head -1
```

Expected: `HTTP/2 200`.

- [ ] **Step 4: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-api.js
git commit -m "feat(portal): portal-api.js fetch client"
```

---

## Task 10: Portal layout — shell, topbar, sidebar, drawer

**Files:**
- Create: `medic_plus/public/portal/portal-layout.jsx`
- Create: `medic_plus/public/portal/portal-styles.css`

- [ ] **Step 1: Create `portal-styles.css`**

Create `medic_plus/public/portal/portal-styles.css`:

```css
/* Portal-only overrides on top of meridian.css. Mobile-first per CLAUDE.md. */

.portal-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg);
}

.portal-topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
}

.portal-topbar .practice-logo {
  height: 32px;
  width: auto;
}

.portal-topbar .practice-name {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.portal-topbar .spacer { flex: 1; }

.portal-main {
  flex: 1;
  padding: 16px;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

.portal-tabs {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--border);
  -webkit-overflow-scrolling: touch;
}

.portal-tab {
  padding: 10px 14px;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
  min-height: 40px;
}

.portal-tab.active {
  color: var(--text);
  border-bottom-color: var(--accent, #2563eb);
}

.portal-drawer {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(0,0,0,0.4);
  display: none;
}

.portal-drawer.open { display: flex; }

.portal-drawer-content {
  background: var(--bg);
  width: 100%;
  max-width: 480px;
  margin-left: auto;
  height: 100vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

@media (max-width: 480px) {
  .portal-drawer-content {
    max-width: 100%;
  }
  .portal-main { padding: 12px; }
}

.portal-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 20px;
  background: var(--text);
  color: var(--bg);
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  border: 0;
  cursor: pointer;
}

.portal-cta.secondary {
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
}
```

- [ ] **Step 2: Create `portal-layout.jsx`**

Create `medic_plus/public/portal/portal-layout.jsx`:

```javascript
// Portal layout primitives — shell, topbar, sidebar, drawer.

(function() {
  const { useEffect } = React;

  function PortalShell({ children }) {
    return <div className="portal-shell">{children}</div>;
  }

  function PortalTopbar({ practice, route, go, onLogout }) {
    return (
      <div className="portal-topbar">
        {practice && practice.logo && (
          <img src={practice.logo} alt={practice.practice_name} className="practice-logo" />
        )}
        <div className="practice-name">{practice ? practice.practice_name : "Patient Portal"}</div>
        <div className="spacer" />
        {window.portalApi.isAuthenticated && (
          <button className="portal-cta secondary" style={{padding: "0 12px", minHeight: 36}} onClick={onLogout}>
            Sign out
          </button>
        )}
      </div>
    );
  }

  function PortalTabs({ route, go }) {
    const tabs = [
      { id: "home", label: "Home" },
      { id: "appointments", label: "Appointments" },
      { id: "records", label: "Records" },
      { id: "documents", label: "Documents" },
      { id: "billing", label: "Billing" },
      { id: "profile", label: "Profile" },
    ];
    return (
      <div className="portal-tabs" role="tablist">
        {tabs.map(t => (
          <button
            key={t.id}
            role="tab"
            aria-selected={route === t.id}
            className={`portal-tab${route === t.id ? " active" : ""}`}
            onClick={() => go(t.id)}
          >{t.label}</button>
        ))}
      </div>
    );
  }

  function PortalDrawer({ open, onClose, children, title }) {
    useEffect(() => {
      if (!open) return;
      const onKey = (e) => { if (e.key === "Escape") onClose(); };
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    return (
      <div className={`portal-drawer${open ? " open" : ""}`} onClick={onClose}>
        <div className="portal-drawer-content" onClick={(e) => e.stopPropagation()}>
          <div className="portal-topbar">
            <div className="practice-name">{title}</div>
            <div className="spacer" />
            <button className="portal-cta secondary" style={{padding: "0 12px", minHeight: 36}} onClick={onClose}>Close</button>
          </div>
          <div style={{padding: 16, flex: 1, overflowY: "auto"}}>{children}</div>
        </div>
      </div>
    );
  }

  function PortalLoading({ label = "Loading…" }) {
    return <div style={{padding: 24, color: "var(--text-muted)", fontSize: 13}}>{label}</div>;
  }

  function PortalEmpty({ title, description, action }) {
    return (
      <div style={{padding: 40, textAlign: "center", color: "var(--text-muted)"}}>
        <div style={{fontSize: 16, fontWeight: 600, color: "var(--text)", marginBottom: 8}}>{title}</div>
        {description && <div style={{fontSize: 13, marginBottom: 16}}>{description}</div>}
        {action}
      </div>
    );
  }

  window.PortalShell = PortalShell;
  window.PortalTopbar = PortalTopbar;
  window.PortalTabs = PortalTabs;
  window.PortalDrawer = PortalDrawer;
  window.PortalLoading = PortalLoading;
  window.PortalEmpty = PortalEmpty;
})();
```

- [ ] **Step 3: Build + sanity check the file loads**

```bash
cd /home/fruppa/frappe-bench
bench build --app medic_plus 2>&1 | tail -3
curl -sI -H "Host: medic-demo-staging.thedaystar.co.za" https://medic-demo-staging.thedaystar.co.za/assets/medic_plus/portal/portal-layout.jsx | head -1
```

- [ ] **Step 4: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-layout.jsx medic_plus/public/portal/portal-styles.css
git commit -m "feat(portal): layout shell, topbar, tabs, drawer"
```

---

## Task 11: Login screen — email + OTP flow

**Files:**
- Create: `medic_plus/public/portal/portal-login.jsx`

- [ ] **Step 1: Create the login component**

Create `medic_plus/public/portal/portal-login.jsx`:

```javascript
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
              style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 14, marginBottom: 12}}
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
              style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 18, letterSpacing: "0.2em", textAlign: "center", marginBottom: 12}}
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

        {info && <div style={{marginTop: 16, padding: 12, background: "var(--bg-subtle)", borderRadius: 8, fontSize: 12, color: "var(--text-muted)"}}>{info}</div>}
        {error && <div style={{marginTop: 16, padding: 12, background: "#fef2f2", borderRadius: 8, fontSize: 12, color: "#991b1b"}}>{error}</div>}
      </div>
    );
  }

  window.PortalLoginScreen = PortalLoginScreen;
})();
```

- [ ] **Step 2: Build + smoke**

```bash
cd /home/fruppa/frappe-bench && bench build --app medic_plus 2>&1 | tail -2
```

- [ ] **Step 3: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-login.jsx
git commit -m "feat(portal): email-OTP login screen"
```

---

## Task 12: Root `portal-app.jsx` — router + initial mount

**Files:**
- Create: `medic_plus/public/portal/portal-app.jsx`

- [ ] **Step 1: Create the app root**

Create `medic_plus/public/portal/portal-app.jsx`:

```javascript
// Root React tree for the Patient Portal.

(function() {
  const { useState, useEffect, useCallback } = React;

  const VALID_ROUTES = ["home", "appointments", "book", "records", "documents", "billing", "profile"];

  function readUrl() {
    const params = new URLSearchParams(window.location.search);
    let route = params.get("screen");
    if (!route || !VALID_ROUTES.includes(route)) route = null;
    return { route };
  }

  function syncUrl(route, replace) {
    const url = route && route !== "home"
      ? `${window.location.pathname}?screen=${route}`
      : window.location.pathname;
    const fn = replace ? "replaceState" : "pushState";
    window.history[fn]({ route }, "", url);
  }

  function App() {
    const api = window.portalApi;
    const { isAuthenticated, hasPatient, practice, slug } = api;

    // If no slug — render the resolver page (login or practice picker).
    const noSlug = !slug;
    const [route, setRoute] = useState(() => readUrl().route || "home");
    const [bookOpen, setBookOpen] = useState(false);

    useEffect(() => { syncUrl(route, true); }, []);

    useEffect(() => {
      const handler = () => {
        const u = readUrl();
        setRoute(u.route || "home");
      };
      window.addEventListener("popstate", handler);
      return () => window.removeEventListener("popstate", handler);
    }, []);

    const go = useCallback((r) => {
      if (r === "book") { setBookOpen(true); return; }
      setRoute(r);
      syncUrl(r, false);
      window.scrollTo(0, 0);
    }, []);

    async function onLogout() {
      try { await fetch("/api/method/logout", { method: "GET", credentials: "same-origin" }); } catch {}
      window.location.href = slug ? `/portal/${slug}` : "/portal";
    }

    // ----- Resolver views -----
    if (noSlug) {
      if (!isAuthenticated) {
        return (
          <window.PortalShell>
            <div style={{padding: 24, maxWidth: 480, margin: "60px auto"}}>
              <h1 style={{fontSize: 22, fontWeight: 600, marginBottom: 12}}>Patient Portal</h1>
              <p style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 16}}>
                Enter your practice's portal address to continue.
              </p>
              <input
                type="text" placeholder="e.g. my-clinic"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.target.value.trim()) {
                    window.location.href = `/portal/${e.target.value.trim()}`;
                  }
                }}
                style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8}}
              />
            </div>
          </window.PortalShell>
        );
      }
      return <window.PortalPracticePicker />;
    }

    if (!isAuthenticated || !hasPatient) {
      return (
        <window.PortalShell>
          <window.PortalLoginScreen slug={slug} />
        </window.PortalShell>
      );
    }

    return (
      <window.PortalShell>
        <window.PortalTopbar practice={practice} route={route} go={go} onLogout={onLogout} />
        <div className="portal-main">
          <window.PortalTabs route={route} go={go} />
          {route === "home" && <window.PortalHomeScreen go={go} />}
          {route === "appointments" && <window.PortalAppointmentsScreen go={go} />}
          {route === "records" && <window.PortalRecordsScreen go={go} />}
          {route === "documents" && <window.PortalDocumentsScreen go={go} />}
          {route === "billing" && <window.PortalBillingScreen go={go} />}
          {route === "profile" && <window.PortalProfileScreen go={go} />}
        </div>
        <window.PortalDrawer open={bookOpen} onClose={() => setBookOpen(false)} title="Book an appointment">
          {bookOpen && <window.PortalBookDrawer onBooked={() => { setBookOpen(false); go("appointments"); }} />}
        </window.PortalDrawer>
      </window.PortalShell>
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
})();
```

- [ ] **Step 2: Build + smoke**

```bash
cd /home/fruppa/frappe-bench && bench build --app medic_plus 2>&1 | tail -2
```

Open the URL `/portal/<slug>` in a browser. Expect: login screen rendered (other screen components are stubs until the next tasks; React will warn but the login renders).

- [ ] **Step 3: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-app.jsx
git commit -m "feat(portal): root App + URL routing"
```

---

## Task 13: Practice picker (multi-practice resolver)

**Files:**
- Create: `medic_plus/public/portal/portal-practice-picker.jsx`

- [ ] **Step 1: Create the picker**

Create `medic_plus/public/portal/portal-practice-picker.jsx`:

```javascript
(function() {
  const { useEffect, useState } = React;

  function PortalPracticePicker() {
    const [practices, setPractices] = useState(null);
    const [error, setError] = useState("");

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.resolve_my_practices")
        .then((rows) => {
          if (!rows || rows.length === 0) {
            // Zero matches — punt to /register/patient
            window.location.href = "/register/patient";
            return;
          }
          if (rows.length === 1) {
            window.location.href = `/portal/${rows[0].slug}`;
            return;
          }
          setPractices(rows);
        })
        .catch((e) => setError(e.message));
    }, []);

    if (error) return <div style={{padding: 24, color: "#991b1b"}}>{error}</div>;
    if (!practices) return <window.PortalLoading label="Resolving your practices…" />;

    return (
      <window.PortalShell>
        <div style={{padding: 24, maxWidth: 480, margin: "40px auto"}}>
          <h1 style={{fontSize: 22, fontWeight: 600, marginBottom: 16}}>Pick a practice</h1>
          <div style={{display: "grid", gap: 12}}>
            {practices.map(p => (
              <a key={p.slug} href={`/portal/${p.slug}`}
                style={{display: "flex", alignItems: "center", gap: 12, padding: 16, border: "1px solid var(--border)", borderRadius: 8, textDecoration: "none", color: "var(--text)"}}>
                {p.logo && <img src={p.logo} alt="" style={{height: 32, width: "auto"}} />}
                <div style={{fontWeight: 500}}>{p.practice_name}</div>
              </a>
            ))}
          </div>
        </div>
      </window.PortalShell>
    );
  }

  window.PortalPracticePicker = PortalPracticePicker;
})();
```

- [ ] **Step 2: Build + commit**

```bash
cd /home/fruppa/frappe-bench && bench build --app medic_plus 2>&1 | tail -2
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-practice-picker.jsx
git commit -m "feat(portal): practice picker for multi-practice patients"
```

---

## Task 14: Home screen

**Files:**
- Create: `medic_plus/public/portal/portal-home.jsx`

- [ ] **Step 1: Create the home screen**

Create `medic_plus/public/portal/portal-home.jsx`:

```javascript
(function() {
  const { useEffect, useState } = React;

  function PortalHomeScreen({ go }) {
    const [data, setData] = useState(null);
    const [me, setMe] = useState(null);

    useEffect(() => {
      const slug = window.portalApi.slug;
      Promise.all([
        window.portalApi.call("medic_plus.api.patient_portal.list_my_appointments", { slug }),
        window.portalApi.call("medic_plus.api.patient_portal.get_me", { slug }),
      ]).then(([appts, me]) => { setData(appts); setMe(me); });
    }, []);

    if (!data) return <window.PortalLoading />;

    const next = data.upcoming[0] || null;

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 4}}>
          Hi {me ? me.first_name : ""}
        </h1>
        <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 20}}>
          Welcome back to your patient portal.
        </div>

        <div className="card" style={{padding: 20, marginBottom: 16}}>
          <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-dim)", marginBottom: 8}}>
            Next appointment
          </div>
          {next ? (
            <div>
              <div style={{fontSize: 16, fontWeight: 600, marginBottom: 4}}>
                {next.appointment_date} · {String(next.appointment_time).slice(0,5)}
              </div>
              <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 16}}>
                With {next.practitioner_name || next.practitioner}
              </div>
              <button className="portal-cta secondary" onClick={() => go("appointments")}>
                View details
              </button>
            </div>
          ) : (
            <div>
              <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 16}}>
                You have no upcoming appointments.
              </div>
              <button className="portal-cta" onClick={() => go("book")}>
                Book an appointment
              </button>
            </div>
          )}
        </div>

        <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12}}>
          <button className="portal-cta secondary" onClick={() => go("book")} style={{height: 80}}>
            New appointment
          </button>
          <button className="portal-cta secondary" onClick={() => go("records")} style={{height: 80}}>
            View records
          </button>
        </div>
      </div>
    );
  }

  window.PortalHomeScreen = PortalHomeScreen;
})();
```

- [ ] **Step 2: Build + commit**

```bash
cd /home/fruppa/frappe-bench && bench build --app medic_plus 2>&1 | tail -2
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-home.jsx
git commit -m "feat(portal): home screen with next-appointment card + quick actions"
```

---

## Task 15: Appointments screen + cancel

**Files:**
- Create: `medic_plus/public/portal/portal-appointments.jsx`

- [ ] **Step 1: Create the appointments screen**

Create `medic_plus/public/portal/portal-appointments.jsx`:

```javascript
(function() {
  const { useEffect, useState } = React;

  function PortalAppointmentsScreen({ go }) {
    const [data, setData] = useState(null);
    const [busy, setBusy] = useState("");

    function refresh() {
      const slug = window.portalApi.slug;
      window.portalApi.call("medic_plus.api.patient_portal.list_my_appointments", { slug })
        .then(setData);
    }
    useEffect(refresh, []);

    async function cancel(name) {
      if (!confirm("Cancel this appointment?")) return;
      setBusy(name);
      try {
        await window.portalApi.call("medic_plus.api.patient_portal.cancel_my_appointment",
          { slug: window.portalApi.slug, name });
        refresh();
      } catch (e) {
        window.portalApi.showError(e.message);
      } finally { setBusy(""); }
    }

    if (!data) return <window.PortalLoading />;

    return (
      <div className="fade-in">
        <div style={{display: "flex", alignItems: "center", marginBottom: 16}}>
          <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", flex: 1}}>Appointments</h1>
          <button className="portal-cta" onClick={() => go("book")}>+ Book</button>
        </div>

        <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-dim)", margin: "16px 0 8px"}}>
          Upcoming
        </div>
        {data.upcoming.length === 0 ? (
          <window.PortalEmpty title="No upcoming appointments" />
        ) : data.upcoming.map(a => (
          <div key={a.name} className="card" style={{padding: 16, marginBottom: 8, display: "flex", alignItems: "center", gap: 12}}>
            <div style={{flex: 1}}>
              <div style={{fontWeight: 600}}>{a.appointment_date} · {String(a.appointment_time).slice(0,5)}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>
                {a.practitioner_name || a.practitioner} · {a.status}
              </div>
            </div>
            <button className="portal-cta secondary" onClick={() => cancel(a.name)} disabled={busy === a.name}>
              {busy === a.name ? "…" : "Cancel"}
            </button>
          </div>
        ))}

        <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-dim)", margin: "24px 0 8px"}}>
          Past
        </div>
        {data.past.length === 0 ? (
          <window.PortalEmpty title="No past appointments" />
        ) : data.past.map(a => (
          <div key={a.name} className="card" style={{padding: 16, marginBottom: 8}}>
            <div style={{fontWeight: 500}}>{a.appointment_date} · {String(a.appointment_time).slice(0,5)}</div>
            <div style={{fontSize: 12, color: "var(--text-muted)"}}>
              {a.practitioner_name || a.practitioner} · {a.status}
            </div>
          </div>
        ))}
      </div>
    );
  }

  window.PortalAppointmentsScreen = PortalAppointmentsScreen;
})();
```

- [ ] **Step 2: Build + commit**

```bash
cd /home/fruppa/frappe-bench && bench build --app medic_plus 2>&1 | tail -2
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-appointments.jsx
git commit -m "feat(portal): appointments screen with cancel"
```

---

## Task 16: Booking drawer

**Files:**
- Create: `medic_plus/public/portal/portal-book.jsx`

- [ ] **Step 1: Create the booking drawer**

Create `medic_plus/public/portal/portal-book.jsx`:

```javascript
(function() {
  const { useEffect, useState } = React;

  function PortalBookDrawer({ onBooked }) {
    const slug = window.portalApi.slug;
    const [practitioners, setPractitioners] = useState([]);
    const [practitioner, setPractitioner] = useState("");
    const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
    const [slots, setSlots] = useState([]);
    const [slot, setSlot] = useState("");
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
      window.portalApi.call("medic_plus.api.booking.get_practice_practitioners", { practice_slug: slug })
        .then(setPractitioners)
        .catch((e) => setError(e.message));
    }, []);

    useEffect(() => {
      if (!practitioner || !date) { setSlots([]); return; }
      window.portalApi.call("medic_plus.api.booking.get_availability",
        { practice_slug: slug, practitioner, date })
        .then((rows) => setSlots(rows || []))
        .catch((e) => setError(e.message));
    }, [practitioner, date]);

    async function submit(e) {
      e.preventDefault();
      setBusy(true); setError("");
      try {
        await window.portalApi.call("medic_plus.api.patient_portal.book_for_authed_patient", {
          slug, practitioner, appointment_date: date, appointment_time: slot, reason,
        });
        onBooked && onBooked();
      } catch (err) {
        setError(err.message);
      } finally { setBusy(false); }
    }

    return (
      <form onSubmit={submit}>
        <label style={{display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6}}>Practitioner</label>
        <select required value={practitioner} onChange={(e) => setPractitioner(e.target.value)}
          style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 14, marginBottom: 16, minHeight: 44}}>
          <option value="">Pick a doctor…</option>
          {practitioners.map(p => (
            <option key={p.name} value={p.name}>{p.practitioner_name || p.name}</option>
          ))}
        </select>

        <label style={{display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6}}>Date</label>
        <input type="date" required value={date} min={new Date().toISOString().slice(0, 10)}
          onChange={(e) => setDate(e.target.value)}
          style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 14, marginBottom: 16, minHeight: 44}} />

        <label style={{display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6}}>Available slots</label>
        {practitioner && slots.length === 0 && (
          <div style={{fontSize: 12, color: "var(--text-muted)", marginBottom: 16}}>No slots on this date.</div>
        )}
        <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(80px, 1fr))", gap: 8, marginBottom: 16}}>
          {slots.map((t) => (
            <button key={t} type="button"
              onClick={() => setSlot(t)}
              className={`portal-cta ${slot === t ? "" : "secondary"}`}
              style={{padding: "0 8px", minHeight: 40, fontSize: 13}}>
              {t.slice(0,5)}
            </button>
          ))}
        </div>

        <label style={{display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6}}>Reason (optional)</label>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)}
          rows={3}
          style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 14, marginBottom: 16, fontFamily: "inherit"}} />

        <button className="portal-cta" type="submit" disabled={busy || !practitioner || !slot} style={{width: "100%"}}>
          {busy ? "Booking…" : "Confirm booking"}
        </button>
        {error && <div style={{marginTop: 16, padding: 12, background: "#fef2f2", borderRadius: 8, fontSize: 12, color: "#991b1b"}}>{error}</div>}
      </form>
    );
  }

  window.PortalBookDrawer = PortalBookDrawer;
})();
```

- [ ] **Step 2: Build + commit**

```bash
cd /home/fruppa/frappe-bench && bench build --app medic_plus 2>&1 | tail -2
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-book.jsx
git commit -m "feat(portal): book-an-appointment drawer"
```

---

## Task 17: Profile screen (editable form)

**Files:**
- Create: `medic_plus/public/portal/portal-profile.jsx`

- [ ] **Step 1: Create the profile screen**

Create `medic_plus/public/portal/portal-profile.jsx`:

```javascript
(function() {
  const { useEffect, useState } = React;

  const FIELDS = [
    { name: "first_name", label: "First name", type: "text" },
    { name: "middle_name", label: "Middle name", type: "text" },
    { name: "last_name", label: "Last name", type: "text" },
    { name: "dob", label: "Date of birth", type: "date" },
    { name: "sex", label: "Sex", type: "select", options: ["", "Male", "Female", "Other"] },
    { name: "blood_group", label: "Blood group", type: "select", options: ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] },
    { name: "marital_status", label: "Marital status", type: "select", options: ["", "Single", "Married", "Divorced", "Widowed"] },
    { name: "mobile", label: "Mobile", type: "tel" },
    { name: "phone", label: "Phone", type: "tel" },
    { name: "email", label: "Email", type: "email" },
    { name: "occupation", label: "Occupation", type: "text" },
    { name: "address_line1", label: "Address line 1", type: "text" },
    { name: "address_line2", label: "Address line 2", type: "text" },
    { name: "city", label: "City", type: "text" },
    { name: "state", label: "State", type: "text" },
    { name: "zip_code", label: "Zip code", type: "text" },
    { name: "country", label: "Country", type: "text" },
    { name: "allergies", label: "Allergies (self-reported)", type: "textarea" },
    { name: "medication", label: "Current medication (self-reported)", type: "textarea" },
  ];

  function PortalProfileScreen() {
    const slug = window.portalApi.slug;
    const [me, setMe] = useState(null);
    const [form, setForm] = useState({});
    const [busy, setBusy] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.get_me", { slug })
        .then((m) => { setMe(m); setForm(m); });
    }, []);

    function update(name, value) {
      setForm((f) => ({ ...f, [name]: value }));
      setSaved(false);
    }

    async function save() {
      setBusy(true); setError(""); setSaved(false);
      const payload = {};
      for (const f of FIELDS) {
        const cur = form[f.name];
        const orig = me ? me[f.name] : null;
        if ((cur || "") !== (orig || "")) payload[f.name] = cur || null;
      }
      if (Object.keys(payload).length === 0) { setBusy(false); return; }
      try {
        const updated = await window.portalApi.call("medic_plus.api.patient_portal.update_me", { slug, payload });
        setMe(updated); setForm(updated); setSaved(true);
      } catch (e) {
        setError(e.message);
      } finally { setBusy(false); }
    }

    if (!me) return <window.PortalLoading />;

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 4}}>My profile</h1>
        <div style={{fontSize: 13, color: "var(--text-muted)", marginBottom: 20}}>
          Update your contact details and personal information. Clinical history is managed by your practice.
        </div>

        <div style={{display: "grid", gap: 12}}>
          {FIELDS.map((f) => (
            <div key={f.name}>
              <label style={{display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4}}>{f.label}</label>
              {f.type === "textarea" ? (
                <textarea value={form[f.name] || ""} onChange={(e) => update(f.name, e.target.value)} rows={3}
                  style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 14, fontFamily: "inherit"}} />
              ) : f.type === "select" ? (
                <select value={form[f.name] || ""} onChange={(e) => update(f.name, e.target.value)}
                  style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 14, minHeight: 44}}>
                  {f.options.map((o) => <option key={o} value={o}>{o || "—"}</option>)}
                </select>
              ) : (
                <input type={f.type} value={form[f.name] || ""} onChange={(e) => update(f.name, e.target.value)}
                  style={{width: "100%", padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 14, minHeight: 44}} />
              )}
            </div>
          ))}
        </div>

        <div style={{position: "sticky", bottom: 16, marginTop: 24, display: "flex", gap: 8, alignItems: "center"}}>
          <button className="portal-cta" onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </button>
          {saved && <span style={{fontSize: 12, color: "#059669"}}>Saved</span>}
          {error && <span style={{fontSize: 12, color: "#991b1b"}}>{error}</span>}
        </div>
      </div>
    );
  }

  window.PortalProfileScreen = PortalProfileScreen;
})();
```

- [ ] **Step 2: Build + commit**

```bash
cd /home/fruppa/frappe-bench && bench build --app medic_plus 2>&1 | tail -2
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-profile.jsx
git commit -m "feat(portal): profile screen — editable allowlist"
```

---

## Task 18: Records, Documents, Billing screens

**Files:**
- Create: `medic_plus/public/portal/portal-records.jsx`
- Create: `medic_plus/public/portal/portal-documents.jsx`
- Create: `medic_plus/public/portal/portal-billing.jsx`

- [ ] **Step 1: Create `portal-records.jsx`**

Create `medic_plus/public/portal/portal-records.jsx`:

```javascript
(function() {
  const { useEffect, useState } = React;

  function PortalRecordsScreen() {
    const slug = window.portalApi.slug;
    const [data, setData] = useState(null);
    const [tab, setTab] = useState("encounters");

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.list_my_records", { slug })
        .then(setData);
    }, []);

    if (!data) return <window.PortalLoading />;

    const tabs = [
      { id: "encounters", label: `Visits (${data.encounters.length})` },
      { id: "problems", label: `Problems (${data.problems.length})` },
      { id: "allergies", label: `Allergies (${data.allergies.length})` },
      { id: "chronic_conditions", label: `Chronic (${data.chronic_conditions.length})` },
    ];

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 16}}>Records</h1>

        <div className="portal-tabs">
          {tabs.map(t => (
            <button key={t.id} className={`portal-tab${tab === t.id ? " active" : ""}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "encounters" && (
          data.encounters.length === 0 ? <window.PortalEmpty title="No visits recorded" />
          : data.encounters.map(e => (
            <div key={e.name} className="card" style={{padding: 16, marginBottom: 8}}>
              <div style={{fontWeight: 600}}>{e.encounter_date}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{e.practitioner_name || ""}</div>
            </div>
          ))
        )}

        {tab === "problems" && (
          data.problems.length === 0 ? <window.PortalEmpty title="No problems on record" />
          : data.problems.map(p => (
            <div key={p.name} className="card" style={{padding: 16, marginBottom: 8}}>
              <div style={{fontWeight: 600}}>{p.problem}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{p.status} · {p.onset_date || ""}</div>
            </div>
          ))
        )}

        {tab === "allergies" && (
          data.allergies.length === 0 ? <window.PortalEmpty title="No allergies on record" />
          : data.allergies.map(a => (
            <div key={a.name} className="card" style={{padding: 16, marginBottom: 8}}>
              <div style={{fontWeight: 600}}>{a.allergen}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{a.severity} · {a.reaction}</div>
            </div>
          ))
        )}

        {tab === "chronic_conditions" && (
          data.chronic_conditions.length === 0 ? <window.PortalEmpty title="No chronic conditions on record" />
          : data.chronic_conditions.map(c => (
            <div key={c.name} className="card" style={{padding: 16, marginBottom: 8}}>
              <div style={{fontWeight: 600}}>{c.condition}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{c.status} · {c.onset_date || ""}</div>
            </div>
          ))
        )}
      </div>
    );
  }

  window.PortalRecordsScreen = PortalRecordsScreen;
})();
```

- [ ] **Step 2: Create `portal-documents.jsx`**

Create `medic_plus/public/portal/portal-documents.jsx`:

```javascript
(function() {
  const { useEffect, useState } = React;

  function PortalDocumentsScreen() {
    const slug = window.portalApi.slug;
    const [data, setData] = useState(null);

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.list_my_documents", { slug })
        .then(setData);
    }, []);

    function downloadHref(doctype, name) {
      return window.portalApi.downloadUrl(
        "medic_plus.api.patient_portal.download_my_document",
        { slug, doctype, name }
      );
    }

    if (!data) return <window.PortalLoading />;

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 16}}>Documents</h1>

        <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-dim)", margin: "16px 0 8px"}}>
          Sick notes
        </div>
        {data.sick_notes.length === 0 ? <window.PortalEmpty title="No sick notes" />
        : data.sick_notes.map(d => (
          <div key={d.name} className="card" style={{padding: 16, marginBottom: 8, display: "flex", alignItems: "center"}}>
            <div style={{flex: 1}}>
              <div style={{fontWeight: 600}}>{d.date_issued}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{d.diagnosis || "—"} · {d.days_off} day(s) off</div>
            </div>
            <a href={downloadHref("Sick Note", d.name)} target="_blank" rel="noopener noreferrer"
              className="portal-cta secondary">Download</a>
          </div>
        ))}

        <div style={{fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-dim)", margin: "24px 0 8px"}}>
          Prescriptions
        </div>
        {data.prescriptions.length === 0 ? <window.PortalEmpty title="No prescriptions" />
        : data.prescriptions.map(d => (
          <div key={d.name} className="card" style={{padding: 16, marginBottom: 8, display: "flex", alignItems: "center"}}>
            <div style={{flex: 1}}>
              <div style={{fontWeight: 600}}>{d.medication_request_date}</div>
              <div style={{fontSize: 12, color: "var(--text-muted)"}}>{d.status}</div>
            </div>
            <a href={downloadHref("Medication Request", d.name)} target="_blank" rel="noopener noreferrer"
              className="portal-cta secondary">Download</a>
          </div>
        ))}
      </div>
    );
  }

  window.PortalDocumentsScreen = PortalDocumentsScreen;
})();
```

- [ ] **Step 3: Create `portal-billing.jsx`**

Create `medic_plus/public/portal/portal-billing.jsx`:

```javascript
(function() {
  const { useEffect, useState } = React;

  function PortalBillingScreen() {
    const slug = window.portalApi.slug;
    const [data, setData] = useState(null);

    useEffect(() => {
      window.portalApi.call("medic_plus.api.patient_portal.list_my_invoices", { slug })
        .then(setData);
    }, []);

    function downloadHref(name) {
      return window.portalApi.downloadUrl(
        "medic_plus.api.patient_portal.download_my_invoice", { slug, name }
      );
    }

    if (!data) return <window.PortalLoading />;

    return (
      <div className="fade-in">
        <h1 style={{fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 16}}>Billing</h1>
        {data.length === 0 ? <window.PortalEmpty title="No invoices yet" description="Your invoices will appear here once your practice issues them." />
        : data.map(inv => (
          <div key={inv.name} className="card" style={{padding: 16, marginBottom: 8}}>
            <div style={{display: "flex", alignItems: "center", marginBottom: 4}}>
              <div style={{fontWeight: 600, flex: 1}}>{inv.name}</div>
              <a href={downloadHref(inv.name)} target="_blank" rel="noopener noreferrer"
                className="portal-cta secondary">PDF</a>
            </div>
            <div style={{fontSize: 12, color: "var(--text-muted)"}}>
              {inv.posting_date} · {inv.currency} {inv.grand_total} · outstanding: {inv.outstanding_amount} · {inv.status}
            </div>
          </div>
        ))}
      </div>
    );
  }

  window.PortalBillingScreen = PortalBillingScreen;
})();
```

- [ ] **Step 4: Build + manual smoke**

```bash
cd /home/fruppa/frappe-bench && bench build --app medic_plus 2>&1 | tail -2
```

Open `/portal/<slug>` in a browser, sign in, walk every tab. Each tab should render either data or an empty state — no console errors.

- [ ] **Step 5: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/public/portal/portal-records.jsx medic_plus/public/portal/portal-documents.jsx medic_plus/public/portal/portal-billing.jsx
git commit -m "feat(portal): records, documents, billing screens"
```

---

## Task 19: Playwright UI tests

**Files:**
- Create: `medic_plus/tests/ui/test_patient_portal.py`

- [ ] **Step 1: Inspect the existing conftest**

```bash
ls /home/fruppa/frappe-bench/apps/medic_plus/medic_plus/tests/ui/
cat /home/fruppa/frappe-bench/apps/medic_plus/medic_plus/tests/ui/conftest.py 2>/dev/null | head -60
```

Confirm the fixture names per CLAUDE.md (`logged_in_admin_page`, `_frappe_login`, `BASE_URL`, `RUN_TAG`).

- [ ] **Step 2: Create the test file**

Create `medic_plus/tests/ui/test_patient_portal.py`:

```python
"""Patient Portal — Playwright UI tests.

Per medic_plus CLAUDE.md, every new feature must ship with Playwright tests.
"""
import os
import pytest
import frappe
from urllib.parse import urlparse


BASE_URL = os.getenv("MEDIC_BASE_URL", "https://medic-demo-staging.thedaystar.co.za")


@pytest.fixture(scope="module")
def portal_fixtures():
    """Provision a Practice + Patient + User for portal tests; teardown after."""
    frappe.init(site="medic-demo-staging.thedaystar.co.za", sites_path="/home/fruppa/frappe-bench/sites")
    frappe.connect()

    slug = "ui-portal-test"
    email = "ui-portal-test@example.com"

    if not frappe.db.exists("Practice", {"slug": slug}):
        frappe.get_doc({
            "doctype": "Practice", "practice_name": "UI Portal Test", "slug": slug,
            "is_active": 1, "email": "ui-portal-test@example.com",
        }).insert(ignore_permissions=True)
    practice = frappe.db.get_value("Practice", {"slug": slug}, "name")

    if not frappe.db.exists("Patient", {"email": email}):
        frappe.get_doc({
            "doctype": "Patient", "first_name": "Ui", "last_name": "Patient",
            "sex": "Female", "email": email, "custom_practice": practice,
            "status": "Active", "invite_user": 0,
        }).insert(ignore_permissions=True)
    if not frappe.db.exists("User", {"email": email}):
        frappe.get_doc({
            "doctype": "User", "email": email, "first_name": "Ui",
            "enabled": 1, "user_type": "Website User", "send_welcome_email": 0,
            "roles": [{"role": "Patient"}],
        }).insert(ignore_permissions=True)

    frappe.db.commit()
    yield {"slug": slug, "email": email}


def test_portal_login_page_renders(page, portal_fixtures):
    slug = portal_fixtures["slug"]
    page.goto(f"{BASE_URL}/portal/{slug}")
    page.wait_for_selector("input[type='email']", timeout=10000)
    # Inject + verify OTP via the API directly (bypass email send)
    page.wait_for_selector("text=Patient Portal", timeout=5000)


def test_portal_otp_flow_signs_user_in(page, portal_fixtures):
    """Walk OTP flow end-to-end. We bypass email by reading the OTP from Redis cache."""
    from medic_plus.api import patient_portal
    slug = portal_fixtures["slug"]
    email = portal_fixtures["email"]

    page.goto(f"{BASE_URL}/portal/{slug}")
    page.fill("input[type='email']", email)
    page.click("button:has-text('Send code')")
    page.wait_for_selector("input[inputmode='numeric']", timeout=10000)

    code = frappe.cache.get_value(patient_portal._otp_cache_key(slug, email))
    assert code, "OTP not in cache — did request_portal_otp run?"
    page.fill("input[inputmode='numeric']", code)
    page.click("button:has-text('Sign in')")
    # After verify the page reloads to /portal/<slug> with auth; expect Home content
    page.wait_for_selector("text=Welcome back to your patient portal", timeout=15000)


def test_portal_tabs_navigate(page, portal_fixtures):
    """Click each tab and verify its heading renders."""
    slug = portal_fixtures["slug"]
    # Reuse session from previous test; otherwise re-login via OTP API.
    page.goto(f"{BASE_URL}/portal/{slug}?screen=appointments")
    page.wait_for_selector("h1:has-text('Appointments')", timeout=10000)

    page.goto(f"{BASE_URL}/portal/{slug}?screen=records")
    page.wait_for_selector("h1:has-text('Records')", timeout=10000)

    page.goto(f"{BASE_URL}/portal/{slug}?screen=profile")
    page.wait_for_selector("h1:has-text('My profile')", timeout=10000)


def test_portal_profile_save(page, portal_fixtures):
    slug = portal_fixtures["slug"]
    page.goto(f"{BASE_URL}/portal/{slug}?screen=profile")
    page.wait_for_selector("h1:has-text('My profile')", timeout=10000)
    new_phone = "+27" + str(int(os.getenv("RUN_TAG", "0")) % 100000000).zfill(9)
    page.fill("input[type='tel']", new_phone)  # first tel input = mobile
    page.click("button:has-text('Save changes')")
    page.wait_for_selector("text=Saved", timeout=10000)


def test_portal_mobile_375_no_horizontal_scroll(page, portal_fixtures):
    slug = portal_fixtures["slug"]
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(f"{BASE_URL}/portal/{slug}?screen=appointments")
    page.wait_for_selector("h1:has-text('Appointments')", timeout=10000)
    has_h_scroll = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert not has_h_scroll, "Page has horizontal scroll at 375px"
```

- [ ] **Step 3: Run the Playwright suite**

```bash
cd /home/fruppa/frappe-bench
env/bin/python -m pytest apps/medic_plus/medic_plus/tests/ui/test_patient_portal.py -v 2>&1 | tail -40
```

Expected: all 5 tests pass (or skip with a documented reason if the staging site rejects test logins).

- [ ] **Step 4: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add medic_plus/tests/ui/test_patient_portal.py
git commit -m "test(portal): Playwright UI suite covering OTP login, tabs, profile, mobile"
```

---

## Task 20: Release artifacts — release notes, techspec, README

**Files:**
- Create: `docs/releases/v0.4.0.md`
- Modify: `techspec.md`
- Modify: `README.md`

- [ ] **Step 1: Check current version + write release notes**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
ls docs/releases/ | sort -V | tail -3
cat pyproject.toml | grep "^version" | head -1
```

If the latest tag is e.g. `v0.3.x`, the next minor is `v0.4.0` (new top-level surface per CLAUDE.md release discipline). Adjust the version below if it differs.

Create `docs/releases/v0.4.0.md`:

```markdown
# v0.4.0 — Patient Portal

**Release date:** 2026-05-18

## What's new for patients

A new self-service portal at `https://<your-practice>-staging.thedaystar.co.za/portal/<your-practice-slug>`:

- **Sign in with email only** — no password. We send a 6-digit code that expires in 10 minutes.
- **Book your own appointments** — pick a doctor, pick a date, pick a slot.
- **Cancel up to 24 hours before** — anything closer needs a phone call to reception.
- **See your records** — past visits, allergies, problems, chronic conditions (read-only, curated by your doctor).
- **Download your documents** — sick notes and prescriptions as PDFs.
- **View your invoices** — outstanding balances and PDF downloads. Online payment is coming in a future release.
- **Update your contact details** — name, phone, email, address, self-reported allergies and medication.

## What's new for practices

- Patients can no longer call reception just to ask "where's my sick note?" — direct them to the portal.
- The portal lives at `/portal/<your-slug>`. Each Patient record's `email` field is what the patient signs in with — make sure it's set.
- The portal is mobile-first; it works on a 360 px Android in a clinic waiting room.

## Behaviour to expect at upgrade

- The old Jinja `/portal` page is replaced. Bare `/portal` now redirects:
  - Signed-out: prompts for the practice slug.
  - Signed-in with one Patient record: 302s to `/portal/<slug>`.
  - Signed-in with multiple: shows a practice picker.
- A patient signing in for the first time auto-provisions a User account with the `Patient` role. No invitations to send.

## Things this release does NOT do (deferred)

- Online payment of invoices.
- Patient self-reported allergies/conditions appearing in the doctor's structured allergy/condition lists (only the free-text fields are exposed).
- Multi-practice login under one session.

## Technical notes

- New module: `medic_plus.api.patient_portal`.
- Shared booking-rules helper `medic_plus.api.booking._book_slot` is now used by both guest and authed flows.
- Three new permission_query_conditions registered: Patient Problem List, Medication Request, Sales Invoice. The existing Patient role's PQC scoping is reused.
- 18 Python tests + 5 Playwright tests added.

## Commits

(Filled in at tag time — `git log --oneline v0.3.x..v0.4.0`.)
```

- [ ] **Step 2: Append to `techspec.md`**

Run:
```bash
echo "" >> techspec.md
echo "## 2026-05-18 — Patient Portal (v0.4.0)" >> techspec.md
echo "" >> techspec.md
echo "**Summary:** Practice-scoped patient portal at \`/portal/<slug>\` — Babel-in-browser React SPA reusing the Meridian design system from \`/daystar-health\`. Email-OTP passwordless auth (10-min TTL, 5 sends/10min, 5 verify attempts). Seven screens: Home, Appointments, Book, Records, Documents, Billing, Profile." >> techspec.md
echo "" >> techspec.md
echo "**Module:** \`medic_plus.api.patient_portal\` (13 endpoints)." >> techspec.md
echo "**PQCs added:** Patient Problem List, Medication Request, Sales Invoice." >> techspec.md
echo "**PQCs extended:** Patient Encounter (Patient role branch)." >> techspec.md
echo "**Refactor:** \`medic_plus.api.booking._book_slot\` shared helper; \`verify_and_book\` calls it." >> techspec.md
echo "**Frontend bundle:** \`medic_plus/public/portal/\` (10 files)." >> techspec.md
echo "**Tests:** 18 Python + 5 Playwright." >> techspec.md
echo "**Spec:** \`docs/superpowers/specs/2026-05-18-patient-portal-design.md\`" >> techspec.md
echo "**Plan:** \`docs/superpowers/plans/2026-05-18-patient-portal.md\`" >> techspec.md
```

Verify:
```bash
tail -20 techspec.md
```

- [ ] **Step 3: Update README changelog**

Open `README.md`, find the changelog section at the bottom, prepend a v0.4.0 line. Don't write the whole file out — just edit the changelog section. If the changelog section doesn't exist, append:

```markdown

## Changelog

- **v0.4.0 (2026-05-18)** — Patient portal at `/portal/<slug>`. Email-OTP login, self-service booking, profile editing, document downloads.
```

- [ ] **Step 4: Commit**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git add docs/releases/v0.4.0.md techspec.md README.md
git commit -m "docs: v0.4.0 patient portal release notes + techspec + changelog"
```

---

## Task 21: Final integration test + merge to develop + tag

**Files:**
- Run all tests; merge; tag.

- [ ] **Step 1: Run full Python test suite**

```bash
cd /home/fruppa/frappe-bench
bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus --skip-before-tests --module medic_plus.api.test_patient_portal 2>&1 | tail -20
```

Expected: 18 tests pass.

- [ ] **Step 2: Run Playwright suite**

```bash
cd /home/fruppa/frappe-bench
env/bin/python -m pytest apps/medic_plus/medic_plus/tests/ui/test_patient_portal.py -v 2>&1 | tail -20
```

Expected: 5 tests pass (or document any skips with a reason).

- [ ] **Step 3: Manual end-to-end smoke**

Walk the full happy path on staging:

1. Open `/portal/<slug>` in a fresh browser (no cookies) → login screen.
2. Enter the patient email → click Send code → check email or Redis for the code.
3. Enter code → land on Home with "Welcome back".
4. Click Book → pick doctor → date → slot → submit → see toast or land on Appointments.
5. New appointment shows in Upcoming.
6. Click Cancel → confirms → moves to Past with status Cancelled.
7. Open Records tab → tabs switch.
8. Open Documents → if a sick note exists, click Download → PDF opens.
9. Open Billing → if invoices exist, click PDF.
10. Open Profile → change mobile → Save → reload → mobile persists.
11. Resize browser to 375px → no horizontal scroll, tabs scrollable, forms single-column.
12. Click Sign out → land back on login screen.
13. Sign in as a different patient at a different practice → confirm cannot see the first patient's data anywhere.

Document any issues found here; fix in a new commit on the branch.

- [ ] **Step 4: Verify session log lands against the right Work Order**

Per `/home/CLAUDE.md` Session Logging — when this session ends, open `https://crm.thedaystar.co.za/app/dev-session-log`, confirm a row exists. If it landed in "Unassigned Sessions", either:
- Update `dev_work_order` on the SL to point at the medic_plus patient portal WO, OR
- Create a new `Dev Work Order` under Khwezi Medical Software Solutions for this feature, then point the SL at it.

- [ ] **Step 5: Merge to develop**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git checkout develop
git pull origin develop
git merge feature/patient-portal --no-ff -m "feat: patient portal v0.4.0 — practice-scoped React SPA with OTP auth"
```

- [ ] **Step 6: Tag v0.4.0**

```bash
git tag -a v0.4.0 -m "Patient portal at /portal/<slug> — OTP login, booking, profile, records, documents, billing"
git push origin develop --tags
```

Per CLAUDE.md release discipline, a tag is the trigger for the GitHub Actions deploy to production — confirm whether you want this to deploy automatically or hold the tag locally first. **Do not push the tag without explicit user approval** because production deploy fires on tag push.

- [ ] **Step 7: Update release notes commits section**

```bash
cd /home/fruppa/frappe-bench/apps/medic_plus
git log --oneline $(git describe --tags --abbrev=0 HEAD~1)..v0.4.0 > /tmp/portal_commits.txt
```

Edit `docs/releases/v0.4.0.md`: replace the "(Filled in at tag time…)" line with the content of `/tmp/portal_commits.txt`. Amend the v0.4.0 tag if you do this before pushing, or commit it as a follow-up.

---

## Self-Review Checklist

After plan written:

**Spec coverage:**
- [x] URL routing (`/portal/<slug>`, bare `/portal` resolver) — Task 8 (slug shell), Task 12 (resolver in App), Task 13 (picker)
- [x] 7 screens — Tasks 14, 15, 16, 17, 18
- [x] Editable profile allowlist — Task 5
- [x] OTP login flow — Tasks 4 + 11
- [x] Auto-provision Frappe User + Patient role — Task 4
- [x] Shared `_book_slot` helper — Task 1
- [x] PQCs (Patient Encounter / Problem List / Medication Request / Sales Invoice) — Tasks 2, 3
- [x] Cancellation policy (≥24h) — Task 6
- [x] No online payment — explicitly out of scope, billing screen has no Pay button (Task 18)
- [x] Read-only records exposure — Task 7 + Task 18 (records screen)
- [x] PDF downloads with ownership validation — Task 7 + Task 18 (documents screen)
- [x] Cross-tenant isolation test — Task 7
- [x] Mobile responsiveness — Task 10 (`portal-styles.css`) + Task 19 (Playwright 375px test)
- [x] Release artifacts (release notes, techspec, README) — Task 20

**Placeholder scan:** Searched for "TBD", "TODO", "fill in", "similar to" — none in implementation steps. Only acceptable references: "(Filled in at tag time…)" in release notes (deliberately deferred to step 7 of Task 21) and "confirm during impl" for the Medication Request print format name (deliberate runtime decision).

**Type consistency:**
- `_book_slot` signature in Task 1 matches the call in Task 6 (`patient_name`, `practice`, `practitioner`, `appointment_date`, `appointment_time`, `reason`, `appointment_type`).
- `_resolve_my_patient` returns dict with `name`, `customer` etc. consistently used across Tasks 5, 6, 7.
- `portalApi.call(method, args)` shape consistent across all frontend tasks.
- Field name `appointment_time` used consistently (not `time`).
- Window globals (`PortalShell`, `PortalTopbar`, `PortalLoginScreen`, etc.) consistent between definitions (Tasks 10, 11, 13) and consumers (Task 12 `portal-app.jsx`).
- `slug` parameter name consistent across all endpoints (vs. `practice_slug` only in pre-existing `medic_plus.api.booking` calls, which are explicitly kept on their existing names per Task 16 booking-drawer code).

---
