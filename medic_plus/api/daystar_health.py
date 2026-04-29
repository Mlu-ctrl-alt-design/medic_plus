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
