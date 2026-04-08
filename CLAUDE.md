# CLAUDE.md — Medic Plus

Guidance for Claude Code working in this repository.

---

## Project Overview

**Medic Plus** (`medic_plus`) is a multi-tenant healthcare practice management platform built on ERPNext v16 + Healthcare module v16. Each doctor operates as a **Practice** (tenant), isolated via Permission Query Conditions — no Company-based isolation, no Frappe User Permissions.

**Site:** `medic-demo-staging.thedaystar.co.za`
**Bench path:** `/home/fruppa/frappe-bench`
**App path:** `/home/fruppa/frappe-bench/apps/medic_plus`

**Installed apps:** frappe 16.13, erpnext 16.12, healthcare 16.0, marley_frontend, payments, medic_plus

---

## Architecture: Practice-as-Tenant

| Concept | Implementation |
|---------|---------------|
| Tenant | `Practice` doctype |
| Membership | `Practice Member` (User → Practice, role: Admin/Doctor/Receptionist) |
| Data isolation | Permission Query Conditions in `api/permissions.py` + `hooks.py` |
| Custom fields | Fixtures in `fixtures/custom_field.json` — never create via UI |
| Frontend | `marley_frontend` app (React SPA) — referred to as "Moli" in some PRD docs |

**Never use Company or Frappe User Permissions for tenant scoping.** The isolation model is entirely `custom_practice` Link fields + Permission Query Conditions.

---

## Git Workflow

### Branch strategy

```
main          ← production-ready, tagged releases only
  └── develop ← integration branch, all features merge here first
        └── feature/phase-{X}{letter}-{description}  ← one branch per phase/feature
```

### Branch naming

```
feature/phase-1a-foundation
feature/phase-1b-onboarding
feature/phase-1c-sick-notes
feature/phase-1d-prescriptions
feature/phase-1e-dispensing
feature/phase-1f-moli-frontend
fix/description-of-bug
chore/description
```

### Starting a feature branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/phase-{X}{letter}-{description}
```

### Completing a feature branch

```bash
# 1. Commit all work on the feature branch (see commit rules below)
git add <specific files>
git commit -m "feat: ..."

# 2. Merge to develop
git checkout develop
git merge feature/phase-{X}{letter}-{description}

# 3. Tag phase completions on develop
git tag -a v0.1.{N} -m "Phase 1X complete: description"

# 4. Push
git push origin develop --tags
```

**Never commit directly to `main` or `develop`.** Always work on a feature branch and merge via the sequence above.

### Commit rules

- **Atomic:** one logical concern per commit
- **Format:** `{type}: {description}` — types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
- **Passing:** all tests pass at every commit
- **File scope:** always `git add <specific files>`, never `git add -A`

### Commit message examples

```
feat: add practitioner SA fields and dispensing flag via fixtures
feat: implement doctor onboarding API endpoint
feat: enhance Sick Note with SA compliance fields and print format
feat: add prescription print format with NAPPI and schedule badge
feat: add dispense action and dispensary stock management
fix: guard dispensary provisioning against duplicate warehouse creation
test: add cross-tenant isolation tests for Patient
```

---

## Development Rules

### Custom fields
- **Always** define in `fixtures/custom_field.json` with `"module": "Medic Plus"`
- **Always** add the field name to the `hooks.py` fixtures filter list
- **Never** create custom fields via the Frappe UI (they won't be version-controlled)
- After adding: `bench --site medic-demo-staging.thedaystar.co.za migrate`

### Hooks
- All `doc_events`, `permission_query_conditions`, `extend_doctype_class` go in `hooks.py`
- Doc event handlers go in `api/doc_events.py`
- Permission query functions go in `api/permissions.py`

### Whitelisted APIs
- All public API endpoints go in `api/` with one file per domain:
  - `api/onboarding.py` — tenant provisioning
  - `api/dispense.py` — stock dispensing
  - `api/booking.py` — patient self-booking
  - `api/permissions.py` — permission query conditions (not endpoints)
  - `api/doc_events.py` — document lifecycle hooks (not endpoints)
- Always guard with role check: `if "System Manager" not in frappe.get_roles(): frappe.throw(...)`
- Always wrap multi-document operations in try/except with `frappe.db.rollback()` on failure

### Print formats
- Jinja templates in `print_format/{format_name}/{format_name}.html`
- Registered in `fixtures/print_format.json` with `"module": "Medic Plus"`
- Use `frappe.get_doc()` sparingly in templates — prefer `frappe.db.get_value()` for single fields

### Tests
- Use `frappe.tests.utils.FrappeTestCase`
- Every feature must have a cross-tenant isolation test: create 2 Practices, assert Doctor A cannot read Doctor B's records
- Run: `bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus`

### Never
- Modify ERPNext, Healthcare, or any other app's source files
- Use `frappe.db.sql()` raw queries where ORM works
- Commit `.pyc` files, `__pycache__`, or `node_modules`
- Use `git add -A` or `git add .`

---

## Existing Doctypes

| Doctype | Module | Purpose |
|---------|--------|---------|
| `Practice` | Medic Plus | Tenant entity — one per doctor/clinic |
| `Practice Member` | Medic Plus | Links User → Practice with role |
| `Sick Note` | Medic Plus | Submittable sick note with SA compliance fields |

## Custom Fields on Standard Doctypes

| Doctype | Field | Type | Purpose |
|---------|-------|------|---------|
| Patient | `custom_practice` | Link → Practice | Tenant scoping |
| Patient Appointment | `custom_practice` | Link → Practice | Tenant scoping |
| Patient Encounter | `custom_practice` | Link → Practice | Tenant scoping |
| Inpatient Record | `custom_practice` | Link → Practice | Tenant scoping |
| Healthcare Practitioner | `custom_hpcsa_number` | Data | HPCSA registration |
| Healthcare Practitioner | `custom_practice_number` | Data | SA practice billing number |
| Healthcare Practitioner | `custom_practitioner_signature` | Signature | Appears on sick notes and prescriptions |
| Healthcare Practitioner | `custom_is_dispensing_doctor` | Check | Triggers warehouse provisioning |
| Item | `custom_schedule` | Select (S0–S8) | SA medicines scheduling classification |
| Item | `custom_nappi_code` | Data | National Pharmaceutical Product Interface code |
| Warehouse | `custom_practice` | Link → Practice | Scopes dispensary to practice |
| Stock Entry | `custom_practice` | Link → Practice | Scopes stock entries to practice |

## Permission Query Conditions

All defined in `api/permissions.py`, registered in `hooks.py`:

| Doctype | Query function |
|---------|---------------|
| Practice | `get_practice_permission_query` |
| Practice Member | `get_practice_permission_query` |
| Patient | `get_patient_permission_query` |
| Patient Appointment | `get_patient_appointment_permission_query` |
| Patient Encounter | `get_patient_encounter_permission_query` |
| Inpatient Record | `get_inpatient_record_permission_query` |
| Sick Note | `get_sick_note_permission_query` |
| Healthcare Practitioner | `get_healthcare_practitioner_permission_query` |
| Stock Entry | `get_stock_entry_permission_query` |
| Warehouse | `get_warehouse_permission_query` |

`Healthcare Administrator` role bypasses all queries (platform admin).

---

## Bench Commands

```bash
# Apply schema + fixture changes
bench --site medic-demo-staging.thedaystar.co.za migrate

# Run app tests
bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus

# Export fixtures after UI changes (use sparingly — prefer code-first)
bench --site medic-demo-staging.thedaystar.co.za export-fixtures --app medic_plus

# Clear cache after hooks.py changes
bench --site medic-demo-staging.thedaystar.co.za clear-cache

# Restart workers after Python changes
bench restart
```

---

## Repositories

All repos under `github.com/mlu-ctrl-alt-design`.

---

## Phase 1 Status

| Phase | Branch | Status | Tag |
|-------|--------|--------|-----|
| 1A — Practitioner fields + medicine catalogue | `feature/phase-1a-practitioner-fields` | ✅ Merged | v0.1.1a |
| 1B — Doctor onboarding API | `feature/phase-1b-onboarding` | ✅ Merged | v0.1.1b |
| 1C — Sick Note SA compliance + print format | `feature/phase-1c-sick-notes` | ✅ Merged | v0.1.1c |
| 1D — Prescription print format | `feature/phase-1d-prescriptions` | ✅ Merged | v0.1.1d |
| 1E — Dispensing + stock management | `feature/phase-1e-dispensing` | ✅ Merged | v0.1.1e |
| 1F — Marley frontend integration | `feature/phase-1f-moli-frontend` | 🔲 Pending | — |
