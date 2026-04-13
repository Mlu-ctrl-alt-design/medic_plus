import frappe


def _get_user_practice(user: str = None) -> str | None:
	return frappe.db.get_value(
		"Practice Member", {"user": user or frappe.session.user}, "practice"
	)


def _is_platform_admin(user: str = None) -> bool:
	# C1 fix: always resolve roles for the *given* user, not the session user.
	# Frappe passes an explicit user to PQC functions for background jobs and
	# shared-document scenarios; using frappe.session.user here would silently
	# return "" (unrestricted) for any admin running the session, even when
	# evaluating permissions for a different target user.
	return "Healthcare Administrator" in frappe.get_roles(user or frappe.session.user)


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
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPatient`.`custom_practice` = {frappe.db.escape(practice)}"


def get_patient_appointment_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
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


def get_sick_note_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
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
