"""FHIR R4/R5 resource mappers.

Each mapper takes a Frappe doc (or dict) and returns a plain dict
that validates against fhir.resources models.

Canonical code-system URIs follow the Code System fixture URIs.
"""

from __future__ import annotations

import frappe

# Canonical URIs for SA-localised code systems
_CS_ICD10_ZA = "http://hl7.org/fhir/sid/icd-10-za"
_CS_NAPPI = "https://www.nappi.co.za"
_CS_LOINC = "http://loinc.org"
_CS_SNOMED = "http://snomed.info/sct"
_CS_TARIFF = "https://www.bhf.co.za/sama-tariff"

def _fhir_base_url() -> str:
	return f"{frappe.utils.get_url()}/api/fhir/R4"


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

def patient_to_fhir(patient_name: str) -> dict:
	p = frappe.get_doc("Patient", patient_name)
	resource = {
		"resourceType": "Patient",
		"id": p.name,
		"meta": _meta(p),
		"identifier": [
			{
				"use": "official",
				"system": f"{_fhir_base_url()}/naming-system/medic-plus-patient",
				"value": p.name,
			}
		],
		"name": [
			{
				"use": "official",
				"text": p.patient_name or "",
				"family": (p.last_name or "").strip() or _split_name(p.patient_name)[1],
				"given": [_split_name(p.patient_name)[0]],
			}
		],
		"gender": _gender(getattr(p, "sex", None)),
		"birthDate": str(p.dob) if p.dob else None,
		"active": True,
	}
	# SA ID as additional identifier
	sa_id = p.get("custom_sa_id_number") or ""
	if sa_id:
		resource["identifier"].append({
			"use": "official",
			"system": "https://www.dha.gov.za/sa-id",
			"value": sa_id,
		})
	_strip_none(resource)
	return resource


# ---------------------------------------------------------------------------
# Encounter
# ---------------------------------------------------------------------------

def encounter_to_fhir(encounter_name: str) -> dict:
	enc = frappe.get_doc("Patient Encounter", encounter_name)
	resource = {
		"resourceType": "Encounter",
		"id": enc.name,
		"meta": _meta(enc),
		"status": _encounter_status(enc),
		"subject": {"reference": f"Patient/{enc.patient}"},
	}

	# Practitioner participant
	if enc.get("practitioner"):
		resource["participant"] = [
			{
				"actor": {"reference": f"Practitioner/{enc.practitioner}"},
			}
		]

	# Encounter date → actualPeriod
	if enc.encounter_date:
		resource["actualPeriod"] = {"start": str(enc.encounter_date)}

	# Diagnosis from custom_claim_diagnosis_code
	diag_code = enc.get("custom_claim_diagnosis_code") or ""
	if diag_code:
		resource["diagnosis"] = [
			{
				"condition": [
					{
						"concept": {
							"coding": [
								{
									"system": _CS_ICD10_ZA,
									"code": diag_code,
									"display": _icd_display(diag_code),
								}
							],
							"text": _icd_display(diag_code),
						}
					}
				]
			}
		]

	# Tariff code → type
	tariff = enc.get("custom_claim_tariff_code") or ""
	if tariff:
		resource["type"] = [
			{
				"coding": [
					{
						"system": _CS_TARIFF,
						"code": tariff,
						"display": _tariff_display(tariff),
					}
				],
				"text": _tariff_display(tariff),
			}
		]

	_strip_none(resource)
	return resource


# ---------------------------------------------------------------------------
# Condition  (from custom_claim_diagnosis_code on encounter)
# ---------------------------------------------------------------------------

def condition_to_fhir(encounter_name: str) -> dict | None:
	enc = frappe.get_doc("Patient Encounter", encounter_name)
	diag_code = enc.get("custom_claim_diagnosis_code") or ""
	if not diag_code:
		return None

	return {
		"resourceType": "Condition",
		"id": f"{enc.name}-cond-{diag_code.replace('.', '_')}",
		"meta": _meta(enc),
		"subject": {"reference": f"Patient/{enc.patient}"},
		"encounter": {"reference": f"Encounter/{enc.name}"},
		"code": {
			"coding": [
				{
					"system": _CS_ICD10_ZA,
					"code": diag_code,
					"display": _icd_display(diag_code),
				}
			],
			"text": _icd_display(diag_code),
		},
		"clinicalStatus": {
			"coding": [
				{
					"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
					"code": "active",
				}
			]
		},
		"verificationStatus": {
			"coding": [
				{
					"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
					"code": "confirmed",
				}
			]
		},
	}


# ---------------------------------------------------------------------------
# MedicationRequest  (from custom_claim_nappi_code on encounter)
# ---------------------------------------------------------------------------

def medication_request_to_fhir(encounter_name: str) -> dict | None:
	enc = frappe.get_doc("Patient Encounter", encounter_name)
	nappi = enc.get("custom_claim_nappi_code") or ""
	if not nappi:
		return None

	display = _nappi_display(nappi)
	return {
		"resourceType": "MedicationRequest",
		"id": f"{enc.name}-med-{nappi}",
		"meta": _meta(enc),
		"status": "active",
		"intent": "order",
		"subject": {"reference": f"Patient/{enc.patient}"},
		"encounter": {"reference": f"Encounter/{enc.name}"},
		"medication": {
			"concept": {
				"coding": [
					{
						"system": _CS_NAPPI,
						"code": nappi,
						"display": display,
					}
				],
				"text": display,
			}
		},
	}


# ---------------------------------------------------------------------------
# AllergyIntolerance  (from Patient Allergy doctype)
# ---------------------------------------------------------------------------

def allergy_to_fhir(allergy_name: str) -> dict:
	a = frappe.get_doc("Patient Allergy", allergy_name)
	criticality = _allergy_criticality(a.get("severity") or "")
	return {
		"resourceType": "AllergyIntolerance",
		"id": a.name,
		"meta": _meta(a),
		"patient": {"reference": f"Patient/{a.patient}"},
		"code": {
			"coding": [
				{
					"system": _CS_SNOMED,
					"code": a.get("reaction_code") or "",
					"display": a.get("substance") or a.get("allergen") or "",
				}
			],
			"text": a.get("substance") or a.get("allergen") or "",
		},
		"clinicalStatus": {
			"coding": [
				{
					"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
					"code": "active",
				}
			]
		},
		"criticality": criticality,
		"type": "allergy",
	}


# ---------------------------------------------------------------------------
# Observation (vitals — from encounter fields)
# ---------------------------------------------------------------------------

def vitals_to_fhir(encounter_name: str) -> list[dict]:
	"""Return a list of Observation resources for any vitals on the encounter."""
	enc = frappe.get_doc("Patient Encounter", encounter_name)
	observations = []

	systolic = enc.get("custom_blood_pressure_systolic")
	diastolic = enc.get("custom_blood_pressure_diastolic")
	if systolic and diastolic:
		observations.append(_bp_observation(enc, systolic, diastolic))

	weight = enc.get("custom_weight_kg")
	if weight:
		observations.append(_simple_observation(
			enc, "29463-7", "Body weight", float(weight), "kg",
			"http://unitsofmeasure.org", "kg",
		))

	height = enc.get("custom_length_height")
	if height:
		observations.append(_simple_observation(
			enc, "8302-2", "Body height", float(height), "cm",
			"http://unitsofmeasure.org", "cm",
		))

	return observations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _meta(doc) -> dict:
	return {
		"versionId": str(doc.modified or "").replace(" ", "T"),
		"lastUpdated": str(doc.modified or "").replace(" ", "T") + "Z" if doc.modified else None,
	}


def _gender(sex: str | None) -> str:
	mapping = {"Male": "male", "Female": "female", "Other": "other"}
	return mapping.get(sex or "", "unknown")


def _encounter_status(enc) -> str:
	docstatus = getattr(enc, "docstatus", 0)
	if docstatus == 1:
		return "discharged"
	if docstatus == 2:
		return "cancelled"
	return "in-progress"


def _icd_display(code: str) -> str:
	return frappe.db.get_value(
		"Code Value",
		{"code_system": ["in", ["ICD-10-ZA", "ICD-10"]], "code": code},
		"display",
	) or code


def _nappi_display(code: str) -> str:
	return frappe.db.get_value(
		"Code Value",
		{"code_system": "NAPPI", "code": code},
		"display",
	) or code


def _tariff_display(code: str) -> str:
	return frappe.db.get_value("Tariff Code", code, "description") or code


def _allergy_criticality(severity: str) -> str:
	mapping = {"Severe": "high", "Moderate": "low", "Mild": "low", "Life-threatening": "high"}
	return mapping.get(severity, "unable-to-assess")


def _split_name(full_name: str | None) -> tuple[str, str]:
	parts = (full_name or "").strip().split(" ", 1)
	if len(parts) == 2:
		return parts[0], parts[1]
	return parts[0] if parts else "", ""


def _bp_observation(enc, systolic, diastolic) -> dict:
	return {
		"resourceType": "Observation",
		"id": f"{enc.name}-bp",
		"meta": _meta(enc),
		"status": "final",
		"code": {
			"coding": [
				{"system": _CS_LOINC, "code": "55284-4", "display": "Blood pressure"}
			]
		},
		"subject": {"reference": f"Patient/{enc.patient}"},
		"encounter": {"reference": f"Encounter/{enc.name}"},
		"component": [
			{
				"code": {"coding": [{"system": _CS_LOINC, "code": "8480-6", "display": "Systolic BP"}]},
				"valueQuantity": {"value": float(systolic), "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"},
			},
			{
				"code": {"coding": [{"system": _CS_LOINC, "code": "8462-4", "display": "Diastolic BP"}]},
				"valueQuantity": {"value": float(diastolic), "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"},
			},
		],
	}


def _simple_observation(enc, loinc_code: str, display: str, value: float, unit: str,
                         ucum_system: str, ucum_code: str) -> dict:
	return {
		"resourceType": "Observation",
		"id": f"{enc.name}-{loinc_code}",
		"meta": _meta(enc),
		"status": "final",
		"code": {
			"coding": [{"system": _CS_LOINC, "code": loinc_code, "display": display}]
		},
		"subject": {"reference": f"Patient/{enc.patient}"},
		"encounter": {"reference": f"Encounter/{enc.name}"},
		"valueQuantity": {
			"value": value,
			"unit": unit,
			"system": ucum_system,
			"code": ucum_code,
		},
	}


def _strip_none(d: dict) -> None:
	"""Remove keys whose values are None (in-place, one level deep)."""
	for key in list(d.keys()):
		if d[key] is None:
			del d[key]
