import frappe


def _get_user_practice() -> str | None:
	return frappe.db.get_value(
		"Practice Member", {"user": frappe.session.user}, "practice"
	)


def set_practice_on_insert(doc, method=None):
	"""Auto-set custom_practice on Healthcare DocTypes before insert."""
	if not doc.get("custom_practice"):
		practice = _get_user_practice()
		if practice:
			doc.custom_practice = practice


def provision_dispensary_on_update(doc, method=None):
	"""Auto-provision a Dispensary warehouse when a doctor enables dispensing."""
	if not doc.get("custom_is_dispensing_doctor"):
		return
	if not doc.has_value_changed("custom_is_dispensing_doctor"):
		return

	# Resolve the practice linked to this practitioner via Practice Member
	practice = frappe.db.get_value(
		"Practice Member", {"practitioner": doc.name, "role": "Doctor"}, "practice"
	)
	if not practice:
		return

	practice_doc = frappe.get_doc("Practice", practice)
	warehouse_name = f"{practice_doc.practice_name} - Dispensary"

	if frappe.db.exists("Warehouse", {"warehouse_name": warehouse_name}):
		return

	# Warehouses require the practice's own ERPNext Company
	company = practice_doc.get("company")
	if not company:
		frappe.log_error(
			f"Cannot provision dispensary for {doc.name}: practice '{practice}' has no linked company.",
			"Dispensary Provisioning"
		)
		return

	frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": warehouse_name,
		"company": company,
		"custom_practice": practice,
	}).insert(ignore_permissions=True)
