"""Compose the Daystar Health dashboard payload.

The deep module orchestrates DB reads + payload shaping for the dashboard
screen. Splits into:

- ``build_dashboard(practice, user)`` — the public entry point that resolves
  the user's first name, runs the queries scoped to the Practice, and
  delegates to the format helper.
- ``_format_dashboard(...)`` — pure transformation; takes already-fetched
  values and returns the payload dict. Testable in isolation without a DB.
"""

from datetime import date, datetime, timedelta
from urllib.parse import urlencode

import frappe
from frappe.utils import format_date, getdate, today

# Statuses we treat as "outstanding" for the labs KPI. The Healthcare Lab Test
# lifecycle moves Open → Started → Approved/Completed; the first two are work
# the practitioner still owes the patient.
_OUTSTANDING_LAB_STATUSES = ("Open", "Started")


def build_dashboard(*, practice: str, user: str) -> dict:
    """Compose the Daystar Health dashboard payload for a given Practice."""
    from medic_plus.api.perf import track_call
    track_call("build_dashboard")
    user_doc = frappe.db.get_value(
        "User", user, ["first_name", "last_name"], as_dict=True
    ) or frappe._dict(first_name="", last_name="")

    today_date = getdate(today())
    today_iso = today_date.isoformat()

    # Today's appointments — list shaped for the schedule card AND counted for KPI.
    appt_rows = frappe.db.get_all(
        "Patient Appointment",
        filters={"custom_practice": practice, "appointment_date": today_iso},
        fields=[
            "name", "patient", "patient_name", "appointment_time",
            "duration", "practitioner", "practitioner_name", "status",
            "appointment_type",
        ],
        order_by="appointment_time asc",
    )
    today_appointments = [
        {
            "id": r.name,
            "patient_id": r.patient,
            "patient_name": r.patient_name or "",
            "time": _format_time(r.appointment_time),
            "duration": int(r.duration or 0),
            "practitioner": r.practitioner_name or r.practitioner or "",
            "reason": r.appointment_type or "",
            "status": r.status or "",
        }
        for r in appt_rows
    ]

    # Active patient count for the Practice.
    active_patient_count = frappe.db.count(
        "Patient",
        filters={"custom_practice": practice, "status": "Active"},
    )

    # Outstanding labs: Lab Test has no custom_practice field, so we scope via
    # the patient's tenant link.
    outstanding_lab_count = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabLab Test` lt
        INNER JOIN `tabPatient` p ON p.name = lt.patient
        WHERE p.custom_practice = %(practice)s
          AND lt.status IN %(statuses)s
        """,
        {"practice": practice, "statuses": _OUTSTANDING_LAB_STATUSES},
    )[0][0]

    # Week volume: encounters per day for the last 7 days, keyed by short
    # weekday name so the format helper can fill missing days with 0.
    week_start = today_date - timedelta(days=6)
    encounter_rows = frappe.db.get_all(
        "Patient Encounter",
        filters={
            "custom_practice": practice,
            "encounter_date": [">=", week_start.isoformat()],
        },
        fields=["encounter_date"],
        limit_page_length=0,
    )
    weekly_counts: dict = {}
    for row in encounter_rows:
        d = getdate(row.encounter_date)
        key = d.strftime("%a")
        weekly_counts[key] = weekly_counts.get(key, 0) + 1

    # Recent patients: latest 6 with at least one encounter, ordered by most
    # recent encounter date.
    recent_rows = frappe.db.sql(
        """
        SELECT p.name AS id, p.patient_name AS name,
               TIMESTAMPDIFF(YEAR, p.dob, CURDATE()) AS age,
               p.sex,
               MAX(e.encounter_date) AS last_seen
        FROM `tabPatient` p
        INNER JOIN `tabPatient Encounter` e ON e.patient = p.name
        WHERE p.custom_practice = %(practice)s
        GROUP BY p.name, p.patient_name, p.dob, p.sex
        ORDER BY last_seen DESC
        LIMIT 12
        """,
        {"practice": practice},
        as_dict=True,
    )
    recent_patient_rows = [
        {
            "id": r.id,
            "name": r.name or "",
            "age": int(r.age) if r.age is not None else None,
            "sex": (r.sex or "")[:1],
            "last_seen": format_date(r.last_seen) if r.last_seen else "",
        }
        for r in recent_rows
    ]

    return _format_dashboard(
        user_first_name=user_doc.first_name or "",
        today_appointments=today_appointments,
        active_patient_count=active_patient_count,
        outstanding_lab_count=int(outstanding_lab_count),
        weekly_encounter_counts=weekly_counts,
        recent_patient_rows=recent_patient_rows,
        view_full_schedule_url=_full_schedule_url(practice, today_iso),
        today_label=_format_today_label(today_date),
    )


def _format_time(value) -> str:
    """Return HH:MM for a timedelta / time / str input from Patient Appointment."""
    if value is None:
        return ""
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
    if isinstance(value, str):
        return value[:5]
    return value.strftime("%H:%M")


def _format_today_label(d: date) -> str:
    return d.strftime("%A, %B %d")


def _full_schedule_url(practice: str, iso_date: str) -> str:
    qs = urlencode({"custom_practice": practice, "appointment_date": iso_date})
    return f"/app/patient-appointment?{qs}"

# Display order for the week-volume chart — Monday→Sunday matches the
# clinic week the design renders.
_WEEK_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Cap the dashboard's recent-patients table so the at-a-glance card never
# stretches past the design height.
_RECENT_PATIENTS_LIMIT = 6


def _format_dashboard(
    *,
    user_first_name: str,
    today_appointments: list,
    active_patient_count: int,
    outstanding_lab_count: int,
    weekly_encounter_counts: dict,
    recent_patient_rows: list,
    view_full_schedule_url: str,
    today_label: str,
) -> dict:
    greeting = f"Good morning, Dr. {user_first_name}" if user_first_name else "Good morning"
    week_volume = [
        {"day": d, "visits": int(weekly_encounter_counts.get(d, 0))}
        for d in _WEEK_DAYS
    ]
    breakdown: dict = {}
    for appt in today_appointments:
        status = appt.get("status") or "Unknown"
        breakdown[status] = breakdown.get(status, 0) + 1
    return {
        "greeting": greeting,
        "today_label": today_label,
        "kpis": {
            "today_appointments": {
                "value": len(today_appointments),
                "breakdown": breakdown,
            },
            "active_patients": {"value": int(active_patient_count)},
            "outstanding_labs": {"value": int(outstanding_lab_count)},
        },
        "today_schedule": list(today_appointments),
        "week_volume": week_volume,
        "recent_patients": list(recent_patient_rows)[:_RECENT_PATIENTS_LIMIT],
        "view_full_schedule_url": view_full_schedule_url,
    }
