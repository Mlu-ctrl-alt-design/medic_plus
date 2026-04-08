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
| `medic_plus.api.booking.create_appointment` | Book an appointment (creates patient if new) |

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
