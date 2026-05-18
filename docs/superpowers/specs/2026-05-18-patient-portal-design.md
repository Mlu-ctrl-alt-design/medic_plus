# Patient Portal — Design Spec

**Date:** 2026-05-18
**App:** `medic_plus`
**Site:** `medic-demo-staging.thedaystar.co.za`
**Status:** Approved for planning

## Summary

A patient-facing React SPA mounted at `/portal/<slug>` that reuses the Meridian design system from `/daystar-health`. Patients authenticate via passwordless email OTP, book appointments with practitioners in their practice, manage their own profile, view records and documents, and see their invoices. The portal is practice-scoped: one Patient record per practice, one URL per practice. The existing Jinja `/portal` is replaced; bare `/portal` becomes a resolver that 302s logged-in patients to the right slug.

## Goals

- Patients can sign in without a password and reach the portal in under a minute.
- Patients can book, cancel, and reschedule appointments without contacting reception.
- Patients can view their own clinical records (read-only) and download submitted sick notes and prescriptions as PDFs.
- Patients can edit a curated subset of their Patient record (contact + demographics + self-reported allergies/medication).
- Cross-tenant isolation: a Patient at Practice A cannot read anything belonging to Practice B, enforced by Permission Query Conditions and re-validated in endpoints.

## Non-goals

- Online payment of invoices (deferred).
- Self-reported clinical edits beyond free-text allergies/medication (no patient-curated `Patient Allergy` rows in MVP).
- POPIA two-sided OTP unmask flow (stays doctor-side).
- Multi-practice login under one session (each practice login is its own session).
- Cross-practice consolidated Patient record (would require PQC refactor; out of scope).

## Architecture decisions

| Decision | Choice | Rationale |
|---|---|---|
| Patient ↔ practice scoping | Practice-scoped portal at `/portal/<slug>` | Matches existing `/book?practice=<slug>` convention; no PQC refactor |
| Authentication | Email OTP, passwordless, auto-provision Frappe User on first verify | Best UX for low-frequency users; reuses booking OTP infra |
| Feature scope | Full patient parity (7 screens) | User's call — Home / Appointments / Book / Records / Documents / Billing / Profile |
| Legacy `/portal` | Replace + resolver redirect from bare `/portal` | Cheap; old email links keep working |
| Authed booking | New endpoint `book_for_authed_patient`; shared rules helper with guest flow | Avoids divergent booking-rules implementations |
| Records exposure | Encounter list + Problem List + Allergies + Chronic Conditions, read-only | Doctypes already exist; patient self-curation deferred |
| Billing | Read-only list of Sales Invoices with PDF download; no payment | Online payment deferred per user decision |
| Cancellation policy | Cancel allowed iff `appointment_date + appointment_time − now() ≥ 24h` | Confirmed by user |
| Frontend stack | Babel-in-browser React, same pattern as `/daystar-health` | Consistency with existing SPA; no new build pipeline |
| Asset bundle | Separate `medic_plus/public/portal/` directory | Doctor SPA bundle is untouched; shared CSS reused |
| Role | Reuse the existing `Patient` role | `api/permissions.py` already implements `Patient`-role PQC branches via `_get_patient_name_for_user` (lines 49–115). A new role would duplicate this. |

## URL & routing

- **`/portal`** — resolver. Behavior:
  - Guest → renders a minimal "Enter your practice address" page (input → form submits to `/portal/<slug>`). No practice list disclosure.
  - Logged-in `Patient Portal User` with exactly one Patient record → 302 to `/portal/<slug>`.
  - Logged-in user with multiple Patient records → renders practice picker fed by `resolve_my_practices`.
  - Logged-in user with zero Patient records → renders "No patient account found at any practice on this platform" with a link to `/register/patient`.
- **`/portal/<slug>`** — main SPA shell. Always renders the React app; the app handles its own internal routing for screens, login, and OTP.
- **`/portal/<slug>?screen=<x>&drawer=<y>&id=<z>`** — internal SPA routing pattern, mirroring `/daystar-health`.
- The existing Jinja `index.html` / `index.py` at `medic_plus/www/portal/` are replaced by a Jinja shell that boots the React SPA. No HTML rendered server-side beyond the shell + boot context.

## Screens

| Screen | Default? | Contents |
|---|---|---|
| `home` | ✅ | Next appointment card, two big quick-action buttons (Book / Records), unread-document badge, practice name + logo header |
| `appointments` | | Two-section list: Upcoming, Past. Each row shows date/time, practitioner, status. Upcoming rows have Cancel (≥24h) and Reschedule (= cancel + book in new drawer). |
| `book` | | Drawer-based flow: pick practitioner → pick date (Meridian date-picker) → pick slot (calls `get_availability`) → reason free-text → confirm → success state. Mirrors doctor-side `MNewVisitDrawer`. |
| `records` | | Tabbed view: Encounters / Problems / Allergies / Chronic Conditions. Each tab is a list; tapping an item opens a read-only detail drawer. |
| `documents` | | Two-section list: Sick Notes (submitted), Prescriptions (Medication Request, submitted). Each row has a "Download PDF" button → `download_my_document`. |
| `billing` | | List of Sales Invoices where `customer == Patient.customer`. Columns: invoice no, date, total, outstanding, status. Download PDF. No "Pay now" button. |
| `profile` | | Form mapped to editable Patient fields (see §Profile). Inline save bar; autosave on blur or explicit "Save" button. Read-only fields rendered as static text with lock icon. |

Auxiliary screens (live inside the SPA shell, not separate routes):

- `login` — email input → "Send code" → OTP input → "Verify"
- `practice-picker` — only when `resolve_my_practices` returns >1
- `error` — generic catch-all

## Profile — editable mapping

**Patient-editable** (PATCH via `update_me`):

`first_name`, `middle_name`, `last_name`, `dob`, `sex`, `mobile`, `phone`, `email`, `blood_group`, `marital_status`, `occupation`, `address_line1`, `address_line2`, `city`, `state`, `zip_code`, `country`, `allergies` (free-text), `medication` (free-text), `custom_preferred_language`, `custom_ai_consent`.

**Read-only / hidden:**

`name`, `custom_practice`, `customer`, `medical_history`, `surgical_history`, `tobacco_*`, `alcohol_*`, `surrounding_factors`, `other_risk_factors`, structured `Patient Allergy` / `Patient Chronic Condition` / `Patient Problem List` rows, `custom_sa_id_number` (POPIA-masked — displayed as `••• 1234` with no unmask affordance in patient portal).

`update_me` rejects any payload key not on the editable allowlist with HTTP 400; defense-in-depth, not just relying on the UI to omit them.

## Authentication

- **`request_portal_otp(slug, email)`** (`allow_guest=True`)
  - Validates practice slug; verifies `email` matches at least one Patient record at that practice.
  - Rate-limit: 5 requests per email/slug per 10 minutes (cache key `portal_otp_attempt:{slug}:{email}`).
  - Generates 6-digit code, stores in cache key `portal_otp:{slug}:{email}` with 10-minute TTL.
  - Sends OTP email via `frappe.sendmail` (subject branded with practice name).
  - Returns `{ok: true}` regardless of whether the email matches a Patient — prevents email enumeration. The 5-per-10-min rate-limit applies.
- **`verify_portal_otp(slug, email, code)`** (`allow_guest=True`)
  - Validates code against cache, single-use (deletes on success).
  - On success:
    - If no Frappe User exists with `email`, auto-provision: `enabled=1`, `send_welcome_email=0`, `user_type=Website User`, no password.
    - Add role `Patient` if not present.
    - Call `frappe.local.login_manager.login_as(email)` to mint session.
  - Returns `{ok: true, csrf_token, slug}`. Frontend stores csrf in `window.portalApi`.
- **OTP constants** (mirror `api/booking.py`):
  - 6 digits, numeric only
  - 10 min TTL
  - 5 verify attempts per code
  - 5 send requests per email/slug per 10 min
- **Logout**: built-in `/api/method/logout`.

## API surface — `medic_plus.api.patient_portal`

| Endpoint | Guest? | Returns | Notes |
|---|---|---|---|
| `request_portal_otp(slug, email)` | ✅ | `{ok}` | Always returns ok; rate-limited |
| `verify_portal_otp(slug, email, code)` | ✅ | `{ok, csrf_token, slug}` | Mints session + auto-provisions User |
| `resolve_my_practices()` | | `[{slug, practice_name, logo}]` | For multi-practice patients |
| `get_boot(slug)` | | `{patient_id, patient_name, practice: {...}, role_flags: {...}}` | Initial SPA boot context |
| `get_me(slug)` | | `{...patient...}` | Editable + read-only-but-visible fields; masks SA ID |
| `update_me(slug, payload)` | | `{ok, patient}` | Allowlist enforced server-side |
| `list_my_appointments(slug)` | | `{upcoming: [...], past: [...]}` | Limit 20 past |
| `cancel_my_appointment(slug, name)` | | `{ok}` | 400 if `(appointment_date + appointment_time) − now() < 24h` |
| `book_for_authed_patient(slug, practitioner, appointment_date, appointment_time, reason)` | | `{ok, appointment_name}` | Calls shared `_book_slot` helper |
| `list_my_records(slug)` | | `{encounters, problems, allergies, chronic_conditions}` | Each capped at 50, paginate later |
| `get_my_record_detail(slug, doctype, name)` | | `{...doc...}` | Drawer detail view |
| `list_my_documents(slug)` | | `{sick_notes, prescriptions}` | docstatus=1 only |
| `download_my_document(slug, doctype, name)` | | PDF binary | Validates ownership before rendering print format |
| `list_my_invoices(slug)` | | `[{...}]` | Sales Invoices where `customer == Patient.customer` |
| `get_practice_practitioners(slug)` | | `[{...}]` | Reuse existing `medic_plus.api.booking.get_practice_practitioners` |
| `get_availability(slug, practitioner, date)` | | `[{time}]` | Reuse existing `medic_plus.api.booking.get_availability` |

### Shared booking helper (refactor)

Extract a private helper in `medic_plus.api.booking`:

```python
def _book_slot(*, patient_doc, practice, practitioner, appointment_date, appointment_time, reason) -> str:
    """
    Single source of truth for booking rules:
      - slot must be in `get_availability`
      - no double-book (existing 'Patient Appointment' for same patient/time)
      - min notice (future: configurable; today: any future time OK)
      - returns the created Patient Appointment name
    """
```

`verify_and_book` (guest) and `book_for_authed_patient` both call this. Future booking rules — cancellation windows, no-show penalties, min-notice — live here only.

## Permissions & isolation

### Role

Reuse existing `Patient` role. Auto-assigned on first OTP verify together with `Website User` type. `api/permissions.py` already implements `Patient`-role PQC branches via `_get_patient_name_for_user` for Patient, Patient Appointment, Sick Note, Patient Allergy, Patient Chronic Condition, Patient Medical Record, Patient Insurance Policy, Patient Insurance Coverage. No new role required.

### PQCs to extend in `api/permissions.py` + `hooks.py`

Add a `Patient`-role branch to PQCs that don't yet have one but are needed for the portal:

- `get_patient_encounter_permission_query` — currently practice-only; add patient branch.
- `get_patient_problem_list_permission_query` — new PQC (if not already registered).
- `get_medication_request_permission_query` — new PQC.
- `get_sales_invoice_permission_query` — new PQC (scope by `Patient.customer == Sales Invoice.customer` for the session user).

Branch shape (same as existing patterns):

```python
def get_X_permission_query(user=None):
    if _is_platform_admin(user):
        return ""
    if "Patient" in frappe.get_roles(user or frappe.session.user):
        patient = _get_patient_name_for_user(user)
        return f"`tabX`.`patient` = {frappe.db.escape(patient)}" if patient else "1=0"
    practice = _get_user_practice(user)
    if not practice:
        return "1=0"
    return f"`tabX`.`custom_practice` = {frappe.db.escape(practice)}"
```

For Sales Invoice the scope is `customer = <Patient.customer for the session user>` (the existing `_get_patient_name_for_user` helper needs a sibling `_get_customer_for_user` that joins Patient → customer).

### Defense-in-depth

Every new endpoint re-validates ownership in code before reading or writing — not just relying on PQC. Pattern:

```python
def _resolve_my_patient(slug):
    patient = frappe.db.get_value("Patient", {
        "email": frappe.session.user,
        "custom_practice": _practice_from_slug(slug),
    }, ["name", ...], as_dict=True)
    if not patient:
        frappe.throw(_("No patient record at this practice"), frappe.PermissionError)
    return patient
```

## Frontend

### File layout

```
medic_plus/public/portal/
  portal-api.js          # window.portalApi (mirrors meridian-api.js)
  portal-app.jsx         # root router
  portal-layout.jsx      # shell, topbar, sidebar (mobile drawer)
  portal-login.jsx       # email + OTP screens
  portal-practice-picker.jsx
  portal-home.jsx
  portal-appointments.jsx
  portal-book.jsx        # drawer-based booking flow
  portal-records.jsx
  portal-documents.jsx
  portal-billing.jsx
  portal-profile.jsx

medic_plus/www/portal/
  index.html             # Jinja shell at `/portal` (resolver)
  index.py
  <slug>.html / <slug>.py via dynamic route OR a single `[slug].html` template if Frappe supports it; otherwise the same shell with the slug read from `frappe.form_dict`
```

### Reused from `/daystar-health` assets

Loaded directly (same `<script>` tags) from `medic_plus/public/daystar-health/`:

- `meridian.css`, `styles.css`
- `meridian-icons.jsx`
- `meridian-date-picker.jsx`
- `meridian-time-picker.jsx`
- `meridian-select.jsx`
- `meridian-textarea.jsx`

Same Babel-in-browser pattern; no Vite/webpack added. Page-load cost is acceptable for patient sessions (typically one visit per week or less).

### Boot context

```html
<script>
window.__DAYSTAR_PORTAL__ = {
  csrfToken: {{ csrf_token | tojson }},
  sessionUser: {{ session_user | tojson }},
  slug: {{ slug | tojson }},
  practice: {{ practice | tojson }},    // {name, practice_name, logo, color}
  isAuthed: {{ is_authed | tojson }},
  hasPatient: {{ has_patient | tojson }}
};
</script>
```

### Responsive (mandatory per `frappe-bench/CLAUDE.md`)

- Mobile-first CSS; reuse Meridian breakpoints.
- 375px-width must work: book flow drawer is full-screen, appointments list collapses to single-column, profile form is single-column on phones.
- Touch targets ≥40px.
- Sticky top bar collapses on small viewports.

## Testing

### Python (`medic_plus/api/test_patient_portal.py`)

Test fixtures: create 2 Practices, 1 Patient at each, then assert:

- `request_portal_otp` rate-limit kicks in at 6th call within 10 min.
- `request_portal_otp` returns `{ok: true}` for unknown email (no enumeration).
- `verify_portal_otp` auto-provisions User + Patient Portal User role.
- `verify_portal_otp` rejects wrong code, exhausts after 5 attempts.
- `update_me` rejects payload with `custom_practice`, `custom_sa_id_number`, `medical_history`.
- `cancel_my_appointment` returns 400 when `<24h` before slot.
- `book_for_authed_patient` rejects slot not in `get_availability`.
- Cross-tenant PQC: Patient A at Practice X cannot read Patient B's appointments, invoices, sick notes, encounters at Practice Y.
- Use `IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]` per CLAUDE.md.
- Call PQCs directly with `user=...` per CLAUDE.md test pattern.

### Playwright (`medic_plus/tests/ui/test_patient_portal.py`)

Reuse `conftest.py` fixtures. Cover:

- OTP login flow end-to-end (mock email retrieval via Email Queue or pre-set OTP cache).
- Home renders next appointment + quick actions.
- Booking flow: pick practitioner → date → slot → submit → appointment appears in list.
- Cancel an appointment ≥24h out succeeds; <24h shows error.
- Edit profile (mobile, first_name) → save → reload → persists.
- Download a sick note PDF (assert content-type).
- 375px viewport: appointments list and profile form render without horizontal scroll.

## Release artifacts

Per `frappe-bench/CLAUDE.md` "Release Discipline (NON-NEGOTIABLE)":

1. **`docs/releases/vX.Y.0.md`** — reader-facing notes. Version is next minor (new top-level UI surface).
2. **`techspec.md`** append — date, one-line summary, commit SHAs.
3. **daystar_dev_logger Session Log** — verify the auto-log lands against the medic_plus Work Order on `crm.thedaystar.co.za`; split/reassign if it went to "Unassigned".

## Risks & open questions

- **Email deliverability**: `mute_emails=1` on staging. Test plan must temporarily flip to 0 for OTP integration tests, then flip back per the 2026-04-09 incident note in CLAUDE.md. Or stub `frappe.sendmail` in tests.
- **Email enumeration vs UX**: returning `{ok}` always means a user who mistypes their email gets stuck. Mitigation: portal login form shows "If the email matches a patient record, we sent a code." Acceptable trade-off.
- **Patients without `email` set**: existing Patient records may have no email. Out of scope to fix here, but the OTP flow simply won't find them — receptionist must update the Patient record's email first. Add a note to the release.
- **Patient.customer link**: not all Patient records have a Customer link populated. Billing screen shows empty state if `Patient.customer` is null. No fallback needed in MVP.
- **Prescription download via Medication Request**: confirm the print format name during implementation; if no standard print format exists, ship one as part of this work.

## Out of scope (explicit)

- Native mobile app
- Push notifications
- Telehealth video (separate Phase 1F-related work)
- Payment of invoices online
- Patient self-curation of structured clinical records (allergies, conditions)
- POPIA SA ID unmask for patient self-service
- Practice-switcher within a single session
