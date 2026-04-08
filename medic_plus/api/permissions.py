import frappe


def _get_user_practice(user: str = None) -> str | None:
	return frappe.db.get_value(
		"Practice Member", {"user": user or frappe.session.user}, "practice"
	)


def _is_platform_admin() -> bool:
	return "Healthcare Administrator" in frappe.get_roles()


def get_practice_permission_query(user: str = None) -> str:
	if _is_platform_admin():
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPractice`.`name` = {frappe.db.escape(practice)}"


def get_patient_permission_query(user: str = None) -> str:
	if _is_platform_admin():
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPatient`.`custom_practice` = {frappe.db.escape(practice)}"


def get_patient_appointment_permission_query(user: str = None) -> str:
	if _is_platform_admin():
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPatient Appointment`.`custom_practice` = {frappe.db.escape(practice)}"


def get_patient_encounter_permission_query(user: str = None) -> str:
	if _is_platform_admin():
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPatient Encounter`.`custom_practice` = {frappe.db.escape(practice)}"


def get_inpatient_record_permission_query(user: str = None) -> str:
	if _is_platform_admin():
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabInpatient Record`.`custom_practice` = {frappe.db.escape(practice)}"


def get_sick_note_permission_query(user: str = None) -> str:
	if _is_platform_admin():
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabSick Note`.`practice` = {frappe.db.escape(practice)}"


def get_healthcare_practitioner_permission_query(user: str = None) -> str:
	if _is_platform_admin():
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
