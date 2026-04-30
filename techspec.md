# techspec.md — Medic Plus

Living technical specification. Every feature, bugfix, refactor, and design decision is logged here with dates.

---

## 2026-04-30 — Phase 1A (Issue #24): SA-PMI Patient Identity

### Scope

Multi-identifier patient registration with SA ID checksum validation, POPIA consent gate, fuzzy duplicate detection, and SPA registration form upgrade. Implements the SA Patient Master Index (SA-PMI) identity layer on top of the existing Frappe Healthcare Patient doctype.

### DocType Created

#### Patient Identifier (child table of Patient)
- **Purpose:** Stores one or more identity documents per patient. Exactly one row may carry `is_primary = 1`.
- **Fields:** `id_type` (Select: SAID / Passport / Refugee / Asylum / BirthCert / NHID / Other), `id_value` (Data, reqd), `is_primary` (Check), `country` (Link → Country, optional), `expiry_date` (Date, optional).
- **Naming:** `istable=1` — child records use Frappe's implicit numeric `idx`.
- **File:** `medic_plus/medic_plus/doctype/patient_identifier/`

### Custom Fields Added to Patient (Fixtures)

| Field | Type | Purpose |
|-------|------|---------|
| `custom_identifiers` | Table → Patient Identifier | Child table of identifier rows |
| `custom_popia_consent_special` | Check | POPIA Section 27 consent for SA ID / race / language collection |
| `custom_nhid` | Data (indexed) | NHID slot — HPRS integration deferred to a later phase |
| `custom_race` | Select | African / Coloured / Indian or Asian / White / Other / Prefer not to say |
| `custom_home_language` | Select | SA 11 official languages + Other |
| `custom_preferred_language` | Select | SA 11 official languages + Other |

All exported via `fixtures/custom_field.json`; field names in the `hooks.py` filter list.

### New Python Modules

#### `medic_plus/api/sa_id.py`
- `validate_said(id_number)` — raises `frappe.ValidationError` if the 13-digit SA ID fails the SA Dept of Home Affairs checksum:
  1. Sum digits at 0-indexed positions 0, 2, 4, 6, 8, 10 → A
  2. Concatenate digits at positions 1, 3, 5, 7, 9, 11 → N; compute N × 2; sum individual digits → B
  3. `check_digit = (10 − (A + B) % 10) % 10` must equal `id_number[12]`
- `parse_said(id_number)` — returns `{dob: "YYYY-MM-DD", sex: "Male"|"Female"}`. Year century: YY ≤ current two-digit year → 2000+YY, else 1900+YY. Sex: sequence digits 6–9 ≥ 5000 → Male.

**Note:** The issue specification cites `8501015009087` as checksum-valid. The standard algorithm yields check digit 6 for that DOB/sequence combination; `8501015009086` is the canonical test ID used in the test suite. The discrepancy is documented in `test_patient_pmi.py`.

#### `medic_plus/api/patient_identity.py`
- `find_duplicate_patients(patient_name, practice, dob=None, id_value=None)` — `@frappe.whitelist()`. Returns a list of potential duplicate patient dicts. Non-blocking (never raises). Scoring:
  - Exact `id_value` match (any id_type) → always returned.
  - Soundex match on first token of `patient_name` + DOB within ± 1 day → candidate.
  - Levenshtein distance ≤ 2 on lower-cased `patient_name` + DOB within ± 1 day → candidate.
- Soundex and Levenshtein are vendored (pure Python, no external deps).

### Document Lifecycle Hooks

`Patient.validate` → `medic_plus.api.doc_events.validate_patient_identifiers`:
1. **POPIA gate:** if any row has `id_type = "SAID"` and `custom_popia_consent_special = 0` → `ValidationError`.
2. **SA ID checksum:** for each SAID row, calls `validate_said()`.
3. **DOB/sex derivation:** after validation, `parse_said()` populates `doc.dob` and `doc.sex` if not already set.
4. **Primary constraint:** `sum(is_primary for row in identifiers) > 1` → `ValidationError`.

### Permission Query Condition

`Patient Identifier` PQC (`get_patient_identifier_permission_query`):
- Platform admin → unrestricted (`""`).
- Patient role → `parent = <patient_name_for_user>`.
- Practice staff → `parent IN (SELECT name FROM tabPatient WHERE custom_practice = <practice>)`.

Registered in `hooks.py`; CustomDocPerm rows for Practice Admin (read/write/create/delete), Doctor (read/write/create), Receptionist (read/write/create) exported in `fixtures/custom_docperm.json`.

### Endpoints

| Method | Auth | Purpose |
|--------|------|---------|
| `medic_plus.api.patient_identity.find_duplicate_patients` | authenticated | Fuzzy-match candidates, non-blocking |
| `medic_plus.api.practice_resolver.get_active_practice` | authenticated | Returns the session user's practice (now `@frappe.whitelist()`) |

### SPA: meridian-patients.jsx

Added **Register Patient** side-drawer to the Patients list screen:
- "Register Patient" button (top-right of patients page header); disabled until practice resolves.
- Drawer sections: Demographics (first/last name, sex, DOB, email, mobile), Identifier (id_type picker + id_value input), POPIA consent checkbox (shown only when `id_type = "SAID"`), Language & Background (race, home_language, preferred_language — optional).
- Non-blocking duplicate warning banner shown on name/DOB/ID blur.
- Client-side POPIA gate: blocks submission with an inline error if consent is missing for SAID.
- On success: closes drawer and navigates to the new patient's detail screen.

### Tests

#### Python (`medic_plus/api/test_patient_pmi.py`) — 12 test methods across 5 classes

| Class | Behaviors |
|-------|-----------|
| `TestSAIDTracerBullet` | Identifier row persists; DOB/sex derived from SA ID; PQC denies cross-practice receptionist |
| `TestSAIDChecksumValidation` | Bad check digit rejected; 12-digit ID rejected; valid ID accepted |
| `TestPOPIAConsentGate` | SAID without consent raises; Passport without consent allowed |
| `TestPrimaryIdentifierConstraint` | Two primaries raises; multiple identifiers one-primary accepted |
| `TestFuzzyDuplicateDetection` | Exact identifier match returned; Soundex + DOB proximity returned |

#### Playwright (`medic_plus/tests/ui/test_patient_pmi_ui.py`) — 6 test methods

Register Patient button visible; drawer opens; SAID shows POPIA checkbox; Passport hides it; race/language fields rendered; SAID-without-consent shows inline error.

### Design Decisions

| Decision | Reason |
|----------|--------|
| Soundex + Levenshtein vendored (pure Python) | No external packages; Frappe bench envs do not guarantee `jellyfish` or `python-Levenshtein` |
| POPIA consent gated at validate(), not before_insert() | `validate` fires before Frappe's `_validate()` mandatory check, so `doc.dob`/`doc.sex` set here persist |
| Child table PQC uses parent-subquery (not denormalized `custom_practice`) | Patient Identifier is always accessed through the parent Patient; subquery is a one-hop join the DB can optimise |
| `custom_nhid` is a slot only | HPRS national lookup integration is explicitly out-of-scope; the field reserves the column for the future phase |
| SAID check digit 7 vs 6 discrepancy | Issue #24 cites `8501015009087` as checksum-valid; the algorithm (odd-sum + doubled-even-concat) yields 6, not 7. Test suite uses `8501015009086`. |

### Out of Scope (Deferred)

- Biometric capture (Phase 5+)
- HPRS national patient lookup via NHID (field is a slot only)
- Patient demographic change request workflow (Phase 3 with patient portal)
- Telemedicine consent capture (Phase 4)

---

## 2026-04-29 — Phase 1J (Issue #8): Daystar Health profile — wired + password change

### Scope
Slice 5 of 5 (final) wiring `/daystar-health`. Replaces the hardcoded provider profile with the logged-in user's real data, and wires the password-change form to Frappe's standard endpoint. Notifications tab is removed from the SPA's profile sidebar — no schema backing.

### Endpoint: `daystar_health.get_my_practitioner_profile()`
Joins User core (name, email, phone, user_image) with the Healthcare Practitioner linked via the user's Practice Member row (department, HPCSA number, practice number). Adds a top-level `two_factor_authentication` boolean derived from `frappe.utils.user.user_has_2fa` since User has no direct 2FA field.

Same `frappe.PermissionError` no-practice gate as every other Daystar Health endpoint.

### Frontend rewire (`meridian-profile.jsx`)
- Three render states: skeleton, error card, ready (two tabs only — Account, Security).
- **Profile tab**: read-only fields rendered as styled disabled boxes (`<ReadOnlyField>` helper). No "Save changes" button anywhere on the tab. Footer note tells the user to contact their practice administrator for changes.
- **Security tab**: password-change form (current / new / confirm) posts to `frappe.core.doctype.user.user.update_password`. Success/error feedback inline. 2FA shown read-only with status badge ("Enabled" / "Not configured") and a pointer to the Frappe Desk for setup.
- **Notifications tab removed** — no `User Notification Preference` doctype, so any UI we'd ship would be misleading.

### Sidebar fix
The bottom-of-sidebar "Sign out" button was wired to `go('login')` — that just changed the SPA route; the Frappe session was untouched. Fixed to call `window.meridianApi.logout()` so it actually ends the session. Also added `data-testid="nav-profile"` and `data-testid="nav-signout"` on those buttons.

### Tests
- Python: 2 new — endpoint rejects no-practice user (tracer); endpoint returns the documented payload (User + Practitioner blocks + 2FA boolean).
- Playwright: 2 new — profile renders read-only with no Save button + Notifications tab absent; password change round-trip (uses a throwaway Practice user fixture, changes the password through the SPA, then signs in with the new password to prove end-to-end).

### Slice 5 wraps Phase 1 of the SPA wiring (#4 → #5 → #6 → #7 → #8)
The five issues delivered:
- #4 — auth flow + foundation (`practice_resolver`, page bootstrap, `meridian-api.js`)
- #5 — dashboard composite + frontend
- #6 — patients list (REST resource API + server-side search/pagination)
- #7 — patient detail composite (POPIA-filtered, per-tab capped)
- #8 — profile read-only + password change

Outstanding follow-up: **Issue #12** (Custom DocPerm fixtures for Practice roles) — currently unblocked on staging via a Physician role on the test user, but needs to land before the SPA can serve real Practice users without that workaround.

---

## 2026-04-29 — Phase 1I (Issue #7): Daystar Health patient detail — wired to composite endpoint

### Scope
Slice 4 of 5 wiring `/daystar-health`. Replaces the static `MH_DATA` lookups on the patient detail screen with a single composite endpoint that returns all six tabs in one round trip.

### Deep module: `patient_summary`
- `build_patient_summary(patient_name, practice)` — orchestrator. Fetches Patient + Patient Encounters (last 20) + Vital Signs (last 12) + active medications de-duped across encounters + Lab Tests (last 20) + Frappe Comments on the Patient (last 20). Hands them to the format helper.
- `_format_patient_summary(...)` — pure transformation. Caps each tab and applies the **POPIA whitelist**: only the fields in `_PATIENT_PUBLIC_FIELDS` (`name / patient_name / dob / sex / mobile / email / status`) survive into the patient block. `custom_sa_id_number` is impossible to leak — it never appears in the response, even if the caller hands the helper a row containing it.

### Endpoint: `daystar_health.get_patient_detail(patient)`
- Cross-tenant guard: looks up the patient's `custom_practice` and refuses with `frappe.PermissionError` if it doesn't match the caller's active Practice. Same error class as no-practice, so an attacker can't probe Practice membership of arbitrary IDs by looking at the response code.
- Returns the composite payload from `build_patient_summary`.
- "See full record" links per tab go to the Frappe Desk filtered list — built into the payload as `full_record_links`.

### Frontend rewire (`meridian-patient.jsx`)
- Three render states: skeleton, error (with "Back to patients" CTA), ready.
- Ready state has six tabs: Overview / Visits / Vitals / Medications / Labs / Notes — all hydrated from the same fetch, no waterfall on tab switch.
- Notes tab renders Comment HTML via `dangerouslySetInnerHTML` (Frappe's HTML Editor field — same trust boundary as the Frappe Desk activity feed).

### Tests
- Python: 4 new unit tests — POPIA exclusion (the tracer), per-tab caps (visits/labs/meds/notes capped at 20, vitals at 12), endpoint rejects no-practice, endpoint rejects cross-tenant patient request.
- Playwright: 2 new tests — detail screen renders all 6 tab containers (with search filter to ensure we click a row in our own Practice when admin's view bypasses Patient PQC); response body of the composite call asserted to never contain `custom_sa_id_number`.

### Out of scope (later slices)
- Profile + password change (#8) — last slice.

### Surfaced gap (Issue #12)
While testing as a real Practice user (selfserve.test), discovered that medic_plus ships no Custom DocPerm fixtures granting Practice Admin / Practice Doctor / Practice Receptionist roles read access on Patient and related Healthcare doctypes. Practice users get 403 from `/api/resource/Patient` *before* the PQC runs because the role-permission gate isn't open. Tracked in #12 with a workaround (Physician role added to test user).

---

## 2026-04-29 — Phase 1H (Issue #6): Daystar Health patients list — wired to REST resource API

### Scope
Slice 3 of 5 wiring `/daystar-health`. Replaces the static `MH_DATA.PATIENTS` array on the patients screen with a real, server-side paginated/searchable/sortable list backed by Frappe's REST `Patient` resource.

### No new backend module
Per Q11, the patients list is a direct REST consumer — `meridianApi.resource("Patient", {fields, or_filters, order_by, limit_start, limit_page_length})`. PQC (`get_patient_permission_query` in `api/permissions.py`) handles tenant scoping for free, so we get cross-tenant safety without writing any new endpoint.

### Frontend rewire (`meridian-patients.jsx`)
- Three render states: skeleton (during load), error (toast + inline card), ready (table or empty-state card).
- **Search**: 300ms-debounced input, refetches via `or_filters` across `patient_name`, `mobile`, `email`. Clearing the input restores the unfiltered list.
- **Pagination**: real `limit_start / limit_page_length / total` with prev/next. Pagination footer shows `start – end of total`. The total comes from a parallel `frappe.client.get_count` (or a wider `or_filters`-based query when searching).
- **Page-size selector**: 25 / 50 / 100. Persists for the session in `sessionStorage` under `daystar.patients.pageSize`.
- **Sort**: server-side `order_by` on `patient_name` (Name) and `dob` (Age — `dob desc` = oldest first). Click header to toggle direction; resets page to 0.
- **Sidebar nav** now exposes `data-testid={`nav-${key}`}` on every nav button so Playwright tests can navigate between screens deterministically.

### Per the design decisions in the issue
Removed: risk / status / provider filter chips (no Frappe backing), MRN column (no field), risk badge, status pill (Stable/Watch/Urgent — those values don't exist), conditions and allergies columns, "Last seen" column (would require joining Patient Encounter — surfaces in slice 4 via the patient detail screen instead), checkboxes / bulk actions, Export and Register buttons.

### Tests
- Python (`api/test_daystar_health.py`): 2 PQC contract tests — Doctor user is restricted to their own Practice; orphan (no Practice Member) gets `1=0`. Mocks at the `_is_platform_admin` / `_get_user_practice` boundary so the test stays a behavior-of-PQC test, not a doctype-fixture test.
- Playwright (`tests/ui/test_daystar_health.py`): 5 tests — list loads with skeleton then renders rows; search filters list and clearing restores; next-then-prev shows different pages then restores; page-size persists in `sessionStorage`; empty state renders for no-match search.

### Out of scope (later slices)
- Patient detail composite (#7) — clicking a row already navigates to `route='patient'`, but that screen still consumes `MH_DATA`.
- Profile + password change (#8).

---

## 2026-04-29 — Phase 1G (Issue #5): Daystar Health dashboard — wired to live Practice data

### Scope
Slice 2 of 5 wiring `/daystar-health`. Replaces the static `MH_DATA` constants on the dashboard screen with a real composite endpoint scoped to the user's active Practice.

### Deep module: `dashboard_aggregator`
- `build_dashboard(*, practice, user)` — orchestrator. Resolves the user's first name, runs Practice-scoped queries against Patient Appointment / Patient / Lab Test / Patient Encounter, then delegates to the format helper.
- `_format_dashboard(...)` — pure transformation. Takes already-fetched values and returns the payload dict. Tested in isolation without a DB so the interesting rules (greeting personalisation, week-volume always 7 days, recent-patients cap at 6, status breakdown of today's appointments) have fast unit coverage.

### Endpoint: `daystar_health.get_dashboard()`
- Thin orchestrator: `practice_resolver.get_active_practice` → `build_dashboard` → return. Surfaces `frappe.PermissionError` unchanged so the SPA can render the no-practice card.

### Frontend rewire (`meridian-dashboard.jsx`)
- On mount, `meridianApi.call('medic_plus.api.daystar_health.get_dashboard')`. Skeleton placeholder during load; toast + inline error card on failure.
- KPI tiles: today's appointments (with status-breakdown subtitle using *real* statuses — Confirmed / Open / Scheduled — not the mock's "checked-in / in-room"), active patients, outstanding labs.
- Today's schedule, week-volume bar chart, recent-patients table all hydrate from the payload.
- Per Q9 design decision: dropped the "Pending refills" KPI tile (no Frappe backing), the "Needs attention" alerts panel (no backing), the MRN/Risk/Status columns on recent patients, the Day/Week/Month toggle, and the "New appointment" button.
- "View full schedule" button links to the Frappe Desk Patient Appointment list filtered by `custom_practice` and today's `appointment_date`.

### Schema realities handled
- `Lab Test` has no `custom_practice` field. The outstanding-labs KPI uses a JOIN through `Patient.custom_practice` rather than schema migration.
- The `checked_in / in_room` statuses in the mock don't exist in `Patient Appointment`. The real statuses (`Confirmed / No Show / Open / Scheduled`) are surfaced verbatim.

### Tests
- Python (`api/test_daystar_health.py`): 4 format-helper unit tests + 2 endpoint contract tests (no-Practice rejection, payload shape on success). Mocks at the boundary so the helper is testable without DB or session.
- Playwright (`tests/ui/test_daystar_health.py`): one test that creates a temporary `Practice Member` row for Administrator (role=Admin to bypass the Doctor → Healthcare Practitioner validation), logs in, asserts the dashboard renders all three KPI tiles, the week-volume chart, today-schedule and recent-patients sections, the greeting block, and the "View full schedule" link with the right `custom_practice` query string. Tears the Practice Member row down on teardown so the slice 1 no-practice tests still pass for Administrator.

### Out of scope (later slices)
- Patients list (#6), patient detail composite (#7), profile + password change (#8).

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

## 2026-04-30 — SA EMR Phase 1: Compliance core (#18)

Closes the legal-floor gap so the Daystar Health SPA can host real SA practice data. Six commits on `develop` (e51975c → d2b967a):

- New doctypes: `Patient Allergy` (FHIR-aligned criticality), `Patient Chronic Condition` (Link → Diagnosis), `Medical Aid Scheme` (CMS directory), `Record Archive Queue`. Each clinical doctype denormalises `custom_practice` from Patient on insert for fast PQC subqueries.
- 4 new Permission Query Conditions scope via `patient.custom_practice` + 1 PQC for `Patient Medical Record`. 12 Custom DocPerm rows (3 Practice roles × 4 doctypes — Receptionist read-only on chronic conditions).
- 4 SA medical-aid Custom Fields on `Patient Insurance Policy`: `custom_sa_scheme`, `custom_principal_member_id`, `custom_dependent_code`, `custom_authorisation_reference`.
- Whitelisted endpoints: `get_patient_allergies`, `get_patient_chronic_conditions`, `get_patient_medical_aid`, `search_icd10` — all assert patient ∈ active practice.
- `build_patient_summary` hydrates allergies (cap 50), chronic conditions (cap 50), medical aid (cap 5).
- Reference data fixtures: 1 `Code System` (ICD-10, FHIR uri), 34 curated WHO ICD-10 codes (HTN, T1/T2DM, asthma, URTI/UTI, depression/GAD, etc.), 10 SA schemes (Discovery, Bonitas, Momentum, Bestmed, Medshield, Profmed, Polmed, GEMS, Fedhealth, Keyhealth).
- Daily scheduler `medic_plus.api.retention.flag_overdue_records` — HPCSA Booklet 9 / NHA §17 (6-year retention, paediatric to age 21, idempotent via Record Archive Queue).
- SPA: Allergies + Conditions tabs in patient drawer, severe-allergy banner, Medical Aid card on Overview, reusable `MIcd10Picker` (250 ms debounced).
- Tests: 10 `IntegrationTestCase` (PQC shape, cross-practice blocks, happy-path reads, denormalisation, summary hydration), 4 retention tests (TDD), 4 Playwright (banner + tabs + ICD-10).

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
