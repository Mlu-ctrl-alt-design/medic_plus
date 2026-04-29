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
