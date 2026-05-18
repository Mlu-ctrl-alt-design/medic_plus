"""Encounter Template — apply defaults, smart orders, EPI coupling, required-field enforcement.

Public surface:
  apply_template(doc)             — called from Patient Encounter before_insert
  validate_template_fields(doc)   — called from Patient Encounter before_submit
  check_hypertensive_urgency(doc) — sets doc.flags.hypertensive_urgency (non-blocking)
  get_template_for_type(encounter_type) — whitelisted; used by the frontend

Internal (testable):
  _get_epi_due_orders(patient, dob) — returns list of due/overdue EPI order dicts
"""

import json
import datetime

import frappe

ANTENATAL_TEMPLATE_NAME = "Antenatal Visit Template"
CHRONIC_TEMPLATE_NAME = "Chronic Disease Follow-up Template"
WELLCHILD_TEMPLATE_NAME = "Well-Child Visit Template"

_HT_URGENCY_SYSTOLIC = 180
_HT_URGENCY_DIASTOLIC = 110


def _get_template(appointment_type: str):
	if not appointment_type:
		return None
	practice = frappe.db.get_value(
		"Practice Member", {"user": frappe.session.user}, "practice"
	)
	if practice:
		name = frappe.db.get_value(
			"Encounter Template",
			{"appointment_type": appointment_type, "practice": practice},
			"name",
		)
		if name:
			return frappe.get_doc("Encounter Template", name)
	name = frappe.db.get_value(
		"Encounter Template",
		{"appointment_type": appointment_type, "is_platform_template": 1},
		"name",
	)
	return frappe.get_doc("Encounter Template", name) if name else None


def _load_json(raw, default):
	if not raw:
		return default
	return json.loads(raw) if isinstance(raw, str) else raw


def _get_patient_icd10_codes(patient: str) -> list[str]:
	if not patient:
		return []
	rows = frappe.get_all(
		"Patient Chronic Condition",
		filters={"patient": patient, "chronic_status": "Active"},
		fields=["icd10_code"],
		ignore_permissions=True,
	)
	return [r.icd10_code for r in rows if r.icd10_code]


def _patient_age_years(patient: str) -> float | None:
	"""Return patient's age in fractional years, or None if DOB unknown."""
	dob = frappe.db.get_value("Patient", patient, "dob")
	if not dob:
		return None
	dob_date = frappe.utils.getdate(dob)
	today = frappe.utils.getdate()
	delta = today - dob_date
	return delta.days / 365.25


def _get_epi_due_orders(patient: str, dob) -> list[dict]:
	"""Return Immunisation-type order dicts for EPI vaccines that are due or overdue.

	Attempts to call the Phase 2 Patient Immunisation Status API.
	Returns [] on any import error (graceful degradation).
	"""
	try:
		from medic_plus.api.immunisation import get_patient_immunisation_status  # Phase 2
		status = get_patient_immunisation_status(patient=patient)
		orders = []
		for entry in (status or []):
			if entry.get("status") in ("Due", "Overdue"):
				note = "OVERDUE" if entry.get("status") == "Overdue" else "DUE"
				orders.append({
					"order_type": "Immunisation",
					"order_name": entry.get("vaccine_name", ""),
					"notes": note,
				})
		return orders
	except Exception:
		# EPI module not yet deployed or raised unexpectedly — degrade gracefully
		return []


def _apply_age_guard(template, patient: str) -> bool:
	"""Return True if template should be applied for this patient.

	Returns False when age_guard_max_years > 0 and patient is older than that threshold.
	"""
	max_years = int(template.get("age_guard_max_years") or 0)
	if max_years <= 0:
		return True
	age = _patient_age_years(patient)
	if age is None:
		return True  # unknown age — allow template (conservative)
	return age <= max_years


def apply_template(doc) -> None:
	"""Apply template defaults, auto-orders, smart orders, and EPI coupling before insert."""
	template = _get_template(doc.get("appointment_type"))
	if not template:
		return

	# Age guard — skip template for patients over the configured threshold
	if not _apply_age_guard(template, doc.get("patient")):
		return

	# Field defaults
	defaults = _load_json(template.get("field_defaults"), {})
	for field, value in defaults.items():
		if not doc.get(field):
			doc.set(field, value)

	existing_orders = doc.get("custom_encounter_orders") or []
	if existing_orders:
		return

	# Baseline auto-orders
	for order in _load_json(template.get("auto_orders"), []):
		doc.append("custom_encounter_orders", {
			"order_type": order.get("order_type", "Lab"),
			"order_name": order.get("order_name", ""),
			"status": "Draft",
			"notes": order.get("notes", ""),
		})

	# Smart orders (ICD-10 condition-matched)
	smart_rules = _load_json(template.get("smart_orders"), [])
	if smart_rules:
		patient_codes = _get_patient_icd10_codes(doc.get("patient"))
		added_order_names = {o["order_name"] for o in _load_json(template.get("auto_orders"), [])}
		for rule in smart_rules:
			prefix = rule.get("icd10_prefix", "")
			order_name = rule.get("order_name", "")
			if not prefix or not order_name or order_name in added_order_names:
				continue
			if any(code.startswith(prefix) for code in patient_codes):
				doc.append("custom_encounter_orders", {
					"order_type": rule.get("order_type", "Lab"),
					"order_name": order_name,
					"status": "Draft",
					"notes": rule.get("notes", ""),
				})
				added_order_names.add(order_name)

	# EPI coupling — append due/overdue immunisation orders
	if template.get("epi_coupling_enabled"):
		dob = frappe.db.get_value("Patient", doc.get("patient"), "dob")
		epi_orders = _get_epi_due_orders(doc.get("patient"), dob)
		existing_names = {o.order_name for o in (doc.get("custom_encounter_orders") or [])}
		for order in epi_orders:
			if order["order_name"] and order["order_name"] not in existing_names:
				doc.append("custom_encounter_orders", {
					"order_type": order["order_type"],
					"order_name": order["order_name"],
					"status": "Draft",
					"notes": order.get("notes", ""),
				})
				existing_names.add(order["order_name"])


def check_hypertensive_urgency(doc) -> None:
	"""Set doc.flags.hypertensive_urgency when BP meets urgency thresholds (non-blocking)."""
	systolic = doc.get("custom_blood_pressure_systolic") or 0
	diastolic = doc.get("custom_blood_pressure_diastolic") or 0
	urgency = systolic >= _HT_URGENCY_SYSTOLIC or diastolic >= _HT_URGENCY_DIASTOLIC
	doc.flags.hypertensive_urgency = urgency
	if urgency:
		frappe.msgprint(
			frappe._(
				"Hypertensive urgency: BP {0}/{1} mmHg — consider same-day management."
			).format(systolic, diastolic),
			title=frappe._("Clinical Alert"),
			indicator="orange",
		)


def validate_template_fields(doc) -> None:
	"""Enforce required fields at before_submit; flag hypertensive urgency non-blocking."""
	template = _get_template(doc.get("appointment_type"))
	if not template:
		return

	if not _apply_age_guard(template, doc.get("patient")):
		return

	required = _load_json(template.get("required_fields"), [])
	meta = frappe.get_meta("Patient Encounter")
	missing = [meta.get_label(f) or f for f in required if not doc.get(f)]
	if missing:
		labels = ", ".join(f"<b>{m}</b>" for m in missing)
		frappe.throw(
			frappe._(
				"Required for {0} encounters before submission: {1}."
			).format(doc.get("appointment_type"), labels),
			frappe.ValidationError,
		)

	check_hypertensive_urgency(doc)


@frappe.whitelist()
def get_template_for_type(encounter_type: str):
	"""Return template config for *encounter_type*, or None if no template configured."""
	template = _get_template(encounter_type)
	if not template:
		return None
	return {
		"template_name": template.template_name,
		"field_defaults": _load_json(template.get("field_defaults"), {}),
		"required_fields": _load_json(template.get("required_fields"), []),
		"auto_orders": _load_json(template.get("auto_orders"), []),
		"smart_orders": _load_json(template.get("smart_orders"), []),
		"epi_coupling_enabled": bool(template.get("epi_coupling_enabled")),
		"age_guard_max_years": int(template.get("age_guard_max_years") or 0),
	}
