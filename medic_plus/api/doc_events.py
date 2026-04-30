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


def apply_encounter_template(doc, method=None):
	"""Apply an Encounter Template's defaults to a new Patient Encounter."""
	from medic_plus.api.encounter_templates import apply_template
	apply_template(doc)


def validate_encounter_template_fields(doc, method=None):
	"""Enforce Encounter Template required fields before submit."""
	from medic_plus.api.encounter_templates import validate_template_fields
	validate_template_fields(doc)


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


def validate_patient_identifiers(doc, method=None):
    """Validate Patient Identifier child rows and derive DOB/sex from SA ID.

    Called from the Patient 'validate' doc event so it runs before mandatory
    field checks fire on the native Healthcare Patient.validate().
    """
    from medic_plus.api.sa_id import validate_said, parse_said

    identifiers = doc.get("custom_identifiers") or []
    if not identifiers:
        return

    has_said = any(r.id_type == "SAID" for r in identifiers)
    if has_said and not doc.get("custom_popia_consent_special"):
        frappe.throw(
            frappe._(
                "POPIA consent for special personal information is required "
                "when providing an SA ID number."
            ),
            frappe.ValidationError,
        )

    primary_count = 0
    for row in identifiers:
        if row.id_type == "SAID":
            validate_said(row.id_value)
            parsed = parse_said(row.id_value)
            if not doc.dob:
                doc.dob = parsed["dob"]
            if not doc.sex:
                doc.sex = parsed["sex"]
        if int(row.get("is_primary") or 0):
            primary_count += 1

    if primary_count > 1:
        frappe.throw(
            frappe._("Only one identifier may be marked as primary."),
            frappe.ValidationError,
        )


def sync_practice_doctors(doc, method=None):
	"""Keep Practice Member (role=Doctor) in sync with the Practice.doctors child table.

	Called on Practice after_insert and on_update. For each row in doc.doctors:
	  - If no matching Practice Member exists, create one.
	For any Practice Member (role=Doctor) whose practitioner is no longer in the
	doctors table, remove it.
	"""
	current_practitioners = {row.practitioner for row in (doc.doctors or []) if row.practitioner}

	# Existing Doctor Practice Members for this practice
	existing = frappe.get_all(
		"Practice Member",
		filters={"practice": doc.name, "role": "Doctor"},
		fields=["name", "practitioner"],
		ignore_permissions=True,
	)
	existing_map = {pm["practitioner"]: pm["name"] for pm in existing}

	# Add missing members
	for practitioner in current_practitioners:
		if practitioner not in existing_map:
			pm = frappe.get_doc({
				"doctype": "Practice Member",
				"practice": doc.name,
				"practitioner": practitioner,
				"role": "Doctor",
			})
			pm.insert(ignore_permissions=True)

	# Remove stale members (practitioner removed from child table)
	for practitioner, pm_name in existing_map.items():
		if practitioner not in current_practitioners:
			frappe.delete_doc("Practice Member", pm_name, ignore_permissions=True, force=True)
