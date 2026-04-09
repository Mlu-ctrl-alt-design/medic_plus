import frappe


def _get_user_practice(user: str = None) -> str | None:
	return frappe.db.get_value(
		"Practice Member", {"user": user or frappe.session.user}, "practice"
	)


def _get_practice_company(practice: str) -> str | None:
	return frappe.db.get_value("Practice", practice, "company")


def _is_platform_admin(user: str = None) -> bool:
	"""Returns True if the given user (or current session user) has Healthcare Administrator role."""
	return "Healthcare Administrator" in frappe.get_roles(user or frappe.session.user)


def get_practice_permission_query(user: str = None) -> str:
	if _is_platform_admin(user):
		return ""
	practice = _get_user_practice(user)
	if not practice:
		return "1=0"
	return f"`tabPractice`.`name` = {frappe.db.escape(practice)}"


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
