import frappe
from medic_plus.medic_plus.doctype.practice_setup_checklist.practice_setup_checklist import (
	on_practice_profile_complete,
	on_signature_saved,
	on_staff_accepted,
	on_patient_invited,
	on_schedule_created,
	on_billing_configured,
)


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


def update_checklist_on_practice_save(doc, method=None):
	"""Step 1 — mark practice profile complete once name + phone/email are present."""
	if doc.practice_name and (doc.phone or doc.email):
		on_practice_profile_complete(doc.name)


def update_checklist_on_signature(doc, method=None):
	"""Step 2 — mark signature step complete when practitioner saves a signature."""
	if not doc.has_value_changed("custom_practitioner_signature"):
		return
	if not doc.get("custom_practitioner_signature"):
		return
	practice = frappe.db.get_value(
		"Practice Member", {"practitioner": doc.name, "role": "Doctor"}, "practice"
	)
	if practice:
		on_signature_saved(practice)


def update_checklist_on_member_status(doc, method=None):
	"""Steps 3 & 4 — update checklist when a Practice Member is added.

	Practice Member has no 'status' field.  We tick the checklist step
	immediately on insert/update based solely on role:
	  - Doctor / Admin / Receptionist → staff has been added (step 3)
	  - Patient                        → a patient has been invited (step 4)
	"""
	practice = doc.practice
	role = doc.role

	if not practice or not role:
		return

	if role in ("Admin", "Doctor", "Receptionist"):
		on_staff_accepted(practice)
	elif role == "Patient":
		on_patient_invited(practice)


def update_checklist_on_schedule_created(doc, method=None):
	"""Step 5 — tick when a Practitioner Schedule is created for this practice."""
	practice = frappe.db.get_value(
		"Practice Member", {"practitioner": doc.practitioner, "role": "Doctor"}, "practice"
	)
	if practice:
		on_schedule_created(practice)


def update_checklist_on_first_invoice(doc, method=None):
	"""Step 6 — tick when the practice's first Sales Invoice is created."""
	practice = frappe.db.get_value("Practice", {"company": doc.company}, "name")
	if practice:
		on_billing_configured(practice)
