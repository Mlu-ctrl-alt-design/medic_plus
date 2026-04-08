# techspec.md — Medic Plus

Living technical specification. Every feature, bugfix, refactor, and design decision is logged here with dates.

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

---

## Roadmap

- [ ] Prescription print format — Jinja, per-practice letterhead
- [ ] Sick Note print format — Jinja, per-practice letterhead
- [ ] Practice self-registration web form
- [ ] Patient portal — login, view appointments, sick notes, prescriptions
- [ ] Inpatient management dashboard
- [ ] Subscription billing integration
- [ ] SMS/WhatsApp OTP option (Africa's Talking)
- [ ] Unit tests — Practice, Practice Member, Sick Note, booking APIs
