"""Whitelisted endpoints for the Daystar Health SPA at /daystar-health.

Each endpoint is a thin orchestrator:
  - resolve the active Practice via practice_resolver (raises PermissionError
    when the caller has no Practice Member row);
  - run the doctype-scoped queries;
  - hand them to the appropriate aggregator for shaping;
  - return a JSON-serialisable payload.

Heavy logic lives in the deep modules (dashboard_aggregator,
patient_summary, …) so it can be tested in isolation.
"""

import json
from datetime import date, timedelta

import frappe

from medic_plus.api.dashboard_aggregator import build_dashboard
from medic_plus.api.patient_summary import build_patient_summary
from medic_plus.api.practice_resolver import get_active_practice


@frappe.whitelist()
def get_dashboard() -> dict:
    """Return the dashboard payload for the logged-in user's active Practice."""
    practice = get_active_practice()
    return build_dashboard(practice=practice, user=frappe.session.user)


_USER_PROFILE_FIELDS = (
    "name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "user_image",
)

_PRACTITIONER_PROFILE_FIELDS = (
    "name",
    "department",
    "custom_hpcsa_number",
    "custom_practice_number",
)


@frappe.whitelist()
def get_my_practitioner_profile() -> dict:
    """Return the read-only profile for the logged-in practitioner.

    Joins ``User`` core fields with the ``Healthcare Practitioner`` linked
    via the user's ``Practice Member`` row. Raises ``PermissionError`` for
    callers without a Practice — the SPA surfaces that as the no-practice
    error card, same as every other endpoint.
    """
    practice = get_active_practice()
    user_email = frappe.session.user
    user_row = frappe.db.get_value(
        "User", user_email, list(_USER_PROFILE_FIELDS), as_dict=True
    ) or {}
    practitioner_name = frappe.db.get_value(
        "Practice Member",
        {"user": user_email, "practice": practice},
        "practitioner",
    )
    practitioner_row = {}
    if practitioner_name:
        practitioner_row = frappe.db.get_value(
            "Healthcare Practitioner",
            practitioner_name,
            list(_PRACTITIONER_PROFILE_FIELDS),
            as_dict=True,
        ) or {}
    # 2FA per-user state is inferred from frappe.utils.user.user_has_2fa
    # (the User doctype has no direct boolean for it). Returned as a flat
    # field so the SPA can render an enabled/disabled badge without another
    # round trip.
    try:
        from frappe.utils.user import user_has_2fa
        twofa_enabled = bool(user_has_2fa(user_email))
    except Exception:
        twofa_enabled = False

    return {
        "user": dict(user_row),
        "practitioner": dict(practitioner_row),
        "practice": practice,
        "two_factor_authentication": twofa_enabled,
    }


_APPOINTMENT_FIELDS = (
    "name",
    "appointment_date",
    "appointment_time",
    "patient",
    "patient_name",
    "practitioner",
    "practitioner_name",
    "appointment_type",
    "status",
)

_DEFAULT_STATUSES = ["Scheduled", "Open"]


def _format_appointments(rows: list) -> list:
    """Shape raw Patient Appointment dicts into SPA-ready dicts.

    Pure transformation — no DB calls, no session access. Tested in isolation.
    """
    return [
        {
            "name": r.get("name"),
            "appointment_date": str(r.get("appointment_date") or ""),
            "appointment_time": str(r.get("appointment_time") or ""),
            "patient": r.get("patient"),
            "patient_name": r.get("patient_name"),
            "practitioner": r.get("practitioner"),
            "practitioner_name": r.get("practitioner_name"),
            "appointment_type": r.get("appointment_type"),
            "status": r.get("status"),
        }
        for r in rows
    ]


@frappe.whitelist()
def get_appointments(filters=None) -> list:
    """Return Patient Appointments for the logged-in user's active Practice.

    Default window: today → +7 days. Default statuses: Scheduled and Open.
    Accepts an optional ``filters`` dict (or JSON string) with keys:
      ``date_from``, ``date_to``, ``status`` (str or list), ``practitioner``.
    Returns at most 200 rows ordered by appointment_date / appointment_time asc.
    """
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}
    filters = filters or {}

    practice = get_active_practice()
    today = date.today()
    date_from = filters.get("date_from") or str(today)
    date_to = filters.get("date_to") or str(today + timedelta(days=7))

    status_filter = filters.get("status") or _DEFAULT_STATUSES
    if isinstance(status_filter, str):
        status_filter = [status_filter]

    doctype_filters = {
        "custom_practice": practice,
        "appointment_date": ["between", [date_from, date_to]],
        "status": ["in", status_filter],
    }
    practitioner = filters.get("practitioner")
    if practitioner:
        doctype_filters["practitioner"] = practitioner

    rows = frappe.get_all(
        "Patient Appointment",
        filters=doctype_filters,
        fields=list(_APPOINTMENT_FIELDS),
        order_by="appointment_date asc, appointment_time asc",
        limit=200,
    )
    return _format_appointments(rows)


_MEDICAL_RECORD_FIELDS = (
    "name",
    "patient",
    "communication_date",
    "reference_doctype",
    "reference_name",
    "subject",
    "user",
    "attach",
)
_MEDICAL_RECORD_PAGE_DEFAULT = 50
_MEDICAL_RECORD_PAGE_MAX = 200
_MEDICAL_RECORD_SUBJECT_MAX = 240


def _format_medical_records(rows: list, patient_name_by_id: dict) -> list:
    """Shape raw Patient Medical Record dicts into SPA-ready rows.

    Truncates ``subject`` to keep the table compact and surfaces a boolean
    ``has_attach`` rather than the raw file URL (private files cannot be
    rendered cross-user; the source doc carries the canonical attachment).
    """
    out = []
    for r in rows:
        subject = (r.get("subject") or "").strip()
        if len(subject) > _MEDICAL_RECORD_SUBJECT_MAX:
            subject = subject[: _MEDICAL_RECORD_SUBJECT_MAX - 1] + "…"
        out.append({
            "name": r.get("name"),
            "patient": r.get("patient"),
            "patient_name": patient_name_by_id.get(r.get("patient")),
            "communication_date": str(r.get("communication_date") or ""),
            "reference_doctype": r.get("reference_doctype"),
            "reference_name": r.get("reference_name"),
            "subject": subject,
            "user": r.get("user"),
            "has_attach": bool(r.get("attach")),
        })
    return out


@frappe.whitelist()
def get_medical_records(filters=None, limit_start=0, limit_page_length=None) -> dict:
    """Return Patient Medical Record rows for the active Practice.

    Returns a dict shaped ``{rows, total, limit_start, limit_page_length}`` so
    the SPA can render pagination. Patient Medical Record has no
    ``custom_practice`` field — scope is enforced by joining on Patient. The
    PQC ``get_patient_medical_record_permission_query`` is the defence
    in depth; this query restates the same constraint at the API level.

    Filters dict (or JSON string) keys:
      ``patient`` (single Patient name)
      ``reference_doctype`` (str or list — Patient Encounter / Lab Test / …)
      ``date_from`` / ``date_to`` (YYYY-MM-DD; default last 30 days)
    """
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}
    filters = filters or {}

    try:
        limit_start = int(limit_start or 0)
    except (TypeError, ValueError):
        limit_start = 0
    try:
        limit_page_length = int(limit_page_length or _MEDICAL_RECORD_PAGE_DEFAULT)
    except (TypeError, ValueError):
        limit_page_length = _MEDICAL_RECORD_PAGE_DEFAULT
    limit_page_length = max(1, min(limit_page_length, _MEDICAL_RECORD_PAGE_MAX))

    practice = get_active_practice()
    today = date.today()
    date_from = filters.get("date_from") or str(today - timedelta(days=30))
    date_to = filters.get("date_to") or str(today)

    practice_patients = frappe.get_all(
        "Patient",
        filters={"custom_practice": practice},
        pluck="name",
        limit=0,
    )
    if not practice_patients:
        return {"rows": [], "total": 0, "limit_start": limit_start, "limit_page_length": limit_page_length}

    pmr_filters = {
        "patient": ["in", practice_patients],
        "communication_date": ["between", [date_from, date_to]],
    }
    requested_patient = filters.get("patient")
    if requested_patient:
        if requested_patient not in practice_patients:
            # Caller asked for a Patient outside the active practice — no rows.
            return {"rows": [], "total": 0, "limit_start": limit_start, "limit_page_length": limit_page_length}
        pmr_filters["patient"] = requested_patient

    ref_doctype = filters.get("reference_doctype")
    if ref_doctype:
        if isinstance(ref_doctype, str):
            ref_doctype = [ref_doctype]
        pmr_filters["reference_doctype"] = ["in", ref_doctype]

    total = frappe.db.count("Patient Medical Record", filters=pmr_filters)
    rows = frappe.get_all(
        "Patient Medical Record",
        filters=pmr_filters,
        fields=list(_MEDICAL_RECORD_FIELDS),
        order_by="communication_date desc, creation desc",
        limit_start=limit_start,
        limit_page_length=limit_page_length,
    )
    patient_ids = list({r["patient"] for r in rows if r.get("patient")})
    patient_name_by_id = {}
    if patient_ids:
        for p in frappe.get_all(
            "Patient",
            filters={"name": ["in", patient_ids]},
            fields=["name", "patient_name"],
        ):
            patient_name_by_id[p["name"]] = p.get("patient_name")

    return {
        "rows": _format_medical_records(rows, patient_name_by_id),
        "total": total,
        "limit_start": limit_start,
        "limit_page_length": limit_page_length,
    }


@frappe.whitelist()
def get_patient_detail(patient: str) -> dict:
    """Return the composite payload for a Patient detail screen.

    Cross-tenant guard: the requested Patient must belong to the caller's
    active Practice. Cross-Practice requests raise PermissionError so the
    response cannot be used to probe Practice membership of arbitrary IDs.
    """
    practice = get_active_practice()
    patient_practice = frappe.db.get_value("Patient", patient, "custom_practice")
    if patient_practice != practice:
        raise frappe.PermissionError("Patient does not belong to your practice.")
    return build_patient_summary(patient_name=patient, practice=practice)
