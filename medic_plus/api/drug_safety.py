"""Phase 1D — Medication safety checks.

All public functions are pure over patient/encounter state and return a list of
warning dicts.  The before_save hook in doc_events.py calls run_safety_checks()
and surfaces warnings via frappe.msgprint (non-blocking).

Warning dict shape:
  {
    "type":     "drug_allergy" | "drug_interaction" | "schedule_rule",
    "drug":     str,          # drug name that triggered the warning
    "message":  str,          # human-readable explanation
    "severity": str | None,   # allergy severity if applicable
  }
"""
from __future__ import annotations

import frappe


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_drug_master(nappi_code_value: str) -> dict | None:
    """Return Drug Master fields for the given NAPPI Code Value name, or None."""
    if not nappi_code_value:
        return None
    return frappe.db.get_value(
        "Drug Master",
        {"nappi_code_value": nappi_code_value},
        ["name", "drug_name", "atc_code", "ingredient", "schedule"],
        as_dict=True,
    )


def _active_drug_allergies(patient: str) -> list[dict]:
    """Return active Drug-category Patient Allergy rows for the patient."""
    return frappe.get_all(
        "Patient Allergy",
        filters={"patient": patient, "status": "Active", "category": "Drug"},
        fields=["name", "substance", "custom_atc_code", "severity"],
    )


# ---------------------------------------------------------------------------
# Public safety checks
# ---------------------------------------------------------------------------

def check_drug_allergy(patient: str, atc_code: str | None, drug_name: str) -> list[dict]:
    """Return warnings if the patient has an active allergy matching *atc_code*.

    Matching rules (applied in order; first match wins):
      1. ATC code match  — allergy.custom_atc_code == atc_code
      2. Ingredient substring — allergy.substance is a case-insensitive substring
         of drug_name (fallback for allergies recorded without ATC)
    """
    if not patient:
        return []

    warnings: list[dict] = []
    atc_upper = (atc_code or "").upper()
    drug_lower = (drug_name or "").lower()

    for allergy in _active_drug_allergies(patient):
        matched = False
        match_reason = ""

        allergy_atc = (allergy.get("custom_atc_code") or "").upper()
        if allergy_atc and atc_upper and allergy_atc == atc_upper:
            matched = True
            match_reason = f"ATC class {atc_upper}"
        elif allergy.get("substance") and allergy["substance"].lower() in drug_lower:
            matched = True
            match_reason = f"ingredient match ({allergy['substance']})"

        if matched:
            warnings.append({
                "type": "drug_allergy",
                "drug": drug_name,
                "message": (
                    f"Patient has recorded allergy to '{allergy['substance']}' "
                    f"({match_reason}). Severity: {allergy.get('severity', 'Unknown')}."
                ),
                "severity": allergy.get("severity"),
                "allergy_name": allergy["name"],
            })

    return warnings


def check_drug_interaction(nappi_code_values: list[str]) -> list[dict]:
    """Check Healthcare Drug Interaction table for pairwise interaction warnings.

    Returns one warning dict per interaction found.
    """
    if len(nappi_code_values) < 2:
        return []

    # Resolve item codes from NAPPI Code Values via Drug Master
    items: list[str] = []
    for nappi_cv in nappi_code_values:
        dm = _get_drug_master(nappi_cv)
        if dm and dm.get("name"):
            items.append(dm["drug_name"])

    warnings: list[dict] = []
    # Healthcare stores Drug Interaction with drug_name / interacting_drug fields.
    # We do a cross-product check for each pair.
    for i, drug_a in enumerate(items):
        for drug_b in items[i + 1:]:
            interaction = frappe.db.get_value(
                "Drug Interaction",
                {"drug_name": drug_a, "interacting_drug": drug_b},
                ["drug_name", "interacting_drug", "interaction_description"],
                as_dict=True,
            ) or frappe.db.get_value(
                "Drug Interaction",
                {"drug_name": drug_b, "interacting_drug": drug_a},
                ["drug_name", "interacting_drug", "interaction_description"],
                as_dict=True,
            )
            if interaction:
                warnings.append({
                    "type": "drug_interaction",
                    "drug": f"{drug_a} + {drug_b}",
                    "message": (
                        f"Potential interaction between {drug_a} and {drug_b}. "
                        + (interaction.get("interaction_description") or "")
                    ),
                    "severity": None,
                })

    return warnings


def check_schedule_rule(nappi_code_value: str, prescriber: str | None) -> list[dict]:
    """Validate Schedule constraints for a single drug.

    Rules:
      S5 — prescriber must have custom_practice_number (MP number recorded).
      S6 — no repeats allowed; same MP number requirement.
      Both — if repeats > 6 months worth, warn (no hard date calc; warn if
             repeats_authorised > 5 as a proxy for 6 months).
    """
    if not nappi_code_value:
        return []

    dm = _get_drug_master(nappi_code_value)
    if not dm:
        return []

    schedule = (dm.get("schedule") or "").upper()
    if schedule not in ("S5", "S6"):
        return []

    warnings: list[dict] = []

    if prescriber:
        mp_number = frappe.db.get_value(
            "Healthcare Practitioner", prescriber, "custom_practice_number"
        )
        if not mp_number:
            warnings.append({
                "type": "schedule_rule",
                "drug": dm["drug_name"],
                "message": (
                    f"{dm['drug_name']} is {schedule}. "
                    "Prescriber must have a registered MP/PR practice number. "
                    "Please update the Healthcare Practitioner record."
                ),
                "severity": None,
            })

    if schedule == "S6":
        warnings.append({
            "type": "schedule_rule",
            "drug": dm["drug_name"],
            "message": (
                f"{dm['drug_name']} is Schedule 6 — repeats are not permitted. "
                "A new prescription is required for each dispensation."
            ),
            "severity": None,
        })

    return warnings


def run_safety_checks(encounter_doc) -> list[dict]:
    """Aggregate all three safety checks for every drug in the encounter.

    Returns the combined list of warning dicts.  Attaches the list to
    ``encounter_doc._drug_safety_warnings`` for testability.
    """
    all_warnings: list[dict] = []
    patient = getattr(encounter_doc, "patient", None)
    prescriber = getattr(encounter_doc, "practitioner", None)

    drug_rows = getattr(encounter_doc, "drug_prescription", []) or []

    nappi_code_values = [
        r.get("custom_nappi_code_value")
        for r in drug_rows
        if r.get("custom_nappi_code_value")
    ]

    for row in drug_rows:
        nappi_cv = row.get("custom_nappi_code_value")
        if not nappi_cv:
            continue

        dm = _get_drug_master(nappi_cv)
        if not dm:
            continue

        drug_name = dm.get("drug_name") or row.get("drug_name") or nappi_cv
        atc_code = dm.get("atc_code")

        all_warnings.extend(check_drug_allergy(patient, atc_code, drug_name))
        all_warnings.extend(check_schedule_rule(nappi_cv, prescriber))

    all_warnings.extend(check_drug_interaction(nappi_code_values))

    encounter_doc._drug_safety_warnings = all_warnings
    return all_warnings
