import frappe
from frappe.utils import today, date_diff

from medic_plus.api.billing import require_feature


def _get_practice_filter() -> dict:
    """Return filter dict scoped to the current user's practice.

    Platform admins (Healthcare Administrator) see all practices — empty filter.
    Practice staff see only their own practice.
    Raises PermissionError if the user has no practice association.
    """
    from medic_plus.api.permissions import _is_platform_admin, _get_user_practice

    if _is_platform_admin():
        return {}
    practice = _get_user_practice()
    if not practice:
        frappe.throw("You are not associated with any practice.", frappe.PermissionError)
    return {"custom_practice": practice}


@frappe.whitelist()
@require_feature("inpatient_module")
def get_inpatient_summary() -> dict:
    """Return headline stats for the inpatient dashboard."""
    base = _get_practice_filter()

    current_inpatients = frappe.db.count(
        "Inpatient Record",
        {**base, "status": ["in", ["Admission Scheduled", "Admitted"]]},
    )

    todays_admissions = frappe.db.count(
        "Inpatient Record",
        {**base, "admitted_datetime": ["like", f"{today()}%"]},
    )

    expected_discharges = frappe.db.count(
        "Inpatient Record",
        {
            **base,
            "expected_discharge": today(),
            "status": ["in", ["Admission Scheduled", "Admitted"]],
        },
    )

    avg_los = _compute_avg_los(base)

    return {
        "current_inpatients": current_inpatients,
        "todays_admissions": todays_admissions,
        "expected_discharges": expected_discharges,
        "avg_los_days": avg_los,
    }


@frappe.whitelist()
@require_feature("inpatient_module")
def get_current_inpatients() -> list:
    """Return currently admitted patients with LOS and current ward info."""
    base = _get_practice_filter()

    records = frappe.db.get_all(
        "Inpatient Record",
        filters={**base, "status": ["in", ["Admission Scheduled", "Admitted"]]},
        fields=[
            "name",
            "patient",
            "patient_name",
            "gender",
            "status",
            "admitted_datetime",
            "expected_discharge",
            "primary_practitioner",
            "medical_department",
            "custom_practice",
        ],
        order_by="admitted_datetime asc",
        limit=200,
    )

    for r in records:
        # Length of stay in days
        if r.admitted_datetime:
            r["los_days"] = date_diff(today(), r.admitted_datetime.date())
        else:
            r["los_days"] = 0

        # Current active ward from the occupancy child table (left = 0 → still checked in)
        occ = frappe.db.get_value(
            "Inpatient Occupancy",
            {"parent": r.name, "left": 0},
            ["service_unit", "check_in"],
            as_dict=True,
        )
        r["current_ward"] = occ.service_unit if occ else None
        r["check_in"] = str(occ.check_in) if (occ and occ.check_in) else None

    return records


def _compute_avg_los(base_filter: dict) -> float:
    """Average LOS (days) for currently Admitted patients."""
    admitted = frappe.db.get_all(
        "Inpatient Record",
        filters={**base_filter, "status": "Admitted", "admitted_datetime": ["is", "set"]},
        fields=["admitted_datetime"],
    )

    if not admitted:
        return 0

    los_values = [
        date_diff(today(), r.admitted_datetime.date())
        for r in admitted
        if r.admitted_datetime
    ]

    return round(sum(los_values) / len(los_values), 1) if los_values else 0
