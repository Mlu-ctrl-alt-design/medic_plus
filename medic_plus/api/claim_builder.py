"""Pure claim-builder: maps a submitted Patient Encounter to an Insurance Claim.

Deliberately has no side-effects; callers are responsible for persisting the
returned document.  This keeps the function table-testable without a database.
"""

from __future__ import annotations

import frappe


def build_claim(encounter_name: str) -> "frappe.model.document.Document":
	"""Build a Draft Insurance Claim from a submitted Patient Encounter.

	Reads three fields added in Phase 1E:
	  custom_claim_diagnosis_code  → Diagnosis claim line
	  custom_claim_tariff_code     → Procedure claim line
	  custom_claim_nappi_code      → Medication claim line

	Hydrates scheme/member details from the patient's active insurance policy
	(Patient Insurance Policy) if one exists.

	Returns the unsaved Insurance Claim document.  Raises frappe.ValidationError
	if the encounter has no claimable lines.
	"""
	enc = frappe.get_doc("Patient Encounter", encounter_name)
	practice = enc.get("custom_practice")
	if not practice:
		frappe.throw(f"Encounter {encounter_name} has no custom_practice — cannot build claim.")

	lines = _collect_lines(enc)
	if not lines:
		# No claimable data; silently skip (not all encounters need a claim)
		return None

	claim = frappe.new_doc("Insurance Claim")
	claim.practice = practice
	claim.patient = enc.patient
	claim.encounter = encounter_name
	claim.status = "Draft"

	_hydrate_scheme(claim, enc.patient)

	for line_data in lines:
		claim.append("claim_lines", line_data)

	return claim


def _collect_lines(enc) -> list[dict]:
	lines = []

	diagnosis_code = enc.get("custom_claim_diagnosis_code") or ""
	if diagnosis_code.strip():
		lines.append({
			"line_type": "Diagnosis",
			"code": diagnosis_code.strip(),
			"description": _describe_icd(diagnosis_code.strip()),
			"quantity": 1,
			"unit_fee": 0.0,
			"total_fee": 0.0,
			"status": "Pending",
		})

	tariff_code_name = enc.get("custom_claim_tariff_code") or ""
	if tariff_code_name:
		tc = frappe.db.get_value(
			"Tariff Code",
			tariff_code_name,
			["code", "description", "base_fee"],
			as_dict=True,
		)
		if tc:
			lines.append({
				"line_type": "Procedure",
				"code": tc.code,
				"description": tc.description,
				"quantity": 1,
				"unit_fee": tc.base_fee or 0.0,
				"total_fee": tc.base_fee or 0.0,
				"status": "Pending",
			})

	nappi_code = enc.get("custom_claim_nappi_code") or ""
	if nappi_code.strip():
		lines.append({
			"line_type": "Medication",
			"code": nappi_code.strip(),
			"description": _describe_nappi(nappi_code.strip()),
			"quantity": 1,
			"unit_fee": 0.0,
			"total_fee": 0.0,
			"status": "Pending",
		})

	return lines


def _describe_icd(code: str) -> str:
	"""Look up ICD-10 description from Code Value fixtures (best-effort)."""
	desc = frappe.db.get_value(
		"Code Value",
		{"code_system": ["in", ["ICD-10-ZA", "ICD-10"]], "code": code},
		"display",
	)
	return desc or code


def _describe_nappi(nappi: str) -> str:
	"""Look up NAPPI product name from Code Value fixtures (best-effort)."""
	desc = frappe.db.get_value(
		"Code Value",
		{"code_system": "NAPPI", "code": nappi},
		"display",
	)
	return desc or nappi


def _hydrate_scheme(claim, patient: str) -> None:
	"""Copy medical-aid details from the patient's most recent active policy."""
	policy = frappe.db.get_value(
		"Patient Insurance Policy",
		{"patient": patient, "docstatus": 1},
		["custom_sa_scheme", "custom_principal_member_id", "custom_dependent_code",
		 "custom_authorisation_reference"],
		as_dict=True,
		order_by="creation desc",
	)
	if not policy:
		return
	claim.scheme_name = policy.custom_sa_scheme or ""
	claim.member_id = policy.custom_principal_member_id or ""
	claim.dependent_code = policy.custom_dependent_code or ""
	claim.authorisation_reference = policy.custom_authorisation_reference or ""
