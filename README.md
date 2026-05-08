# Medic Plus

A multi-tenant healthcare platform built on [Frappe](https://frappeframework.com) v16 and [ERPNext Healthcare](https://github.com/frappe/healthcare). Enables multiple doctors/practices to operate independently on a single Frappe bench site — no separate site or server per practice.

## Features

- **Multi-tenant isolation** — each Practice sees only its own patients, appointments, and records (enforced at the database layer via Permission Query Conditions)
- **Practice management** — doctors register a Practice with branding, contact details, and a unique booking URL slug
- **Patient appointments** — doctors and receptionists manage bookings; patients can self-book via a public portal
- **Inpatient & outpatient records** — full Patient Encounter workflow scoped per practice
- **Prescriptions** — issued within Patient Encounters, scoped and printable on practice letterhead
- **Sick Notes** — submittable documents with diagnosis, dates off, auto-calculated days, and patient medical record integration
- **Role-based access** — three practice roles (Admin, Doctor, Receptionist) with appropriate permissions

## Architecture

```
Single Frappe Site
├── Practice A (Dr. Smith)
│   ├── Patients          ← isolated via custom_practice field + Permission Query
│   ├── Appointments
│   ├── Patient Encounters / Prescriptions
│   └── Sick Notes
├── Practice B (Dr. Jones)
│   └── ...
└── Healthcare Administrator   ← platform superuser, sees all
```

### Tenant Boundary

Each **Practice** is the tenant entity. All Healthcare DocTypes carry a `custom_practice` Link field. Eight Permission Query Conditions enforce that users only query records belonging to their own practice.

### Data Flow

1. Doctor registers → `Practice` created with unique slug
2. Users added as `Practice Member` (Admin / Doctor / Receptionist) → Frappe role auto-assigned
3. Patients book via `/book?practice=<slug>` or reception creates appointment in desk
4. `custom_practice` is auto-stamped on every new Patient, Appointment, Encounter, and Inpatient Record via `before_insert` hook
5. Doctors create Patient Encounters → prescriptions issued as child table rows
6. Sick Notes issued as standalone submittable documents → linked to Patient Medical Record on submit

## DocTypes

| DocType | Description |
|---------|-------------|
| `Practice` | Tenant entity. UUID-named. Holds slug, branding, subscription plan. |
| `Practice Member` | User ↔ Practice link with role. Auto-assigns/removes Frappe roles. |
| `Sick Note` | Submittable. Auto-calculates days off. Linked to Patient Medical Record on submit. |

### Custom Fields (added to Healthcare DocTypes)

| DocType | Field | Purpose |
|---------|-------|---------|
| Patient | `custom_practice` | Tenant scope |
| Patient Appointment | `custom_practice` | Tenant scope |
| Patient Encounter | `custom_practice` | Tenant scope |
| Inpatient Record | `custom_practice` | Tenant scope |

## Roles

| Role | Access |
|------|--------|
| `Practice Admin` | Full access within their practice — manage members, all records |
| `Practice Doctor` | Create/read/submit encounters, prescriptions, sick notes |
| `Practice Receptionist` | Manage appointments and patient records; read-only sick notes |
| `Healthcare Administrator` | Platform superuser — unrestricted access across all practices |

## Public Booking Portal

URL: `/book?practice=<slug>`

- Lists available doctors and time slots
- Creates Patient record on first booking (matched by email thereafter)
- No login required

### Booking API (whitelisted, guest-accessible)

| Method | Description |
|--------|-------------|
| `medic_plus.api.booking.get_practice_info` | Practice name, logo, contact |
| `medic_plus.api.booking.get_practice_practitioners` | Active doctors for a practice |
| `medic_plus.api.booking.get_availability` | Open time slots for a practitioner on a date |
| `medic_plus.api.booking.request_booking_otp` | Send email OTP to patient (rate-limited, server-side) |
| `medic_plus.api.booking.verify_and_book` | Verify OTP then create appointment atomically |

## Requirements

- Frappe v16
- ERPNext Healthcare app

## Installation

```bash
bench get-app medic_plus https://github.com/thedaystar/medic_plus
bench --site your-site.com install-app medic_plus
bench --site your-site.com migrate
```

## Development

```bash
# After pulling changes
bench --site your-site.com migrate

# Run tests
bench --site your-site.com run-tests --app medic_plus
```

## Roadmap

- [ ] Prescription print format (per-practice letterhead via Jinja)
- [ ] Sick Note print format (per-practice letterhead)
- [ ] Practice self-registration / onboarding web form
- [ ] Patient portal (patients log in, view records, book follow-ups)
- [ ] Inpatient dashboard
- [ ] Subscription billing integration
- [ ] SMS/email appointment reminders

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/medic_plus
pre-commit install
```

## License

MIT

---

## Changelog

### 2026-05-08 — v2.0.0: SA EMR Phase 1 close + Phase 4 + POPIA + FHIR R4
- First major version. Rolls up Phase 1C (SOAP encounter), Phase 1D (drug safety), Phase 1E (insurance claims + POPIA + FHIR), and Phase 4 (telemedicine + AI augmentation). 16 commits, 15 new doctypes, ~11k lines added. Full release notes in `docs/releases/v2.0.0.md`.
- **Phase 1C — Structured SOAP encounter (#26):** `Examination Finding` (child of Patient Encounter) and `Patient Problem List` doctypes; SPA encounter drawer captures Subjective / Objective / Assessment / Plan with ICD-10-ZA picker.
- **Phase 1D — Drug safety (commit `e8323a9`):** `Drug Master` + `Prescription Override Reason` doctypes; allergy/interaction/paediatric-dose checks; HPCSA Booklet 8 prescription print format; SPA `MPrescriptionPanel`.
- **Phase 1E — Insurance Claims (#28):** `Insurance Claim` + `Insurance Claim Line` + `Tariff Code` + `Switch Configuration` doctypes; `claim_builder` + HealthBridge submission client; on-submit hook; cross-tenant PQCs.
- **POPIA controls (#28):** `Patient Consent Record` + `Sub-Processor Register` doctypes; daily `flag_expired_consent_records` cron expires consent older than 3 years.
- **FHIR R4 read-only server (#28):** `/api/fhir/R4/<ResourceType>/<id>` returning `application/fhir+json`; six R4 resources (Patient/Encounter/Condition/MedicationRequest/AllergyIntolerance/Observation); `$everything` Bundle; `CapabilityStatement` at `/api/fhir/R4/metadata`; SMART v2 bearer tokens via `FHIR Access Token` doctype (SHA-256 hashed, 1-hour TTL, practice-bound).
- **Phase 4 — Telemedicine + AI augmentation (commit `e49c3ef`):** `Telemedicine Consent` + `Practice AI Settings` + `AI Inference Log` + `Medic Plus Settings` doctypes; per-encounter `/teleconsult` page; PHI redactor strips identifiers before any external AI call; AI off by default per practice.
- **Tests:** integration + Playwright suites for claims, drug safety, FHIR, POPIA, telemedicine, encounter — every PQC asserts cross-tenant isolation.
- **Permission fix (commit `1db4748`):** repaired Phase 4 + Phase 1E PQC function bodies.

### 2026-04-30 — SA EMR Phase 1 (Issue #18): Compliance core
- Closes the legal-floor gap so the SPA can host real SA practice data. Six commits on `develop` (e51975c → d2b967a).
- New doctypes: `Patient Allergy` (FHIR-aligned criticality), `Patient Chronic Condition`, `Medical Aid Scheme`, `Record Archive Queue`. Each clinical doctype denormalises `custom_practice` from Patient on insert.
- 4 new Permission Query Conditions scope clinical data via `patient.custom_practice` + 1 PQC for `Patient Medical Record`. 12 Custom DocPerm rows.
- 4 SA medical-aid Custom Fields on `Patient Insurance Policy` (CMS scheme link, principal member ID, dependent code, authorisation reference).
- Whitelisted endpoints: `get_patient_allergies`, `get_patient_chronic_conditions`, `get_patient_medical_aid`, `search_icd10`. `build_patient_summary` hydrates allergies / chronic / medical aid.
- Reference data: ICD-10 Code System + 34 curated WHO codes + 10 SA medical-aid schemes (Discovery, Bonitas, Momentum, Bestmed, Medshield, Profmed, Polmed, GEMS, Fedhealth, Keyhealth).
- Daily scheduler `flag_overdue_records` — HPCSA Booklet 9 / NHA §17 (6-year retention, paediatric to age 21, idempotent).
- SPA: Allergies + Conditions tabs, severe-allergy banner, Medical Aid card on Overview, reusable `MIcd10Picker`.
- Tests: 10 IntegrationTestCase + 4 retention (TDD) + 4 Playwright. All green.

### 2026-04-29 — Phase 1J (Issue #8): Daystar Health profile + password change (final SPA slice)
- Final slice of 5 wiring the `/daystar-health` SPA. Replaces the hardcoded provider profile with the logged-in user's real data and wires password change to Frappe's standard endpoint.
- New endpoint `medic_plus.api.daystar_health.get_my_practitioner_profile` — joins User (name / email / phone / image) with Healthcare Practitioner (department / HPCSA / practice number) via the Practice Member row, plus a top-level `two_factor_authentication` boolean from `frappe.utils.user.user_has_2fa`.
- Profile tab is **read-only** — fields render as styled disabled boxes; no Save button. Footer note directs users to their practice administrator for changes.
- Security tab posts current/new/confirm to `frappe.core.doctype.user.user.update_password`. Inline success/error feedback. 2FA state shown read-only with pointer to Frappe Desk for setup.
- Notifications tab removed from the profile sidebar — no schema backing (per Q8 design decision).
- Sidebar "Sign out" button was a route-change-only no-op; now calls `meridianApi.logout()` to actually end the session.
- Tests: 2 new Python (no-practice rejection + payload contract) + 2 new Playwright (read-only rendering + password change round-trip with a throwaway Practice user).
- **SPA wiring Phase 1 complete** (#4 → #5 → #6 → #7 → #8). Outstanding: #12 (Custom DocPerm fixtures for Practice roles).

### 2026-04-29 — Phase 1I (Issue #7): Daystar Health patient detail wired to composite endpoint
- Slice 4 of 5 wiring the `/daystar-health` SPA. Patient detail screen now hydrates all six tabs (Overview / Visits / Vitals / Medications / Labs / Notes) from a single composite call.
- New deep module `api/patient_summary` — `build_patient_summary(patient_name, practice)` orchestrator + pure `_format_patient_summary(...)` helper that applies per-tab caps (20 / 12 for vitals) and the POPIA whitelist (only `name / patient_name / dob / sex / mobile / email / status` make it into the patient block; `custom_sa_id_number` is unreachable).
- New whitelisted endpoint `medic_plus.api.daystar_health.get_patient_detail(patient)` — looks up the patient's `custom_practice` and raises `frappe.PermissionError` for cross-tenant requests, then returns the composite. Same error class as no-practice so callers cannot probe Practice membership.
- Tests: 4 Python (POPIA, per-tab caps, no-practice rejection, cross-tenant rejection) + 2 Playwright (detail loads all 6 tab containers; response body asserted POPIA-clean).
- Surfaced Issue #12: Practice Admin / Doctor / Receptionist roles don't have read permission on Patient via Custom DocPerm — workaround in place (Physician role on selfserve.test).

### 2026-04-29 — Phase 1H (Issue #6): Daystar Health patients list wired to REST resource API
- Slice 3 of 5 wiring the `/daystar-health` SPA. Patients screen now hydrates from `/api/resource/Patient` instead of `MH_DATA` mocks.
- Server-side pagination (real `limit_start/limit_page_length/total`), 300ms-debounced search across `patient_name/mobile/email` via `or_filters`, sortable headers (`patient_name`, `dob`), page-size selector (25/50/100) persisted in `sessionStorage`. Skeleton + error + empty-state UI.
- No new backend endpoint — PQC (`get_patient_permission_query`) handles tenant scoping for free.
- Per design decisions: dropped risk/status/provider filter chips, MRN column, risk badge, status pill, conditions/allergies columns, last-seen column (covered later via patient detail), checkboxes/bulk actions, Export/Register buttons. Sidebar nav now has `data-testid={`nav-${key}`}` on every button for deterministic Playwright navigation.
- Tests: 2 Python PQC contract tests (Doctor restricted to Practice; orphan gets `1=0`) + 5 Playwright tests (list render, search round-trip, prev/next pagination, page-size persistence, empty state).

### 2026-04-29 — Phase 1G (Issue #5): Daystar Health dashboard wired to live Practice data
- Slice 2 of 5 wiring the `/daystar-health` SPA. Dashboard now hydrates from a real composite endpoint instead of `MH_DATA` mocks.
- New deep module `api/dashboard_aggregator` — `build_dashboard(practice, user)` orchestrator + pure `_format_dashboard(...)` helper for testable shaping rules (greeting personalisation, week-volume always 7 days, recent-patients cap of 6, today-appointment status breakdown using the real Healthcare statuses).
- New whitelisted endpoint `medic_plus.api.daystar_health.get_dashboard` — thin orchestrator. Surfaces `frappe.PermissionError` from `practice_resolver` unchanged so the SPA can render the no-practice card.
- Dashboard screen rewrite in `meridian-dashboard.jsx`: skeletons during load, error toast + inline error card on failure, three KPI tiles (today's appointments / active patients / outstanding labs), today's schedule, week-volume chart, recent-patients table.
- Per design decision: dropped "Pending refills" KPI, "Needs attention" panel, MRN/Risk/Status columns, Day/Week/Month toggle, "New appointment" button. "View full schedule" links to Frappe Desk Patient Appointment list scoped to today + Practice.
- Outstanding labs KPI uses a JOIN through `Patient.custom_practice` since `Lab Test` has no `custom_practice` field — avoided schema migration.
- Tests: 4 format-helper unit tests + 2 endpoint contract tests + 1 Playwright dashboard render test (uses a temporary Practice Member row for Administrator with role=Admin to bypass the Doctor→Practitioner validation).

### 2026-04-29 — Phase 1F (Issue #4): Daystar Health SPA — auth flow wired to Frappe
- Slice 1 of 5 wiring the `/daystar-health` SPA to real Frappe APIs.
- New `practice_resolver.get_active_practice(user)` deep module — returns the user's active Practice or raises `frappe.PermissionError` for Guest / no-membership users. Reusable across all later Daystar Health endpoints.
- New page bootstrap `www/daystar_health.py` exposes `csrf_token`, `session_user`, and `has_practice` to the SPA template; new `meridian-api.js` helper centralises CSRF + JSON conventions for every later screen (`call`, `resource`, `login`, `recoverPassword`, `logout`).
- Replaced mock auth in `meridian-auth.jsx` with real `/api/method/login` and `frappe.core.doctype.user.user.reset_password` calls. New `MNoPracticeScreen` for authenticated users without a Practice Member row, with sign-out wired to `/api/method/logout`.
- SPA first-render routing reads the bootstrap and chooses login / no-practice / dashboard at mount time — no more login-screen flicker for already-authenticated users.
- Tests: 3 Python unit tests for `practice_resolver` + 5 Playwright tests covering anonymous, invalid creds, post-login routing, already-logged-in skip, and sign-out.
- Bug fix: renamed `daystar-health.py` → `daystar_health.py` so Frappe's website controller resolver finds it (resolver maps hyphenated `.html` to underscored `.py`).

### 2026-04-22 — Phase 6: Doctor Self-Registration (OTP + Yoco)
- New 3-step `/signup` funnel: details → email OTP → Yoco checkout. Replaces `/register` and `/register/doctor` (deleted).
- Yoco webhook auto-provisions on `payment.succeeded` (no admin approval). Idempotent re-fires; failures flip the PRR to `Provisioning Failed` with the traceback recorded.
- Post-payment activation uses a signed one-time URL (12-hr TTL, SHA-256 hashed in Redis), surfaced via email and consumed at `/signup/complete` to set the password and auto-log in.
- 15-min scheduler (`retry_failed_provisioning`) re-runs any PRR stuck Paid-but-not-Provisioned older than 5 min.
- Admin `onboard_doctor` refactored to call the same `provision_doctor` as the paid path, so both produce identical tenants (Company + Practice + Practitioner + Practice Member + POS Profile + Folder + optional Warehouse + Setup Checklist).
- Migration patches: clean orphan Users from the legacy `Registration Request` flow (skipping System Users), then drop the DocType + table.
- Dev-only `_test_mark_paid` endpoint for hermetic Playwright E2E (gated on `developer_mode`).

### 2026-04-08 — Phase 3: Platform Owner Workspace
- Custom Workspace "Medic Plus Platform" — Administrator/Healthcare Administrator only
- 6 Number Cards: Total/Active Practices, Total Patients, Today's/This Month's Appointments, Sick Notes Issued
- 3 Dashboard Charts: Appointments Over Time (line), Practices by Plan (donut), Patients per Practice (bar)
- 6 Quick Access shortcuts + 3 Recent Activity quick lists
- All exported as fixtures (Number Card, Dashboard Chart, Workspace) via hooks.py

### 2026-04-08 — Phase 2: Email OTP Booking Verification
- Added `request_booking_otp` and `verify_and_book` APIs
- OTP generated and stored server-side in Redis (10 min TTL, single-use, rate-limited)
- Branded HTML OTP email + appointment confirmation email via `frappe.sendmail()`
- Booking portal rebuilt as 3-step flow: Details → OTP → Success
- Outbound email configured: `liz@thedaystar.co.za` via `mail.thedaystar.co.za:587`

### 2026-04-08 — Phase 1: Multi-Tenant Core
- New app `medic_plus` scaffolded and installed on `medic-demo-staging.thedaystar.co.za`
- DocTypes: `Practice`, `Practice Member`, `Sick Note`
- Roles: `Practice Admin`, `Practice Doctor`, `Practice Receptionist`
- Custom fields: `custom_practice` on Patient, Patient Appointment, Patient Encounter, Inpatient Record
- 8 Permission Query Conditions for full data isolation per practice
- `before_insert` doc_events auto-stamp `custom_practice` on all scoped records
- v16 `extend_doctype_class` mixin on Patient Appointment validates practitioner scope
- Public booking portal at `/book?practice=<slug>`
