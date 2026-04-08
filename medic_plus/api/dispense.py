"""
Dispensing API.

Creates a Stock Entry (Material Issue) from the Drug Prescription rows on a
submitted Patient Encounter, deducting stock from the practice's Dispensary
warehouse.

Only callable by users who are Practice Doctors with dispensing enabled.
"""

import frappe
from frappe import _


@frappe.whitelist()
def dispense_encounter(encounter_name: str) -> dict:
	"""Create a Material Issue Stock Entry for all prescribed drugs.

	Args:
		encounter_name: The name of the submitted Patient Encounter.

	Returns:
		dict with the created Stock Entry name.

	Raises:
		frappe.PermissionError: If the caller's practice is not a dispensing practice.
		frappe.ValidationError: If the encounter has no drug prescriptions or
		    the warehouse cannot be resolved.
	"""
	encounter = frappe.get_doc("Patient Encounter", encounter_name)

	# --- Permission: caller must be a member of the encounter's practice ---
	practice = encounter.custom_practice
	if not practice:
		frappe.throw(_("Encounter has no linked Practice."), frappe.ValidationError)

	_assert_dispensing_access(practice)

	# --- Resolve the practice's Dispensary warehouse ---
	warehouse = frappe.db.get_value(
		"Warehouse", {"custom_practice": practice}, "name"
	)
	if not warehouse:
		frappe.throw(
			_("No Dispensary warehouse found for practice {0}. "
			  "Ensure the doctor has dispensing enabled.").format(practice),
			frappe.ValidationError,
		)

	# --- Build Stock Entry items from drug_prescription rows ---
	drugs = encounter.drug_prescription or []
	stock_items = []
	for row in drugs:
		if not row.drug_code:
			continue
		is_stock_item = frappe.db.get_value("Item", row.drug_code, "is_stock_item")
		if not is_stock_item:
			continue  # prescribe-only items are skipped
		stock_items.append({
			"item_code": row.drug_code,
			"qty": _resolve_qty(row),
			"s_warehouse": warehouse,
		})

	if not stock_items:
		frappe.throw(
			_("No stock items found in this encounter's drug prescription. "
			  "Ensure medicines are marked as stock items in the Item master."),
			frappe.ValidationError,
		)

	# --- Create Stock Entry ---
	stock_entry = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Issue",
		"from_warehouse": warehouse,
		"custom_practice": practice,
		"remarks": f"Dispensed from Patient Encounter {encounter_name}",
		"items": stock_items,
	})
	stock_entry.insert(ignore_permissions=True)
	stock_entry.submit()

	return {
		"stock_entry": stock_entry.name,
		"message": _("{0} item(s) dispensed. Stock Entry: {1}").format(
			len(stock_items), stock_entry.name
		),
	}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _assert_dispensing_access(practice: str) -> None:
	"""Ensure the session user is a Doctor member of this practice and that
	the practice has a dispensing-enabled practitioner."""
	if "Healthcare Administrator" in frappe.get_roles():
		return

	member = frappe.db.get_value(
		"Practice Member",
		{"practice": practice, "user": frappe.session.user, "role": "Doctor"},
		["practitioner"],
		as_dict=True,
	)
	if not member:
		frappe.throw(
			_("You are not a Doctor member of practice {0}.").format(practice),
			frappe.PermissionError,
		)

	is_dispensing = frappe.db.get_value(
		"Healthcare Practitioner",
		member.practitioner,
		"custom_is_dispensing_doctor",
	)
	if not is_dispensing:
		frappe.throw(
			_("Your practitioner account is not configured as a dispensing doctor."),
			frappe.PermissionError,
		)


def _resolve_qty(row) -> float:
	"""Determine dispensing quantity from the prescription row.

	The Drug Prescription child table does not have a native qty field.
	We default to 1 unit per prescribed item. Future: derive from dosage × period.
	"""
	return 1.0
