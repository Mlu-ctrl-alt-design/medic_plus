import frappe


def _get_user_practice(user: str = None) -> str | None:
	return frappe.db.get_value(
		"Practice Member", {"user": user or frappe.session.user}, "practice"
	)


def _get_practice_company(practice: str) -> str | None:
	return frappe.db.get_value("Practice", practice, "company")


def _is_platform_admin(user: str = None) -> bool:
	# C1 fix: always resolve roles for the *given* user, not the session user.
	# Frappe passes an explicit user to PQC functions for background jobs and
	# shared-document scenarios; using frappe.session.user here would silently
	# return "" (unrestricted) for any admin running the session, even when
	# evaluating permissions for a different target user.
	return "Healthcare Administrator" in frappe.get_roles(user or frappe.session.user)


def _get_patient_name_for_user(user: str = None) -> str | None:
	"""Return the Patient record name whose email matches the given user."""
	return frappe.db.get_value("Patient", {"email": user or frappe.session.user}, "name")


def get_practice_permission_query(user: str = None) -> str:
	"""PQC for the Practice doctype — filters by practice name."""
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPractice`.`name` = {frappe.db.escape(practice)}"


def get_practice_member_permission_query(user: str = None) -> str:
	"""PQC for Practice Member — filters by the practice field."""
	# C2 fix: each doctype needs its own table name and field reference.
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPractice Member`.`practice` = {frappe.db.escape(practice)}"


def get_patient_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	# Patients with the Patient role see only their own record
	if "Patient" in frappe.get_roles(user or frappe.session.user):
		patient = _get_patient_name_for_user(user)
		return f"`tabPatient`.`name` = {frappe.db.escape(patient)}" if patient else "1=0"
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPatient`.`custom_practice` = {frappe.db.escape(practice)}"


def get_patient_appointment_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	# Patients see only their own appointments
	if "Patient" in frappe.get_roles(user or frappe.session.user):
		patient = _get_patient_name_for_user(user)
		return f"`tabPatient Appointment`.`patient` = {frappe.db.escape(patient)}" if patient else "1=0"
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPatient Appointment`.`custom_practice` = {frappe.db.escape(practice)}"


def get_patient_encounter_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPatient Encounter`.`custom_practice` = {frappe.db.escape(practice)}"


def get_inpatient_record_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabInpatient Record`.`custom_practice` = {frappe.db.escape(practice)}"


def _scope_via_patient(table: str, user: str) -> str:
	"""Common scope shape: doctype rows whose `patient` belongs to active practice.

	Used by SA EMR Phase 1 doctypes that link to Patient and have a denormalised
	`custom_practice` field (Patient Allergy, Patient Chronic Condition) — the
	subquery is redundant when `custom_practice` is reliable, but acts as
	defence in depth and keeps the code path identical for doctypes that lack
	the denormalised field (Patient Insurance Policy / Coverage).
	"""
	if _is_platform_admin(user):
		return ""
	roles = frappe.get_roles(user or frappe.session.user)
	if "Patient" in roles:
		patient = _get_patient_name_for_user(user)
		return f"`{table}`.`patient` = {frappe.db.escape(patient)}" if patient else "1=0"
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return (
		f"`{table}`.`patient` IN ("
		f"SELECT `name` FROM `tabPatient` WHERE `custom_practice` = {frappe.db.escape(practice)}"
		")"
	)


def get_patient_allergy_permission_query(user: str = None) -> str:
	return _scope_via_patient("tabPatient Allergy", user)


def get_patient_chronic_condition_permission_query(user: str = None) -> str:
	return _scope_via_patient("tabPatient Chronic Condition", user)


def get_patient_insurance_policy_permission_query(user: str = None) -> str:
	return _scope_via_patient("tabPatient Insurance Policy", user)


def get_patient_insurance_coverage_permission_query(user: str = None) -> str:
	return _scope_via_patient("tabPatient Insurance Coverage", user)


def get_patient_medical_record_permission_query(user: str = None) -> str:
	# Patient Medical Record carries no `custom_practice` of its own — it
	# inherits scope from the linked Patient. Bridge via a subquery so the
	# usual `tabX.custom_practice = ...` shape applies.
	if _is_platform_admin(user):
		return ""
	roles = frappe.get_roles(user or frappe.session.user)
	if "Patient" in roles:
		patient = _get_patient_name_for_user(user)
		return (
			f"`tabPatient Medical Record`.`patient` = {frappe.db.escape(patient)}"
			if patient else "1=0"
		)
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return (
		"`tabPatient Medical Record`.`patient` IN ("
		f"SELECT `name` FROM `tabPatient` WHERE `custom_practice` = {frappe.db.escape(practice)}"
		")"
	)


def get_sick_note_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	# Patients see only their own sick notes
	if "Patient" in frappe.get_roles(user or frappe.session.user):
		patient = _get_patient_name_for_user(user)
		return f"`tabSick Note`.`patient` = {frappe.db.escape(patient)}" if patient else "1=0"
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabSick Note`.`practice` = {frappe.db.escape(practice)}"


def get_stock_entry_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabStock Entry`.`custom_practice` = {frappe.db.escape(practice)}"


def get_warehouse_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabWarehouse`.`custom_practice` = {frappe.db.escape(practice)}"


def get_healthcare_practitioner_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	# Practitioners visible within the same practice
	member_practitioners = frappe.get_all(
		"Practice Member",
		filters={"practice": practice},
		pluck="practitioner",
	)
	member_practitioners = [p for p in member_practitioners if p]
	if not member_practitioners:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(p) for p in member_practitioners)
	return f"`tabHealthcare Practitioner`.`name` IN ({escaped})"


def get_practitioner_schedule_permission_query(user: str = None) -> str:
	"""Practitioner Schedule visibility scoped to practitioners in the user's practice.

	Healthcare's Practitioner Schedule has no `custom_practice` of its own;
	instead each schedule references a practitioner via `practitioner` Link.
	We reuse the same Practice Member → practitioner derivation as the
	healthcare practitioner PQC.
	"""
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	member_practitioners = frappe.get_all(
		"Practice Member",
		filters={"practice": practice},
		pluck="practitioner",
	)
	member_practitioners = [p for p in member_practitioners if p]
	if not member_practitioners:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(p) for p in member_practitioners)
	return f"`tabPractitioner Schedule`.`practitioner` IN ({escaped})"


def _get_company_filter(user: str, table: str, field: str = "company") -> str:
	"""Return a WHERE clause scoping a financial doctype to the user's practice company."""
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	company = _get_practice_company(practice)
	if not company:
		return "1=0"
	return f"`tab{table}`.`{field}` = {frappe.db.escape(company)}"


def get_practice_setup_checklist_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPractice Setup Checklist`.`practice` = {frappe.db.escape(practice)}"


def get_data_unmask_request_permission_query(user: str = None) -> str:
	"""PQC for Data Unmask Request — filters by the practice field."""
	# C2 fix: uses the correct table and field for this doctype.
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabData Unmask Request`.`practice` = {frappe.db.escape(practice)}"


def get_clinical_access_log_permission_query(user: str = None) -> str:
	"""PQC for Clinical Access Log — filters by the practice field."""
	# C2 fix: uses the correct table and field for this doctype.
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabClinical Access Log`.`practice` = {frappe.db.escape(practice)}"


def get_patient_identifier_permission_query(user: str = None) -> str:
	"""PQC for Patient Identifier child table — scopes via parent Patient's practice.

	Patient Identifier rows are child records of Patient. Access is gated via the
	parent Patient's custom_practice so that cross-tenant reads are denied even
	when querying /api/resource/Patient Identifier directly.
	"""
	if _is_platform_admin(user):
		return ""
	roles = frappe.get_roles(user or frappe.session.user)
	if "Patient" in roles:
		patient = _get_patient_name_for_user(user)
		return (
			f"`tabPatient Identifier`.`parent` = {frappe.db.escape(patient)}"
			if patient else "1=0"
		)
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return (
		"`tabPatient Identifier`.`parent` IN ("
		f"SELECT `name` FROM `tabPatient` WHERE `custom_practice` = {frappe.db.escape(practice)}"
		")"
	)


def get_sales_invoice_permission_query(user: str = None) -> str:
	return _get_company_filter(user, "Sales Invoice")


def get_pos_profile_permission_query(user: str = None) -> str:
	return _get_company_filter(user, "POS Profile")


def get_payment_entry_permission_query(user: str = None) -> str:
	return _get_company_filter(user, "Payment Entry")


def get_purchase_invoice_permission_query(user: str = None) -> str:
	return _get_company_filter(user, "Purchase Invoice")


def get_journal_entry_permission_query(user: str = None) -> str:
	return _get_company_filter(user, "Journal Entry")
