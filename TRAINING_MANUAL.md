# Medic Plus — Developer Training Manual

**App:** `medic_plus` · **Bench:** `/home/fruppa/frappe-bench` · **Site:** `medic-demo-staging.thedaystar.co.za`
**Stack:** Frappe v16 · ERPNext v16 · Healthcare v16 · Python 3.12 · MariaDB · Redis

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture — Practice-as-Tenant](#2-architecture--practice-as-tenant)
3. [DocTypes Reference](#3-doctypes-reference)
4. [Permission Query Conditions](#4-permission-query-conditions)
5. [API Layer](#5-api-layer)
6. [Subscription & Billing (Feature Gates)](#6-subscription--billing-feature-gates)
7. [Patient Data Masking & POPIA Compliance](#7-patient-data-masking--popia-compliance)
8. [Inpatient Dashboard](#8-inpatient-dashboard)
9. [Patient-Facing Pages](#9-patient-facing-pages)
10. [Workspace & Dashboards](#10-workspace--dashboards)
11. [Fixtures](#11-fixtures)
12. [Testing — Unit & Integration](#12-testing--unit--integration)
13. [Testing — Playwright UI Tests](#13-testing--playwright-ui-tests)
14. [Git Workflow](#14-git-workflow)
15. [Deployment & CI/CD](#15-deployment--cicd)
16. [Common Patterns & Conventions](#16-common-patterns--conventions)
17. [Troubleshooting](#17-troubleshooting)

---

## 1. Project Overview

Medic Plus is a **multi-tenant healthcare practice management SaaS** built on the Frappe Healthcare module. Each doctor or clinic operates as an independent **Practice** (tenant). All their data — patients, appointments, encounters, sick notes, dispensary stock — is scoped to that Practice and invisible to other tenants.

### What has been built (as of April 2026)

| Phase | Feature | Status |
|-------|---------|--------|
| 1A | Practitioner SA fields, dispensing flag, medicine catalogue custom fields | ✅ Done |
| 1B | Doctor onboarding API — creates Practice + User + PracticeMember atomically | ✅ Done |
| 1C | Sick Note doctype — SA compliance fields, Jinja print format | ✅ Done |
| 1D | Prescription print format (NAPPI codes, schedule badge, signature) | ✅ Done |
| 1E | Dispensing action + dispensary stock management | ✅ Done |
| 2 | Public booking portal with server-side email OTP | ✅ Done |
| 3A | Platform Owner workspace (KPIs, charts, shortcuts) | ✅ Done |
| 3B | Subscription billing (Paystack) + plan feature gates | ✅ Done |
| 3C | Practice Setup Checklist, patient portal, patient-role PQC isolation | ✅ Done |
| 3D | Patient data masking + two-sided OTP consent (POPIA hardening) | ✅ Done |
| 3E | Inpatient Dashboard (Frappe Page) + inpatient API | ✅ Done |
| — | Full Playwright UI test suite (44 tests) | ✅ Done |

---

## 2. Architecture — Practice-as-Tenant

### Core concept

```
Frappe Site (one shared database)
  └── Practice A  ← tenant 1
  └── Practice B  ← tenant 2
  └── Practice C  ← tenant 3
```

A `Practice` record is the tenant boundary. There are **no Companies** involved. Data isolation is enforced entirely through **Permission Query Conditions** (PQCs) — SQL `WHERE` clauses that Frappe injects into every ORM query.

### Membership model

```
User ──┐
       ├── Practice Member (role: Admin / Doctor / Receptionist)
       └──> Practice
```

When a user logs in, `_get_user_practice()` in `api/permissions.py` returns their practice by looking up their `Practice Member` record. This value is used in every PQC.

### Platform admin bypass

Any user with the **Healthcare Administrator** role bypasses all PQCs and sees all practices. `_is_platform_admin()` checks for this role:

```python
def _is_platform_admin(user: str = None) -> bool:
    return "Healthcare Administrator" in frappe.get_roles(user or frappe.session.user)
```

**Always pass the `user` parameter explicitly** — do not rely on `frappe.session.user` in PQC functions (background jobs run under different user contexts).

### Custom fields for isolation

Every Healthcare DocType that needs practice scoping carries a `custom_practice` Link field (defined in `fixtures/custom_field.json`):

| DocType | Field | Set by |
|---------|-------|--------|
| Patient | `custom_practice` | `before_insert` hook |
| Patient Appointment | `custom_practice` | `before_insert` hook |
| Patient Encounter | `custom_practice` | `before_insert` hook |
| Inpatient Record | `custom_practice` | `before_insert` hook |
| Warehouse | `custom_practice` | Dispensary provisioning |
| Stock Entry | `custom_practice` | Dispensing action |

---

## 3. DocTypes Reference

### Practice

**File:** `medic_plus/medic_plus/doctype/practice/`
**Naming:** `PRAC-.#####` (Expression old style)
**Purpose:** Tenant entity — one per doctor/clinic.

Key fields:
- `practice_name` — display name
- `slug` — URL-safe unique identifier (auto-generated, used in public booking URLs)
- `is_active` — can be deactivated without deleting
- `subscription_plan` — `Free` / `Basic` / `Pro` (Select field)
- `subscription_status` — `Active` / `Trialing` / `Past Due` / `Cancelled`
- `owner_practitioner` — Link to Healthcare Practitioner
- `company` — Link to ERPNext Company (for stock/billing)
- `color`, `logo` — branding for the booking portal

Controller behaviour:
- `before_insert`: auto-generates `slug` from `practice_name` if blank; validates slug uniqueness
- `after_insert`: auto-creates a default `Practitioner Schedule`

### Practice Member

**File:** `medic_plus/medic_plus/doctype/practice_member/`
**Naming:** `PM-.#####`
**Purpose:** Junction between a Frappe User and a Practice, with a role.

Key fields: `practice`, `user`, `role` (Admin/Doctor/Receptionist), `practitioner` (required for Doctor role)

Controller behaviour:
- `after_save`: assigns the corresponding Frappe role (`Practice Admin` / `Practice Doctor` / `Practice Receptionist`) to the User
- `on_trash`: removes the role if no other Practice Member record still grants it

### Sick Note

**File:** `medic_plus/medic_plus/doctype/sick_note/`
**Naming:** `SN-.YYYY.-.#####`
**Purpose:** Submittable sick certificate (SA HPCSA-compliant).

Workflow: Draft → Submitted → Cancelled/Amended

`before_insert`: auto-sets `practice` from session user's Practice Member.
`on_submit`: creates a Patient Medical Record linked to the patient.

### Practice Setup Checklist

**File:** `medic_plus/medic_plus/doctype/practice_setup_checklist/`
**Purpose:** Tracks onboarding progress. Six steps, each with a `completed` checkbox and `completed_on` date.

Steps:
1. Practice profile completed
2. Practitioner profile completed
3. First patient added
4. First appointment scheduled
5. Practitioner schedule created (auto-completed by `doc_events.py` when a Practitioner Schedule is saved)
6. First billing invoice (auto-completed when a Sales Invoice with a matching practice company is submitted)

### Data Unmask Request

**File:** `medic_plus/medic_plus/doctype/data_unmask_request/`
**Naming:** `DMR-.YYYY.-.#####`
**Purpose:** State machine for two-sided OTP consent (POPIA). Statuses: `Pending` → `Verified` / `Expired` / `Denied`.

Stores SHA-256 hashes of the two OTPs (never the plaintext). See Section 7 for full flow.

### Clinical Access Log

**File:** `medic_plus/medic_plus/doctype/clinical_access_log/`
**Naming:** `CAL-.YYYY.-.#####`
**Purpose:** Append-only audit trail for every successful data unmask. Written by `verify_unmask()`. Never writable by users directly.

### Medic Plus Settings

**File:** `medic_plus/medic_plus/doctype/medic_plus_settings/`
**Purpose:** Single-instance settings doctype for platform-wide configuration (Paystack keys, etc.).

### Practice Registration Request

**File:** `medic_plus/medic_plus/doctype/practice_registration_request/`
**Purpose:** Holds a pending self-registration before the admin approves and converts it to a full Practice + User. (Phase 6 implementation pending.)

---

## 4. Permission Query Conditions

All PQCs live in `medic_plus/api/permissions.py` and are registered in `hooks.py` under `permission_query_conditions`.

### Pattern

Every PQC follows this structure:

```python
def get_xxx_permission_query(user: str = None) -> str:
    if _is_platform_admin(user):
        return ""                             # no restriction for Healthcare Administrator
    practice = _get_user_practice(user)
    if not practice:
        return "1=0"                          # no practice = see nothing
    return f"`tabDocType`.`field` = {frappe.db.escape(practice)}"
```

### Registered PQCs

| DocType | Function |
|---------|----------|
| Practice | `get_practice_permission_query` |
| Practice Member | `get_practice_member_permission_query` |
| Patient | `get_patient_permission_query` |
| Patient Appointment | `get_patient_appointment_permission_query` |
| Patient Encounter | `get_patient_encounter_permission_query` |
| Inpatient Record | `get_inpatient_record_permission_query` |
| Sick Note | `get_sick_note_permission_query` |
| Healthcare Practitioner | `get_healthcare_practitioner_permission_query` |
| Warehouse | `get_warehouse_permission_query` |
| Stock Entry | `get_stock_entry_permission_query` |
| Data Unmask Request | `get_data_unmask_request_permission_query` |
| Clinical Access Log | `get_clinical_access_log_permission_query` |

### Patient-role branch

Patients get a Frappe User with the `Patient` role. Their PQC branches differently — they see only their own records (matched by `User.email == Patient.email`):

```python
if "Patient" in frappe.get_roles(user or frappe.session.user):
    patient = _get_patient_name_for_user(user)
    return f"`tabPatient`.`name` = ..." if patient else "1=0"
```

### Adding a new PQC

1. Write the function in `api/permissions.py`
2. Register in `hooks.py`:
   ```python
   permission_query_conditions = {
       "New DocType": "medic_plus.api.permissions.get_new_doctype_permission_query",
   }
   ```
3. Add a `custom_practice` field to the DocType if it needs practice scoping
4. Write isolation unit tests (two practices, verify cross-tenant blind)

---

## 5. API Layer

All API files live in `medic_plus/api/`. One file per domain.

### File map

| File | Purpose |
|------|---------|
| `onboarding.py` | `onboard_doctor()` — atomic Practice + User + Member creation |
| `booking.py` | Guest booking portal APIs (OTP request/verify, availability) |
| `billing.py` | Subscription plans, Paystack checkout, `require_feature` decorator |
| `inpatient.py` | Inpatient dashboard stats and patient list |
| `data_access.py` | Patient data masking, two-sided OTP consent |
| `dispense.py` | Dispensary stock management |
| `permissions.py` | PQC functions + helper utilities (not endpoints) |
| `doc_events.py` | Document lifecycle hooks (not endpoints) |
| `mixins.py` | `PracticeAwareMixin` for `extend_doctype_class` |

### API conventions

Every public endpoint must:
1. Be decorated with `@frappe.whitelist()`
2. Check permissions inside the function — never trust the caller
3. Use `frappe.throw(..., frappe.PermissionError)` to raise 403s
4. Wrap multi-document operations in try/except with `frappe.db.rollback()` on failure

### `onboard_doctor()` flow

Called by the signup form. Creates in one atomic transaction:
1. `Healthcare Practitioner` — SA fields (HPCSA number, practice number, signature)
2. `Practice` — tenant record, sets subscription_plan=Free
3. Frappe `User` — email login, password, language
4. `Practice Member` — links User → Practice with role=Admin
5. `Practice Setup Checklist` — blank checklist for the new practice

### Auto-stamping `custom_practice`

`doc_events.py` registers `before_insert` hooks on all scoped doctypes. `set_practice_on_insert()` reads the session user's Practice Member and writes `custom_practice`:

```python
def set_practice_on_insert(doc, method):
    if doc.get("custom_practice"):
        return
    practice = _get_user_practice()
    if practice:
        doc.custom_practice = practice
```

---

## 6. Subscription & Billing (Feature Gates)

### Plan catalogue

Defined in code in `billing.py` (`MEDIC_PLANS` dict). Three tiers:

| Plan | Price | Patient limit | User limit | Inpatient module |
|------|-------|--------------|-----------|-----------------|
| Free | R 0 | 30 | 2 | ✗ |
| Basic | R 499/month | 100 | 3 | ✗ |
| Pro | R 999/month | Unlimited | Unlimited | ✓ |

The `Practice.subscription_plan` field stores the current tier key.

### `require_feature` decorator

Wrap any endpoint that should be plan-gated:

```python
from medic_plus.api.billing import require_feature

@frappe.whitelist()
@require_feature("inpatient_module")
def get_inpatient_summary():
    ...
```

`require_feature` calls `has_feature(practice, feature_key)`. If the feature is `False` for the practice's plan, it raises `frappe.PermissionError` (HTTP 403). Platform admins bypass the gate.

### Paystack integration

`initiate_paystack_checkout(plan_key)` creates a Paystack transaction and returns a redirect URL. The Paystack webhook at `paystack_webhook()` receives confirmation and updates `Practice.subscription_plan` + `subscription_status`.

Paystack keys are stored in `Medic Plus Settings`. If unset, `initiate_paystack_checkout` returns `{"status": "not_configured"}` instead of raising.

### Billing summary API

`get_billing_summary()` returns a single dict consumed by `/billing` page:

```json
{
  "plan_key": "Free",
  "plan_label": "Free / Trial",
  "price_label": "Free",
  "status": "Active",
  "features": { "appointments": true, "inpatient_module": false, ... },
  "usage": { "Patient": { "used": 12, "limit": 30 } },
  "available_plans": [ { "key": "Basic", ... }, { "key": "Pro", ... } ]
}
```

---

## 7. Patient Data Masking & POPIA Compliance

### Problem

South African law (POPIA) restricts access to sensitive patient identifiers. SA ID numbers, mobile numbers, and medical aid membership numbers must not be visible to any staff member without the patient's active consent.

### Solution: two-sided OTP consent

All logic is in `medic_plus/api/data_access.py`.

**Protected fields:**
- `Patient.custom_sa_id_number`
- `Patient.mobile`
- `Patient Insurance Policy.custom_membership_number`
- `Patient Insurance Policy.custom_dependant_code`

**Display:** A Frappe Client Script on the Patient form replaces these fields with masked values (e.g. `*** **** ****`) and adds a "View" button.

**Flow:**

```
Clinician clicks "View"
  └─> request_unmask(doctype, docname, fieldname)
        ├─> generates requester_otp + patient_otp (random.choices, 6 digits each)
        ├─> stores SHA-256 hashes in Data Unmask Request
        ├─> emails requester_otp to clinician
        ├─> emails patient_otp to patient
        └─> returns DMR name (+ plaintext OTPs in developer_mode for QA)

Clinician enters both OTPs into dialog
  └─> verify_unmask(dmr_name, requester_otp, patient_otp)
        ├─> checks request is Pending and not expired
        ├─> compares SHA-256(otp) against stored hashes
        ├─> marks DMR as Verified
        ├─> writes Clinical Access Log (immutable audit trail)
        └─> returns plaintext value (ONCE — never cached)

Patient can also deny
  └─> deny_unmask(dmr_name) [called from patient portal]
        └─> marks DMR as Denied
```

**OTP expiry:** 10 minutes. `expire_stale_requests()` is a scheduled task (every 15 min) that marks old Pending requests as Expired.

**Staging:** On `developer_mode=1`, `request_unmask()` includes both OTPs in plaintext in the response under `_dev_requester_otp` and `_dev_patient_otp` to enable QA without email delivery.

---

## 8. Inpatient Dashboard

### Frappe Page

Location: `medic_plus/medic_plus/page/inpatient_dashboard/`

Files:
- `inpatient_dashboard.json` — Page definition, roles
- `inpatient_dashboard.js` — Client-side JavaScript

The page renders:
- Four stat cards: Current Inpatients, Today's Admissions, Expected Discharges, Avg LOS
- Patient table (`#ipd-table-wrap`) with LOS, ward, status, primary practitioner
- "Refresh" toolbar button
- "New Admission" button → opens Inpatient Record form

### Backend APIs

**`get_inpatient_summary()`** — Returns the four headline stats.

**`get_current_inpatients()`** — Returns a list of all currently admitted patients. Each record includes `los_days` (computed from `admitted_datetime`) and `current_ward` (from the `Inpatient Occupancy` child table where `left=0`).

Both are gated by `@require_feature("inpatient_module")` — Free and Basic plan practices cannot call them.

### Practice scoping

`_get_practice_filter()` in `inpatient.py` returns `{"custom_practice": practice}` for practice staff or `{}` for platform admins, so admins see all inpatients across all practices.

---

## 9. Patient-Facing Pages

### Public booking portal (`/book`)

**URL:** `/book?practice=<slug>`
**Files:** `medic_plus/www/book/`

A Jinja-rendered three-step form:
1. Fill details (name, email, phone, doctor, date, time slot)
2. Enter 6-digit OTP (emailed by `request_booking_otp`)
3. Confirmation screen

OTP is generated server-side and stored in Redis (expires 10 min). Never touches the browser. `verify_and_book()` is atomic — the OTP is consumed only if the appointment is successfully created.

### Patient portal (`/portal`)

**URL:** `/portal` (requires login)
**Files:** `medic_plus/www/portal/`

Shows the logged-in patient's:
- Upcoming appointments
- Past appointments
- Issued sick notes (with "Download PDF" links)
- Pending data unmask requests (patient can deny here)

Guests are redirected to `/login`. The Patient role PQC ensures patients see only their own data.

### Registration page (`/register`)

**URL:** `/register`
**Files:** `medic_plus/www/register/`

Doctor self-registration form. Calls `onboard_doctor()`. (Full flow pending Phase 6.)

### Billing page (`/billing`)

**URL:** `/billing`
**Files:** `medic_plus/www/billing/`

Shows the current practice's plan, usage bars, feature chips, and upgrade options. Authenticated only — redirects to login otherwise.

---

## 10. Workspace & Dashboards

### Medic Plus Platform (admin workspace)

Visible to: `Administrator`, `Healthcare Administrator` only.

Sections:
- **Key Metrics:** 6 Number Cards (Total Practices, Active Practices, Total Patients, Today's Appointments, This Month's Appointments, Sick Notes Issued)
- **Analytics:** 3 Dashboard Charts (Appointments Over Time, Practices by Plan, Patients per Practice)
- **Quick Access:** 6 shortcuts (New Practice, Practice Members, All Patients, All Appointments, All Sick Notes, Email Account)
- **Recent Activity:** 3 quick lists

### Medic Plus Practice (doctor workspace)

Visible to: `Practice Admin`, `Practice Doctor`, `Practice Receptionist`.

Shows the doctor's own patients, appointments, sick notes, and a shortcut to the Inpatient Dashboard.

### Exporting workspace changes

If you edit the workspace in Desk, always export before committing:

```bash
bench --site medic-demo-staging.thedaystar.co.za export-fixtures --app medic_plus
```

Then check that `fixtures/workspace.json` contains **both** "Medic Plus Platform" and "Medic Plus Practice". The fixture filter in `hooks.py` is `{"filters": [["name", "like", "Medic Plus%"]]}`.

---

## 11. Fixtures

All configuration that must survive `bench migrate` on a fresh site is exported as fixtures. They live in `medic_plus/fixtures/` and are listed in `hooks.py → fixtures`.

| File | Contents |
|------|----------|
| `custom_field.json` | All `custom_*` fields on standard Healthcare doctypes |
| `role.json` | Practice Admin, Practice Doctor, Practice Receptionist roles |
| `workspace.json` | Both workspaces |
| `number_card.json` | 6 platform KPI cards |
| `dashboard_chart.json` | 3 platform charts |
| `print_format.json` | Sick Note, Prescription print formats |
| `client_script.json` | Patient data masking Client Script |

### Rules

- **Never create custom fields via the Frappe UI** — they won't be version-controlled.
- Always set `"module": "Medic Plus"` on every fixture record.
- After adding a new custom field to `custom_field.json`, add the field name to the `fixtures` list in `hooks.py` (the filter key), then run `bench migrate`.

---

## 12. Testing — Unit & Integration

Test files follow the `test_<feature>.py` naming convention, co-located with the module under test (e.g. `medic_plus/api/test_billing.py`).

### Running tests

```bash
bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus
```

### Required coverage per feature

Every feature must include:

1. **Happy path** — the thing it does when everything is correct
2. **Cross-tenant isolation** — create 2 Practices; assert Doctor A cannot read Doctor B's records
3. **Permission boundary** — assert unauthenticated / wrong-role access is blocked

### Python 3.14 + Frappe mock setup

Frappe uses `LocalProxy` for `frappe.session`, `frappe.conf`, etc. Python 3.14 changed how `mock._is_async_obj` works — it now propagates `RuntimeError` from unbound `LocalProxy` objects rather than swallowing it.

Every test module that patches Frappe internals must bind the `LocalProxy` ContextVar in `setUpModule()`:

```python
def setUpModule():
    import frappe.local
    ctx = frappe._get_context()
    ctx.session = frappe._dict(user="Administrator")
    ctx.conf = frappe._dict(developer_mode=1)
    ctx.flags = frappe._dict()
    ctx.lang = "en"
    ctx.message_log = []
    ctx.error_log = []
    ctx.debug_log = []
    ctx.response = frappe._dict()
    frappe.local = ctx
    frappe.cache = mock.MagicMock()
```

(See `api/test_data_access.py` for the authoritative example.)

---

## 13. Testing — Playwright UI Tests

**Location:** `medic_plus/tests/ui/`
**Run command:**

```bash
cd /home/fruppa/frappe-bench
env/bin/python -m pytest apps/medic_plus/medic_plus/tests/ui/ -v
```

### Test files

| File | Tests |
|------|-------|
| `test_doctor_signup.py` | Admin login, onboarding API, Practice list, role assignment, doctor login |
| `test_patient_invite.py` | Patient creation (desk form + API), kiosk registration page, patient visibility |
| `test_billing.py` | Billing page access, content rendering, all billing API endpoints |
| `test_inpatient_dashboard.py` | Dashboard page load, stat cards, empty state, API shape, feature gate |

All 44 tests pass on staging (1 skipped when no inpatients are admitted).

### `conftest.py` fixtures

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `browser_context_args` | session | Sets `ignore_https_errors=True` (staging self-signed cert) |
| `set_default_timeout` | function | 90-second default timeout (Frappe loads many JS assets) |
| `logged_in_admin_page` | function | Returns a `Page` already logged in as Administrator |
| `admin_api_session` | session | `urllib` opener authenticated as Administrator for direct API calls |

`_frappe_login(page, user, password)` is a shared helper. It navigates to `/login`, fills the credentials, and waits for the `/app` redirect. It short-circuits if already on `/app` or `/desk`.

### Locator conventions

**Scope locators tightly.** The most common Playwright failure in Frappe is a strict-mode violation — a locator that matches multiple elements:

```python
# BAD — "Current Inpatients" also appears in "No current inpatients." paragraph
expect(page.get_by_text("Current Inpatients", exact=False)).to_be_visible()

# GOOD — scoped to the stat card label
expect(page.locator(".stat-card .stat-label", has_text="Current Inpatients")).to_be_visible()
```

### Second-session permission tests (feature gates)

Testing that a Free-plan user is blocked requires a separate authenticated session. **Do not** use a second Playwright browser page — Frappe's 403 redirect handler navigates the page to `/login`, destroying the `page.evaluate` execution context.

Instead, use Python `urllib` with a `CookieJar`:

```python
import urllib.request, urllib.parse, http.cookiejar, ssl, json, re

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE
_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_jar),
    urllib.request.HTTPSHandler(context=_ssl_ctx),
)

def _post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, body,
          headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _opener.open(req) as resp:
        return json.loads(resp.read())

# 1. Login
_post(f"{BASE_URL}/api/method/login", {"usr": email, "pwd": password})

# 2. Get CSRF token from desk HTML
with _opener.open(urllib.request.Request(f"{BASE_URL}/desk")) as resp:
    desk_html = resp.read().decode("utf-8", errors="replace")
csrf = re.search(r'"csrf_token"\s*:\s*"([^"]+)"', desk_html).group(1)

# 3. Call the API
req = urllib.request.Request(
    f"{BASE_URL}/api/method/medic_plus.api.inpatient.get_inpatient_summary",
    "".encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded",
             "X-Frappe-CSRF-Token": csrf},
)
try:
    with _opener.open(req) as resp:
        result = json.loads(resp.read())
except urllib.request.HTTPError as e:
    result = {"exc": str(e), "status_code": e.code}
```

### Frappe `frappe.call` error handler behaviour

Frappe's `request.js` handles HTTP errors differently depending on status:

| Status | Behaviour |
|--------|-----------|
| 403 | Calls `error_callback()` with **no arguments** (redirects guest to login). `xhr` is `undefined` in the JS error handler — `xhr.responseText` throws, so `exc='Unknown error'`, `exc_type='ServerError'` |
| 417 | Calls `error_callback(r)` with the parsed response body — `exc` contains the Python traceback |
| 500 | Same as 417 |

When asserting a 403 permission block from within `frappe.call`, check for `exc_type == 'ServerError'` (not just for "PermissionError" in the exc string):

```python
has_error = (
    result.get("exc") is not None
    or result.get("exc_type") == "ServerError"
    or result.get("status_code") in (403, 417)
    or result.get("message") is None
)
```

---

## 14. Git Workflow

### Branch strategy

```
main          ← production-ready, tagged releases only
  └── develop ← integration branch, all features merge here first
        └── feature/phase-{X}{letter}-{description}
```

### Daily workflow

```bash
# Start work
git checkout develop
git pull origin develop
git checkout -b feature/phase-Nx-description

# Work, then commit atomically
git add medic_plus/api/new_feature.py medic_plus/tests/ui/test_new_feature.py
git commit -m "feat: add new feature with Playwright tests"

# Merge back to develop
git checkout develop
git merge feature/phase-Nx-description
git push origin develop

# Tag a release
git tag -a v0.1.Nx -m "Phase Nx complete: description"
git push origin develop --tags
```

### Commit message format

```
{type}: {description}
```

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`

### Rules

- One logical concern per commit
- All tests pass at every commit
- `git add <specific files>` only — never `git add -A`
- Never commit directly to `main` or `develop`

---

## 15. Deployment & CI/CD

### Two-server setup

| Server | Role | URL | Aliases |
|--------|------|-----|---------|
| This VPS (staging) | Development & testing | `medic-demo-staging.thedaystar.co.za` | `selfserve.thedaystar.co.za`, `ehealth-staging.thedaystar.co.za` |
| Remote VPS (production) | Live site | `medic-demo.thedaystar.co.za` | `ehealth.thedaystar.co.za` |

Code moves only via Git. Databases are never synced between environments. Aliases are nginx-level — both hostnames hit the same Frappe site, so users can transition off the legacy hostname without coordination.

### Production deploy

Tag a version to trigger GitHub Actions auto-deploy:

```bash
git tag -a v0.1.5 -m "feat: inpatient dashboard"
git push origin develop --tags
```

The workflow (`deploy-production.yml` in `.github/workflows/`) on the `medic_plus` repo:
1. Backs up the production database
2. Checks out the tag in `apps/medic_plus`
3. Runs `bench migrate`
4. Runs `bench build --app medic_plus`
5. Restarts workers
6. Clears cache
7. Health-checks the site

### Pre-deploy checklist

Before tagging:
- [ ] `bench --site medic-demo-staging.thedaystar.co.za migrate` succeeds cleanly
- [ ] All unit tests pass: `bench run-tests --app medic_plus`
- [ ] All UI tests pass: `env/bin/python -m pytest apps/medic_plus/medic_plus/tests/ui/ -v`
- [ ] `techspec.md` updated with new features
- [ ] No uncommitted fixture changes (export first)

### Rollback

If something breaks after a deploy, trigger `rollback-production.yml` manually from GitHub Actions with the previous tag as `rollback_ref`.

---

## 16. Common Patterns & Conventions

### Adding a new whitelisted API endpoint

1. Create or open the relevant `api/<domain>.py` file
2. Decorate with `@frappe.whitelist()`
3. Add `@require_feature(...)` if plan-gated
4. Validate permissions inside — use `frappe.throw(..., frappe.PermissionError)` for 403s
5. Wrap multi-doc writes in try/except with `frappe.db.rollback()` on failure
6. Add a unit test in `api/test_<domain>.py`
7. Add Playwright tests in `tests/ui/test_<domain>.py`

### Adding a new DocType

1. Create via Frappe Desk (developer_mode=1 writes JSON to disk automatically)
2. Set naming: `"autoname": "PREFIX-.#####"`, `"naming_rule": "Expression (old style)"`
3. If it needs practice scoping: add `custom_practice` Link field and a PQC function
4. Register PQC in `hooks.py`
5. Export fixtures: `bench export-fixtures --app medic_plus`
6. Write cross-tenant isolation tests

### Adding a new custom field

1. Add the field to `fixtures/custom_field.json` with `"module": "Medic Plus"`
2. Add the field name to the `fixtures` list in `hooks.py`
3. Run `bench migrate`
4. Never add via Frappe UI

### Clearing cache after hooks.py changes

```bash
bench --site medic-demo-staging.thedaystar.co.za clear-cache
bench restart
```

### Doctype naming: never use UUID

```json
// WRONG
"naming_rule": "UUID"

// CORRECT
"autoname": "SN-.YYYY.-.#####",
"naming_rule": "Expression (old style)"
```

UUID names are opaque, break list views, and make debugging harder.

---

## 17. Troubleshooting

### Frappe `frappe.call` returns `{exc: 'Unknown error', exc_type: 'ServerError'}`

The server returned a 403. Frappe's 403 handler in `request.js` calls `error_callback()` with no arguments (it redirects guests to login). Inside your JS error handler, `xhr` is `undefined`, so `xhr.responseText` throws a TypeError — caught as "Unknown error". This is a 403 PermissionError, not an application error.

### `bench restart` is required after Python changes

Workers cache loaded modules. After editing any `.py` file that is not a test, run `bench restart` to propagate the change.

### `mute_emails: 1` silently drops all email

Staging sites have `mute_emails: 1`. Any `frappe.sendmail()` call silently does nothing. To test email locally, set it to `0` temporarily — but re-enable it immediately after (see CLAUDE.md troubleshooting: 502 error when mute_emails is off and SMTP rejects a recipient).

### `ModuleNotFoundError: No module named 'medic_plus'`

The app is not pip-installed in the virtualenv:

```bash
env/bin/pip install -e apps/medic_plus
bench --site medic-demo-staging.thedaystar.co.za migrate
bench restart
```

### Frappe strict mode violation in Playwright

A locator matched more than one element. Narrow it:
- Use `.locator(".parent .child", has_text="label")` instead of `get_by_text()`
- Add `.first` to pick the first match if exact scoping is not possible

### Playwright "Execution context was destroyed"

A `page.evaluate()` call triggered a navigation (redirect to login). Do not perform logout or session switching inside `page.evaluate()`. Use the Python `urllib` + `CookieJar` pattern for second-session tests (see Section 13).

### MariaDB root access

```bash
mysql -u root -p"H0bsZ4o7aB0WXhVkDL3qns1oko"
```

Password stored in CLAUDE.md (Staging Server Credentials section).
