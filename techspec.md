# techspec.md — Medic Plus

Living technical specification. Every feature, bugfix, refactor, and design decision is logged here with dates.

---

## 2026-04-29 — Phase 1F (Issue #4): Daystar Health SPA — auth flow wired to Frappe

### Scope
Slice 1 of 5 for the `/daystar-health` Single-Page Application: replace the mock authentication with real Frappe auth, and lay the foundation that subsequent screens (dashboard, patients list, patient detail, profile) reuse.

### Deep module: `practice_resolver`
- `get_active_practice(user) -> str` resolves the user's active Practice via `Practice Member`, the single source of truth for "which Practice does this user belong to" across all Daystar Health endpoints.
- Raises `frappe.PermissionError` for Guest and for any user without a Practice Member row. `Healthcare Administrator` role is *not* specially privileged here — admins still need a Practice Member to use this UI (they retain Frappe Desk access for admin work).

### SPA bootstrap
- `www/daystar_health.py` exposes `csrf_token`, `session_user`, and `has_practice` to the template via `get_context()`. Resolving `has_practice` server-side eliminates a first-render round trip and lets the SPA choose its initial route synchronously.
- `meridian-api.js` is the new centralised SPA API client — wraps `fetch` with CSRF + JSON conventions, surfaces `call`, `resource`, `login`, `recoverPassword`, `logout`, `showError`. Every later slice consumes this helper rather than rolling its own.

### Auth screens (`meridian-auth.jsx`)
- `MLoginScreen` posts to `/api/method/login` with username/email + password. In-page error banner on bad credentials. Username (e.g. `Administrator`) and email both accepted (`type="text"` rather than `type="email"`).
- `MRecoverScreen` posts to `frappe.core.doctype.user.user.reset_password`.
- New `MNoPracticeScreen` renders for authenticated users without a Practice Member row. Sign-out posts to `/api/method/logout` with the CSRF token.

### First-render routing
The SPA's `initialRoute()` reads the bootstrap and chooses `login` / `no-practice` / `dashboard` at mount time. Already-authenticated users no longer see the login screen flicker.

### Tests
- Python: 3 unit tests for `practice_resolver` (member returns Practice, no-membership raises, Guest raises). Mocks `frappe.db` to keep tests pure; LocalProxy bound in `setUpModule` to avoid Python 3.14 + ContextVar issues.
- Playwright: 5 tests covering anonymous → login screen, invalid credentials surface in-page error, admin login lands on no-practice card, already-logged-in admin skips login, sign-out returns to login.

### Bug surfaced
Frappe's website page renderer (`template_page.set_pymodule`) maps hyphenated `.html` templates to underscored `.py` companion modules. The pre-existing `daystar-health.py` was therefore dead code — Frappe was looking for `daystar_health.py`. Renamed to fix the bootstrap injection.

### Out of scope (later slices)
- Dashboard, patients list, patient detail, profile — all still consume static `MH_DATA` mocks. Issues #5, #6, #7, #8.

---

## 2026-04-08 — Phase 3: Platform Owner Workspace

### Requirement
Administrator/Healthcare Administrator needs a single workspace to monitor all practices — metrics, charts, quick links, recent activity.

### Workspace: "Medic Plus Platform"
- **Module:** Medic Plus
- **Role restriction:** Administrator + Healthcare Administrator only
- **Sections:** Key Metrics → Analytics → Quick Access → Recent Activity

### Number Cards (6)
| Card | DocType | Filter |
|------|---------|--------|
| Total Practices | Practice | none |
| Active Practices | Practice | is_active=1 |
| Total Patients | Patient | none |
| Today's Appointments | Patient Appointment | appointment_date=Today |
| This Month's Appointments | Patient Appointment | appointment_date this month |
| Sick Notes Issued | Sick Note | docstatus=1 |

### Dashboard Charts (3)
| Chart | Type | DocType | Grouped by |
|-------|------|---------|------------|
| Appointments Over Time | Line | Patient Appointment | appointment_date (daily, last month) |
| Practices by Subscription Plan | Donut | Practice | subscription_plan |
| Patients per Practice | Bar | Patient | custom_practice |

### Shortcuts (6)
New Practice, Practice Members, All Patients, All Appointments, All Sick Notes, Email Account

### Quick Lists (3)
Recent Practices, Recent Appointments, Recent Sick Notes

### Fixtures
Number Card, Dashboard Chart, and Workspace all exported to `fixtures/` and wired into `hooks.py`.

---

## 2026-04-08 — Phase 1: Multi-Tenant Core + Booking Portal

### Requirement
Build a multi-tenant healthcare platform on top of Frappe Healthcare v16. Doctors register a **Practice**, operate independently on a single bench site, and patients can self-book appointments via a public portal.

### Architecture Decision: Practice-as-Tenant
Each **Practice** is the tenant boundary. All Healthcare DocTypes carry a `custom_practice` Link field. Eight Permission Query Conditions enforce data isolation at the database layer — users only query records belonging to their own practice. Platform admins (`Healthcare Administrator` role) see all.

### DocTypes Created

#### Practice
- **Purpose:** Tenant entity. One per doctor/clinic.
- **Naming:** UUID (v16 feature — no guessable sequential IDs)
- **Key fields:** `practice_name`, `slug` (unique, URL-safe, auto-generated), `is_active`, `subscription_plan`, `owner_practitioner`, `logo`, `color`
- **Slug:** Auto-generated from practice name on insert if empty. Validated to be lowercase alphanumeric + hyphens. Uniqueness enforced in controller.
- **File:** `medic_plus/medic_plus/doctype/practice/`

#### Practice Member
- **Purpose:** Links Frappe Users to a Practice with a role (Admin / Doctor / Receptionist).
- **Naming:** UUID
- **Key fields:** `practice`, `user`, `role`, `practitioner`
- **Side effects on save:** Auto-assigns corresponding Frappe role (`Practice Admin` / `Practice Doctor` / `Practice Receptionist`) to the User. Removes role on trash if no other membership exists.
- **Validation:** Prevents duplicate user+practice membership. Doctor role requires `practitioner` field.
- **File:** `medic_plus/medic_plus/doctype/practice_member/`

#### Sick Note
- **Purpose:** Submittable document issued by a doctor. Creates a Patient Medical Record on submit.
- **Naming:** `SN-.YYYY.-.#####`
- **Key fields:** `patient`, `practice`, `practitioner`, `encounter` (optional), `date_issued`, `fit_for_work_date`, `days_off` (auto-calculated), `diagnosis`, `notes`
- **Workflow:** Draft → Submit → Cancel/Amend
- **Side effects:** `before_insert` auto-sets `practice` from session user's Practice Member. `on_submit` creates a Patient Medical Record.
- **File:** `medic_plus/medic_plus/doctype/sick_note/`

### Custom Fields (Fixtures)
Added `custom_practice` (Link → Practice, search_index=1) to:
- `Patient`
- `Patient Appointment`
- `Patient Encounter`
- `Inpatient Record`

### Roles (Fixtures)
- `Practice Admin` — full access within practice
- `Practice Doctor` — create/submit encounters, prescriptions, sick notes
- `Practice Receptionist` — appointments + patients, read-only sick notes

### Permission Query Conditions
Eight conditions in `medic_plus/api/permissions.py`, wired via `hooks.py`:
- `Practice`, `Practice Member` — scoped to user's own practice
- `Patient`, `Patient Appointment`, `Patient Encounter`, `Inpatient Record` — scoped by `custom_practice`
- `Sick Note` — scoped by `practice`
- `Healthcare Practitioner` — visible only if member of same practice

Platform admins (`Healthcare Administrator`) bypass all conditions.

### hooks.py — doc_events
`before_insert` on Patient, Patient Appointment, Patient Encounter, Inpatient Record → `set_practice_on_insert` — auto-stamps `custom_practice` from the session user's Practice Member record.

### v16 Mixin (extend_doctype_class)
`PracticeAwareMixin` extends `Patient Appointment` — validates that the selected practitioner belongs to the appointment's practice.

---

## 2026-04-08 — Phase 2: Public Booking Portal with Email OTP

### Requirement
Patients book appointments via `/book?practice=<slug>` without a Frappe account. Identity verified via email OTP.

### Security Design
Marley Frontend's existing OTP pattern generates the code client-side and stores it in `localStorage` — trivially bypassed via DevTools. We do not replicate this.

**Our pattern:**
- OTP generated server-side (`random.randint(100000, 999999)`)
- Stored in Redis via `frappe.cache.set_value(key, otp, expires_in_sec=600)`
- Never sent to or stored in the browser
- Single-use: deleted from cache immediately on successful verification
- Rate limited: max 3 requests per 10 minutes per email+practice (tracked in Redis)

### API Endpoints (`medic_plus/api/booking.py`)

| Method | Auth | Purpose |
|--------|------|---------|
| `request_booking_otp(practice_slug, email)` | guest | Generate + email OTP, rate-limited |
| `verify_and_book(practice_slug, otp, ...booking_data)` | guest | Verify OTP then atomically create appointment |
| `get_practice_info(practice_slug)` | guest | Public practice details |
| `get_practice_practitioners(practice_slug)` | guest | Active doctors |
| `get_availability(practice_slug, practitioner, date)` | guest | Open time slots |

### Booking Flow
1. Patient fills form (name, email, phone, doctor, date, time slot)
2. Clicks "Send Verification Code" → `request_booking_otp` → branded OTP email sent
3. Enters 6-digit code → `verify_and_book` → OTP verified, appointment created, confirmation email sent
4. Success screen with appointment reference

### Email
- Outbound: `liz@thedaystar.co.za` via `mail.thedaystar.co.za:587` (TLS)
- Configured via Frappe Email Account DocType
- `mute_emails` disabled in site_config

### Portal Page
- URL: `/book?practice=<slug>`
- Jinja template: `medic_plus/www/book/index.html`
- Context: `medic_plus/www/book/index.py`
- Three-step UI: Details → OTP → Success
- Brand colour applied via CSS variable from Practice's `color` field

### Patient Creation
- New patients auto-created on first booking (matched by email on subsequent bookings)
- `custom_practice` stamped on new Patient records

---

## Design Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-04-08 | Practice uses UUID naming | No guessable IDs for tenant records |
| 2026-04-08 | OTP server-side in Redis, not localStorage | Security — client-side OTP trivially bypassed |
| 2026-04-08 | Permission Query Conditions over row-level security | Native Frappe pattern, applies at ORM layer |
| 2026-04-08 | Single `custom_practice` field on Healthcare DocTypes | Minimal DB footprint, compatible with base Healthcare app |
| 2026-04-08 | verify_and_book is atomic | Prevents partial state: OTP consumed only if appointment succeeds |
| 2026-04-08 | Jinja booking portal (not Vue SPA) | Simpler — no build step, no dependency on marley_frontend |
| 2026-04-13 | Practice naming changed from UUID → PRAC-.##### | UUID names are opaque, break list views, and make debugging harder |
| 2026-04-13 | Two-sided OTP (clinician + patient) for data unmask | POPIA requires affirmative patient consent — one-sided OTP was insufficient |
| 2026-04-13 | Store OTP hashes (SHA-256), never plaintext | Defence-in-depth: even if DB is compromised, OTPs cannot be retrieved |
| 2026-04-13 | urllib + CookieJar for Playwright second-session tests | Frappe's 403 redirect handler destroys page.evaluate context in browser |
| 2026-04-14 | Playwright UI tests mandatory for all features | Regression safety net without needing a staging reset for each PR |

---

## 2026-04-13 — Phase 3B: Subscription Billing + Feature Gates

### Requirement
Practices must be locked to a tier (Free / Basic / Pro). Certain features (inpatient module, SMS reminders, advanced reports) must be unavailable until upgraded. Paystack processes recurring payments.

### Plan catalogue (in-code, `billing.py`)
Plans are defined in `MEDIC_PLANS` dict — no DocType. `Practice.subscription_plan` stores the current key. Avoids schema migration when plan pricing changes.

### `require_feature` decorator
Applied to any endpoint that should be plan-gated:
```python
@frappe.whitelist()
@require_feature("inpatient_module")
def get_inpatient_summary(): ...
```
Raises `frappe.PermissionError` (HTTP 403) if the feature is `False` for the practice's plan. Platform admins bypass unconditionally.

### `/billing` web page
Authenticated Jinja page. Calls `get_billing_summary()` on load. Shows plan, status badge, usage bars, feature chips, and upgrade cards with Paystack checkout buttons.

### Paystack webhook
`paystack_webhook()` validates HMAC-SHA512 signature against `Medic Plus Settings.paystack_secret_key`. On `charge.success`, updates `Practice.subscription_plan` and `subscription_status`.

---

## 2026-04-13 — Phase 3C: Practice Setup Checklist + Patient Portal + Patient PQC

### Practice Setup Checklist
Six-step onboarding tracker. Steps 1-4 are set by the doctor via the UI. Steps 5-6 are auto-completed by `doc_events.py`:
- Step 5: fires on `Practitioner Schedule.after_save`
- Step 6: fires on `Sales Invoice.on_submit` when the company matches the practice's company

### Patient role PQC isolation
Patients get a Frappe User with role `Patient`. Their PQC branches to scope by `User.email == Patient.email` rather than by practice membership. Without this, any patient with a login could see all patients in their practice.

### Patient portal (`/portal`)
Authenticated Jinja page. Shows the logged-in patient's appointments, sick notes, and pending data unmask requests (with a "Deny" button).

---

## 2026-04-13 — Phase 3D: Patient Data Masking (POPIA Hardening)

See Section 7 of TRAINING_MANUAL.md for the full flow.

**New doctypes:** `Data Unmask Request`, `Clinical Access Log`
**New fixtures:** Client Script on Patient form (masking + "View" button)
**New scheduled task:** `expire_stale_requests` (every 15 min)

### Key design choices
- OTPs are 6-digit numeric strings, generated by `random.choices(string.digits, k=6)`
- Only SHA-256 hashes stored — plaintext never persists beyond the HTTP response
- Plaintext returned exactly once per successful `verify_unmask()` call
- `developer_mode=1` returns OTPs in plaintext for QA (`_dev_requester_otp`, `_dev_patient_otp`)

---

## 2026-04-13 — Phase 3E: Inpatient Dashboard

### Frappe Page
`medic_plus/medic_plus/page/inpatient_dashboard/` — visible to all practice roles + admin.

### APIs
- `get_inpatient_summary()` — four headline stats (current, today's admissions, expected discharges, avg LOS)
- `get_current_inpatients()` — full admitted-patient list with computed `los_days` and `current_ward`

Both gated by `@require_feature("inpatient_module")` — only Pro plan practices can access.

`_get_practice_filter()` returns `{}` for platform admins (see all) or `{"custom_practice": practice}` for practice staff.

---

## 2026-04-14 — Playwright UI Test Suite

44 tests across 4 files. All pass on staging (1 skipped when no inpatients are admitted).

Key lessons embedded in `CLAUDE.md` (Tests → UI Tests section):
- Scope locators to `.parent .child` not `get_by_text()` globally
- Use `urllib + CookieJar` for second-session permission tests
- Frappe 403 handler calls `error_callback()` with no args — `exc_type='ServerError'` is the signal, not "PermissionError" in the exception string

---

## 2026-04-22 — Phase 6: Doctor Self-Registration (OTP + Yoco)

- `/signup` funnel replaces `/register` and `/register/doctor`.
- Yoco webhook is the sole provisioning trigger (auto-provisions `provision_doctor` on `payment.succeeded`).
- Post-payment UX uses a signed one-time completion URL (12-hr TTL, SHA-256 hashed in Redis at rest) instead of Frappe's password reset.
- 15-min scheduler retries any PRR stuck in `Paid but not Provisioned`.
- `Registration Request` DocType dropped; orphan Users cleaned up by patch (System Users skipped and logged for manual review).
- Admin `onboard_doctor` refactored to share `provision_doctor` (now emits Company + POS + Checklist + Folder).

Production fixes surfaced by the E2E test:
- `_handle_payment_succeeded` runs as Administrator (Healthcare Practitioner.on_update needs User Permission insert; webhook signature is verified upstream so the elevation is safe).
- `complete.html` and `success.html` gate their immediate `frappe.call` on `whenFrappeReady` — the inline script runs before `frappe-web.bundle` is parsed.
- Form-handler errors use the `.then(success, error)` tuple form; `.catch` doesn't always fire on Frappe XHR rejections.

---

## Roadmap

- [ ] Prescription print format — Jinja, per-practice letterhead ✅ Done (Phase 1D)
- [ ] Sick Note print format — Jinja, per-practice letterhead ✅ Done (Phase 1C)
- [x] Practice self-registration web form (scaffold at /register — full flow Phase 6)
- [x] Patient portal ✅ Done (Phase 3C)
- [x] Inpatient management dashboard ✅ Done (Phase 3E)
- [x] Subscription billing integration ✅ Done (Phase 3B)
- [ ] SMS/WhatsApp OTP option (Africa's Talking)
- [x] Unit tests ✅ Done (scattered across api/)
- [x] Playwright UI tests ✅ Done (Phase 3 hardening)
- [ ] Medical aid integration (Pro plan feature)
- [ ] Advanced reports (Pro plan feature)
- [ ] Phase 6 — Doctor self-registration approval flow
