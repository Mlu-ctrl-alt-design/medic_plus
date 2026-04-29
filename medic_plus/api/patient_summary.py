"""Compose the Daystar Health patient detail composite payload.

The deep module orchestrates DB reads + payload shaping for the patient
detail screen. The screen has six tabs (Overview / Visits / Vitals /
Medications / Labs / Notes); the composite returns all six in one round
trip, with per-tab caps and POPIA whitelisting applied.

POPIA: the format helper explicitly whitelists the patient core fields it
returns. Fields like ``custom_sa_id_number`` never appear in the payload —
no unmask flow this iteration; the SA ID is simply unreachable from the SPA.
"""

from urllib.parse import urlencode

import frappe
from frappe.utils import format_date, format_datetime


def build_patient_summary(*, patient_name: str, practice: str) -> dict:
    """Compose the Daystar Health patient detail payload for a given Patient.

    Caller is responsible for the cross-tenant guard — by the time this is
    invoked, ``patient_name`` is known to belong to ``practice``. We don't
    re-check here so the deep module stays focused on shaping the payload.
    """
    patient_row = frappe.db.get_value(
        "Patient",
        patient_name,
        list(_PATIENT_PUBLIC_FIELDS),
        as_dict=True,
    ) or frappe._dict()

    visits = [
        {
            "id": r.name,
            "date": format_date(r.encounter_date) if r.encounter_date else "",
            "type": r.appointment_type or "",
            "practitioner": r.practitioner_name or r.practitioner or "",
            "department": r.medical_department or "",
            "comment": r.encounter_comment or "",
        }
        for r in frappe.db.get_all(
            "Patient Encounter",
            filters={"patient": patient_name},
            fields=["name", "encounter_date", "appointment_type",
                    "practitioner", "practitioner_name", "medical_department",
                    "encounter_comment"],
            order_by="encounter_date desc",
            limit_page_length=_VISITS_CAP,
        )
    ]

    vitals = [
        {
            "id": r.name,
            "date": format_date(r.signs_date) if r.signs_date else "",
            "bp_systolic": r.bp_systolic,
            "bp_diastolic": r.bp_diastolic,
            "weight": r.weight,
            "temperature": r.temperature,
            "respiratory_rate": r.respiratory_rate,
        }
        for r in frappe.db.get_all(
            "Vital Signs",
            filters={"patient": patient_name},
            fields=["name", "signs_date", "bp_systolic", "bp_diastolic",
                    "weight", "temperature", "respiratory_rate"],
            order_by="signs_date desc, signs_time desc",
            limit_page_length=_VITALS_CAP,
        )
    ]

    # Active medications: de-duplicate prescriptions by drug across recent
    # encounters. Most recent prescription wins.
    seen_drugs: set = set()
    medications: list = []
    rx_rows = frappe.db.sql(
        """
        SELECT dp.drug_code, dp.drug_name, dp.dosage, dp.period,
               dp.dosage_form, dp.interval, e.encounter_date AS started
        FROM `tabDrug Prescription` dp
        INNER JOIN `tabPatient Encounter` e ON e.name = dp.parent
        WHERE e.patient = %(patient)s
        ORDER BY e.encounter_date DESC, dp.idx ASC
        """,
        {"patient": patient_name},
        as_dict=True,
    )
    for r in rx_rows:
        key = r.get("drug_code") or r.get("drug_name") or ""
        if key in seen_drugs:
            continue
        seen_drugs.add(key)
        medications.append({
            "id": key,
            "name": r.get("drug_name") or r.get("drug_code") or "",
            "dosage": r.get("dosage") or "",
            "period": r.get("period") or "",
            "dosage_form": r.get("dosage_form") or "",
            "interval": r.get("interval") or "",
            "started": format_date(r.get("started")) if r.get("started") else "",
        })
        if len(medications) >= _MEDICATIONS_CAP:
            break

    labs = [
        {
            "id": r.name,
            "template": r.template or "",
            "status": r.status or "",
            "result_date": format_date(r.result_date) if r.result_date else "",
        }
        for r in frappe.db.get_all(
            "Lab Test",
            filters={"patient": patient_name},
            fields=["name", "template", "status", "result_date"],
            order_by="result_date desc",
            limit_page_length=_LABS_CAP,
        )
    ]

    notes = [
        {
            "id": r.name,
            "author": r.comment_email or r.owner or "",
            "when": format_datetime(r.creation) if r.creation else "",
            "body": r.content or "",
        }
        for r in frappe.db.get_all(
            "Comment",
            filters={
                "reference_doctype": "Patient",
                "reference_name": patient_name,
                "comment_type": "Comment",
            },
            fields=["name", "comment_email", "owner", "creation", "content"],
            order_by="creation desc",
            limit_page_length=_NOTES_CAP,
        )
    ]

    return _format_patient_summary(
        patient_row=patient_row,
        visits=visits,
        vitals=vitals,
        medications=medications,
        labs=labs,
        notes=notes,
        full_record_links=_full_record_links(patient_name, practice),
    )


def _full_record_links(patient: str, practice: str) -> dict:
    """Frappe Desk URLs for the 'see full record' links on each tab."""
    p = urlencode({"patient": patient})
    return {
        "visits": f"/app/patient-encounter?{p}",
        "vitals": f"/app/vital-signs?{p}",
        "medications": f"/app/patient-encounter?{p}",  # drug history per encounter
        "labs": f"/app/lab-test?{p}",
        "notes": f"/app/patient/{patient}",  # comment activity feed lives on the doc
    }


# Patient fields surfaced to the SPA. Anything outside this list is dropped,
# regardless of what the caller hands in. This is the POPIA whitelist.
_PATIENT_PUBLIC_FIELDS = (
    "name",
    "patient_name",
    "dob",
    "sex",
    "mobile",
    "email",
    "status",
)

# Per-tab row caps. Vitals is shorter because the trend chart in the SPA
# renders exactly 12 data points; the others are bounded for payload size.
_VISITS_CAP = 20
_VITALS_CAP = 12
_MEDICATIONS_CAP = 20
_LABS_CAP = 20
_NOTES_CAP = 20


def _format_patient_summary(
    *,
    patient_row: dict,
    visits: list,
    vitals: list,
    medications: list,
    labs: list,
    notes: list,
    full_record_links: dict | None = None,
) -> dict:
    patient = {k: patient_row.get(k) for k in _PATIENT_PUBLIC_FIELDS if k in patient_row}
    return {
        "patient": patient,
        "visits": list(visits)[:_VISITS_CAP],
        "vitals": list(vitals)[:_VITALS_CAP],
        "medications": list(medications)[:_MEDICATIONS_CAP],
        "labs": list(labs)[:_LABS_CAP],
        "notes": list(notes)[:_NOTES_CAP],
        "full_record_links": full_record_links or {},
    }
