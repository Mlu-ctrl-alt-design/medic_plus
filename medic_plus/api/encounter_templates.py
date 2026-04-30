"""Encounter Template — apply defaults, smart orders, and required-field enforcement.

Public surface:
  apply_template(doc)            — called from Patient Encounter before_insert
  validate_template_fields(doc)  — called from Patient Encounter before_submit
  check_hypertensive_urgency(doc) — sets doc.flags.hypertensive_urgency (non-blocking)
  get_template_for_type(encounter_type) — whitelisted; used by the frontend
"""

import json

import frappe

ANTENATAL_TEMPLATE_NAME = "Antenatal Visit Template"
CHRONIC_TEMPLATE_NAME = "Chronic Disease Follow-up Template"
WELLCHILD_TEMPLATE_NAME = "Well-Child Visit Template"

# Hypertensive urgency thresholds (non-blocking warning)
_HT_URGENCY_SYSTOLIC = 180
_HT_URGENCY_DIASTOLIC = 110


def _get_template(appointment_type: str):
	"""Return the best Encounter Template for *appointment_type*, or None.

	Practice-scoped templates take priority over platform templates.
	"""
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
	"""Return ICD-10 codes for all active Patient Chronic Conditions for *patient*."""
	if not patient:
		return []
	rows = frappe.get_all(
		"Patient Chronic Condition",
		filters={"patient": patient, "chronic_status": "Active"},
		fields=["icd10_code"],
		ignore_permissions=True,
	)
	return [r.icd10_code for r in rows if r.icd10_code]


def apply_template(doc) -> None:
	"""Apply an Encounter Template's defaults to *doc* before insert.

	1. Sets field defaults from template.field_defaults.
	2. Appends baseline auto_orders (skips if orders already present).
	3. Appends smart_orders matched against the patient's active ICD-10 codes.
	"""
	template = _get_template(doc.get("appointment_type"))
	if not template:
		return

	# 1. Field defaults
	defaults = _load_json(template.get("field_defaults"), {})
	for field, value in defaults.items():
		if not doc.get(field):
			doc.set(field, value)

	# Only populate orders on new encounters (empty child table)
	existing_orders = doc.get("custom_encounter_orders") or []
	if existing_orders:
		return

	# 2. Baseline auto-orders
	for order in _load_json(template.get("auto_orders"), []):
		doc.append("custom_encounter_orders", {
			"order_type": order.get("order_type", "Lab"),
			"order_name": order.get("order_name", ""),
			"status": "Draft",
			"notes": order.get("notes", ""),
		})

	# 3. Smart orders matched against patient's active ICD-10 codes
	smart_rules = _load_json(template.get("smart_orders"), [])
	if not smart_rules:
		return

	patient_codes = _get_patient_icd10_codes(doc.get("patient"))
	added_order_names = {o["order_name"] for o in _load_json(template.get("auto_orders"), [])}

	for rule in smart_rules:
		prefix = rule.get("icd10_prefix", "")
		order_name = rule.get("order_name", "")
		if not prefix or not order_name:
			continue
		if order_name in added_order_names:
			continue
		if any(code.startswith(prefix) for code in patient_codes):
			doc.append("custom_encounter_orders", {
				"order_type": rule.get("order_type", "Lab"),
				"order_name": order_name,
				"status": "Draft",
				"notes": rule.get("notes", ""),
			})
			added_order_names.add(order_name)


def check_hypertensive_urgency(doc) -> None:
	"""Set doc.flags.hypertensive_urgency when BP meets urgency thresholds.

	Non-blocking — callers must not raise from this function.
	"""
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
	"""Enforce template required fields and check hypertensive urgency at before_submit.

	Raises frappe.ValidationError for the first missing required field.
	Hypertensive urgency is flagged non-blocking via check_hypertensive_urgency.
	"""
	template = _get_template(doc.get("appointment_type"))
	if not template:
		return

	required = _load_json(template.get("required_fields"), [])
	for field in required:
		if not doc.get(field):
			label = frappe.get_meta("Patient Encounter").get_label(field) or field
			frappe.throw(
				frappe._(
					"Field <b>{0}</b> is required for {1} encounters before submission."
				).format(label, doc.get("appointment_type")),
				frappe.ValidationError,
			)

	check_hypertensive_urgency(doc)


@frappe.whitelist()
def get_template_for_type(encounter_type: str):
	"""Return template defaults, required fields, auto-orders, and smart-orders.

	Returns None when no template is configured for the given type.
	"""
	template = _get_template(encounter_type)
	if not template:
		return None

	return {
		"template_name": template.template_name,
		"field_defaults": _load_json(template.get("field_defaults"), {}),
		"required_fields": _load_json(template.get("required_fields"), []),
		"auto_orders": _load_json(template.get("auto_orders"), []),
		"smart_orders": _load_json(template.get("smart_orders"), []),
	}
