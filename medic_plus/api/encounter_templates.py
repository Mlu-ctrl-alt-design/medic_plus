"""Encounter Template — apply defaults and enforce required fields.

Public surface:
  apply_template(doc)          — called from Patient Encounter before_insert
  validate_template_fields(doc) — called from Patient Encounter before_submit
  get_template_for_type(encounter_type) — whitelisted; used by the frontend
"""

import json

import frappe

ANTENATAL_TEMPLATE_NAME = "Antenatal Visit Template"


def _get_template(appointment_type: str):
	"""Return the best Encounter Template for *appointment_type*, or None.

	Practice-scoped templates take priority over platform templates.
	"""
	if not appointment_type:
		return None

	practice = frappe.db.get_value(
		"Practice Member", {"user": frappe.session.user}, "practice"
	)

	# Practice-scoped template first
	if practice:
		name = frappe.db.get_value(
			"Encounter Template",
			{"appointment_type": appointment_type, "practice": practice},
			"name",
		)
		if name:
			return frappe.get_doc("Encounter Template", name)

	# Fall back to platform template
	name = frappe.db.get_value(
		"Encounter Template",
		{"appointment_type": appointment_type, "is_platform_template": 1},
		"name",
	)
	return frappe.get_doc("Encounter Template", name) if name else None


def apply_template(doc) -> None:
	"""Apply an Encounter Template's defaults to *doc* before insert.

	Sets field defaults and appends pre-populated Encounter Order rows.
	No-ops when no template exists for the appointment_type.
	"""
	template = _get_template(doc.get("appointment_type"))
	if not template:
		return

	# Apply field defaults
	raw = template.get("field_defaults") or "{}"
	defaults = json.loads(raw) if isinstance(raw, str) else (raw or {})
	for field, value in defaults.items():
		if not doc.get(field):
			doc.set(field, value)

	# Append auto-orders (only if the child table is currently empty)
	existing_orders = doc.get("custom_encounter_orders") or []
	if not existing_orders:
		raw_orders = template.get("auto_orders") or "[]"
		orders = json.loads(raw_orders) if isinstance(raw_orders, str) else (raw_orders or [])
		for order in orders:
			doc.append("custom_encounter_orders", {
				"order_type": order.get("order_type", "Lab"),
				"order_name": order.get("order_name", ""),
				"status": "Draft",
				"notes": order.get("notes", ""),
			})


def validate_template_fields(doc) -> None:
	"""Enforce template required fields at before_submit.

	Raises frappe.ValidationError listing the first missing required field.
	"""
	template = _get_template(doc.get("appointment_type"))
	if not template:
		return

	raw = template.get("required_fields") or "[]"
	required = json.loads(raw) if isinstance(raw, str) else (raw or [])

	for field in required:
		if not doc.get(field):
			label = frappe.get_meta("Patient Encounter").get_label(field) or field
			frappe.throw(
				frappe._(
					"Field <b>{0}</b> is required for {1} encounters before submission."
				).format(label, doc.get("appointment_type")),
				frappe.ValidationError,
			)


@frappe.whitelist()
def get_template_for_type(encounter_type: str):
	"""Return template defaults, required fields, and auto-orders for *encounter_type*.

	Returns None when no template is configured for that type.
	Used by the frontend to pre-fill new encounter forms.
	"""
	template = _get_template(encounter_type)
	if not template:
		return None

	raw_defaults = template.get("field_defaults") or "{}"
	raw_required = template.get("required_fields") or "[]"
	raw_orders = template.get("auto_orders") or "[]"

	return {
		"template_name": template.template_name,
		"field_defaults": json.loads(raw_defaults) if isinstance(raw_defaults, str) else (raw_defaults or {}),
		"required_fields": json.loads(raw_required) if isinstance(raw_required, str) else (raw_required or []),
		"auto_orders": json.loads(raw_orders) if isinstance(raw_orders, str) else (raw_orders or []),
	}
