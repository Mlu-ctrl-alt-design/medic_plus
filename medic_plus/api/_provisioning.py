"""
Shared provisioning helpers used by both the admin onboarding API
and the self-registration flow.

All functions are intentionally side-effect free (no frappe.db.commit).
Callers are responsible for transaction management.
"""

import frappe
from frappe import _


def _safe_company_abbr(practice_name: str) -> str:
	"""Generate a unique ERPNext company abbreviation from the practice name."""
	base = "".join(w[0].upper() for w in practice_name.split() if w)[:4] or "P"
	if not frappe.db.exists("Company", {"abbr": base}):
		return base
	for i in range(2, 1000):
		candidate = f"{base}{i}"
		if not frappe.db.exists("Company", {"abbr": candidate}):
			return candidate
	frappe.throw(_("Could not generate a unique company abbreviation for '{0}'.").format(practice_name))


def create_company(practice_name: str) -> str:
	"""Create an ERPNext Company for this practice. Returns the company name."""
	abbr = _safe_company_abbr(practice_name)
	company = frappe.get_doc({
		"doctype": "Company",
		"company_name": practice_name,
		"abbr": abbr,
		"default_currency": "ZAR",
		"country": "South Africa",
	})
	company.insert(ignore_permissions=True)
	return company.name


def create_practice(practice_name: str) -> object:
	practice = frappe.get_doc({
		"doctype": "Practice",
		"practice_name": practice_name,
		"is_active": 1,
	})
	practice.insert(ignore_permissions=True)
	return practice


def create_user(full_name: str, email: str, mobile: str, roles: list[str]):
	parts = full_name.split()
	first = parts[0]
	last = " ".join(parts[1:]) if len(parts) > 1 else ""

	user = frappe.get_doc({
		"doctype": "User",
		"email": email,
		"first_name": first,
		"last_name": last,
		"mobile_no": mobile,
		"send_welcome_email": 1,
		"roles": [{"role": r} for r in roles],
	})
	user.insert(ignore_permissions=True)
	return user


def create_practitioner(
	full_name: str,
	email: str,
	hpcsa_number: str,
	practice_number: str,
):
	parts = full_name.split()
	practitioner = frappe.get_doc({
		"doctype": "Healthcare Practitioner",
		"first_name": parts[0],
		"last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
		"user_id": email,
		"custom_hpcsa_number": hpcsa_number,
		"custom_practice_number": practice_number,
	})
	practitioner.insert(ignore_permissions=True)
	return practitioner


def create_practice_member(
	practice: str,
	user: str,
	practitioner: str,
	role: str = "Doctor",
	status: str = "Accepted",
	full_name: str = "",
	email: str = "",
):
	# Derive full_name and email from the User record if not provided
	if not full_name or not email:
		user_doc = frappe.get_doc("User", user)
		if not full_name:
			full_name = user_doc.full_name or user
		if not email:
			email = user_doc.email or user

	member = frappe.get_doc({
		"doctype": "Practice Member",
		"practice": practice,
		"full_name": full_name,
		"email": email,
		"user": user,
		"role": role,
		"status": status,
		"practitioner": practitioner,
	})
	member.insert(ignore_permissions=True)
	return member


def create_pos_profile(practice_name: str, company: str) -> str | None:
	"""Create a POS Profile for the practice. Returns profile name, or None on failure."""
	abbr = frappe.db.get_value("Company", company, "abbr")
	if not abbr:
		return None

	write_off_account = frappe.db.get_value(
		"Account", {"company": company, "account_name": "Write Off"}, "name"
	)
	write_off_cost_center = frappe.db.get_value(
		"Cost Center", {"company": company, "cost_center_name": "Main"}, "name"
	)
	if not write_off_account or not write_off_cost_center:
		frappe.log_error(
			f"Cannot create POS Profile for {company}: write-off account or cost center not found.",
			"POS Profile Provisioning",
		)
		return None

	# Default payment method — Cash
	cash_account = frappe.db.get_value(
		"Account", {"company": company, "account_name": "Cash"}, "name"
	)

	profile = frappe.get_doc({
		"doctype": "POS Profile",
		"pos_profile_name": f"{practice_name} - POS",
		"company": company,
		"currency": "ZAR",
		"write_off_account": write_off_account,
		"write_off_cost_center": write_off_cost_center,
		"write_off_limit": 0,
		"payments": [
			{
				"mode_of_payment": "Cash",
				"account": cash_account or "",
				"default": 1,
			}
		] if cash_account else [],
	})
	profile.insert(ignore_permissions=True)
	return profile.name


def create_practice_folder(practice_name: str) -> str:
	"""Create a Home/Practices/{practice_name} document folder. Returns the folder path."""
	# Ensure the parent Practices folder exists
	if not frappe.db.exists("File", {"file_name": "Practices", "is_folder": 1, "folder": "Home"}):
		frappe.get_doc({
			"doctype": "File",
			"file_name": "Practices",
			"is_folder": 1,
			"folder": "Home",
		}).insert(ignore_permissions=True)

	folder_name = practice_name[:140]  # File.file_name is varchar(150)
	if not frappe.db.exists("File", {"file_name": folder_name, "is_folder": 1, "folder": "Home/Practices"}):
		frappe.get_doc({
			"doctype": "File",
			"file_name": folder_name,
			"is_folder": 1,
			"folder": "Home/Practices",
		}).insert(ignore_permissions=True)

	return f"Home/Practices/{folder_name}"


def create_dispensary_warehouse(practice_name: str, practice: str, company: str) -> str:
	"""Create a dispensary warehouse linked to the practice's own company."""
	warehouse = frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": f"{practice_name} - Dispensary",
		"company": company,
		"custom_practice": practice,
	})
	warehouse.insert(ignore_permissions=True)
	return warehouse.name


def provision_doctor(
	full_name: str,
	email: str,
	mobile: str,
	hpcsa_number: str,
	practice_number: str,
	practice_name: str,
	is_dispensing_doctor: bool = False,
) -> dict:
	"""
	Full doctor provisioning: Company → Practice → Practitioner → Practice Member → (Warehouse).
	Assumes the User record already exists.
	Raises on any failure — callers must rollback.
	"""
	company_name = create_company(practice_name)
	practice = create_practice(practice_name)

	# Link the practice to its ERPNext company
	frappe.db.set_value("Practice", practice.name, "company", company_name)

	# Create the onboarding checklist for this practice
	frappe.get_doc({
		"doctype": "Practice Setup Checklist",
		"practice": practice.name,
	}).insert(ignore_permissions=True)

	practitioner = create_practitioner(full_name, email, hpcsa_number, practice_number)
	create_practice_member(practice.name, email, practitioner.name, full_name=full_name, email=email)

	pos_profile = create_pos_profile(practice_name, company_name)
	folder = create_practice_folder(practice_name)

	warehouse_name = None
	if is_dispensing_doctor:
		warehouse_name = create_dispensary_warehouse(practice_name, practice.name, company_name)

	return {
		"practice": practice.name,
		"company": company_name,
		"practitioner": practitioner.name,
		"pos_profile": pos_profile,
		"folder": folder,
		"warehouse": warehouse_name,
	}


def provision_patient(
	full_name: str,
	email: str,
	mobile: str,
	date_of_birth: str | None = None,
	preferred_practice: str | None = None,
) -> dict:
	"""
	Patient provisioning: creates a Patient record linked to their User.
	Assumes the User record already exists.
	"""
	parts = full_name.split()
	patient = frappe.get_doc({
		"doctype": "Patient",
		"first_name": parts[0],
		"last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
		"email": email,
		"mobile": mobile,
		"dob": date_of_birth,
		"custom_practice": preferred_practice,
		"patient_name": full_name,
	})
	patient.insert(ignore_permissions=True)

	return {"patient": patient.name}
