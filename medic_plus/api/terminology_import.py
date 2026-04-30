"""Phase 1B (#25) — Terminology stack importers.

Each `import_<system>(csv_path)` reads a 2-column CSV (code, display) and
upserts `Code Value` rows under the corresponding `Code System`. Idempotent:
re-running the same CSV updates the `display` of existing rows in place
and does not create duplicates.

Bench commands in `medic_plus/commands/__init__.py` are thin click wrappers.
"""

import csv

import frappe


def _ensure_code_system(name: str, uri: str) -> None:
	if frappe.db.exists("Code System", name):
		return
	frappe.get_doc({
		"doctype": "Code System",
		"code_system": name,
		"uri": uri,
		"is_fhir_defined": 1,
	}).insert(ignore_permissions=True)


def _upsert_code_value(*, system: str, code: str, display: str) -> str:
	"""Return 'created' or 'updated'.

	Matches Code Value's controller autoname (`{code_value}-{code_system}`)
	so the existence check finds rows previously created via the same path.
	"""
	row_name = f"{code}-{system}"
	if frappe.db.exists("Code Value", row_name):
		current = frappe.db.get_value("Code Value", row_name, "display")
		if current != display:
			frappe.db.set_value("Code Value", row_name, "display", display)
		return "updated"
	frappe.get_doc({
		"doctype": "Code Value",
		"code_system": system,
		"code_value": code,
		"display": display,
	}).insert(ignore_permissions=True)
	return "created"


def _import_csv(*, system: str, uri: str, csv_path: str) -> dict:
	_ensure_code_system(system, uri)
	created = 0
	updated = 0
	with open(csv_path, newline="") as fh:
		reader = csv.DictReader(fh)
		for row in reader:
			code = (row.get("code") or "").strip()
			display = (row.get("display") or "").strip()
			if not code:
				continue
			outcome = _upsert_code_value(system=system, code=code, display=display)
			if outcome == "created":
				created += 1
			else:
				updated += 1
	frappe.db.commit()
	return {"system": system, "created": created, "updated": updated}


def import_icd10(csv_path: str) -> dict:
	"""Idempotent ICD-10-ZA import. Returns {system, created, updated}."""
	return _import_csv(
		system="ICD-10-ZA",
		uri="http://hl7.org/fhir/sid/icd-10-za",
		csv_path=csv_path,
	)


def import_nappi(csv_path: str) -> dict:
	"""Idempotent NAPPI (SA pharmaceutical product code) import."""
	return _import_csv(
		system="NAPPI",
		uri="https://www.nappi.co.za",
		csv_path=csv_path,
	)


def import_loinc(csv_path: str) -> dict:
	"""Idempotent LOINC (lab observation code) import."""
	return _import_csv(
		system="LOINC",
		uri="http://loinc.org",
		csv_path=csv_path,
	)


def import_ucum(csv_path: str) -> dict:
	"""Idempotent UCUM (Unified Code for Units of Measure) import."""
	return _import_csv(
		system="UCUM",
		uri="http://unitsofmeasure.org",
		csv_path=csv_path,
	)


def import_atc(csv_path: str) -> dict:
	"""Idempotent ATC (Anatomical Therapeutic Chemical) import."""
	return _import_csv(
		system="ATC",
		uri="http://www.whocc.no/atc",
		csv_path=csv_path,
	)


def import_snomed_stub(csv_path: str) -> dict:
	"""Idempotent SNOMED-CT-ZA-stub import.

	Production import of the full SNOMED-CT-ZA catalogue is gated on
	IHTSDO Affiliate licence procurement — until that lands, this stub
	system holds a small placeholder seed for development.
	"""
	return _import_csv(
		system="SNOMED-CT-ZA-stub",
		uri="http://snomed.info/sct/za",
		csv_path=csv_path,
	)
