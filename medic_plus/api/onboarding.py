"""
Doctor onboarding API.

Single whitelisted call that provisions an entire doctor tenant:
  Practice → User → Practice Member → (Warehouse if dispensing)

Restricted to System Manager role.
Wrapped in a transaction — any failure rolls back all inserts.
"""

import re
import frappe
from frappe import _


@frappe.whitelist()
def onboard_doctor(
	full_name: str,
	email: str,
	mobile: str,
	hpcsa_number: str,
	practice_number: str,
	practice_name: str,
	is_dispensing_doctor: bool = False,
) -> dict:
	"""Provision a new doctor tenant end-to-end.

	Args:
		full_name: Doctor's full name (e.g. "Dr Jane Nkosi")
		email: Login email — becomes the Frappe User name
		mobile: Mobile number
		hpcsa_number: HPCSA registration number
		practice_number: Practice/billing number
		practice_name: Display name of the practice
		is_dispensing_doctor: Whether to provision a Dispensary warehouse

	Returns:
		dict with created record names and a success message.

	Raises:
		frappe.PermissionError: If caller is not a System Manager.
		frappe.ValidationError: If email or practice_name already exists.
	"""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can onboard doctors."), frappe.PermissionError)

	is_dispensing_doctor = frappe.utils.cint(is_dispensing_doctor)

	_validate_inputs(email, practice_name)

	try:
		practice = _create_practice(practice_name)
		user = _create_user(full_name, email, mobile)
		practitioner = _create_practitioner(full_name, email, hpcsa_number, practice_number)
		_create_practice_member(practice.name, email, practitioner.name)

		warehouse_name = None
		if is_dispensing_doctor:
			warehouse_name = _create_dispensary_warehouse(practice_name, practice.name)

		frappe.db.commit()

	except Exception:
		frappe.db.rollback()
		raise

	return {
		"practice": practice.name,
		"user": email,
		"practitioner": practitioner.name,
		"warehouse": warehouse_name,
		"message": _("Doctor {0} onboarded successfully.").format(full_name),
	}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _validate_inputs(email: str, practice_name: str) -> None:
	if frappe.db.exists("User", email):
		frappe.throw(_("A user with email {0} already exists.").format(email), frappe.ValidationError)
	if frappe.db.exists("Practice", {"practice_name": practice_name}):
		frappe.throw(
			_("A practice named '{0}' already exists.").format(practice_name), frappe.ValidationError
		)


def _create_practice(practice_name: str):
	practice = frappe.get_doc({
		"doctype": "Practice",
		"practice_name": practice_name,
		"is_active": 1,
	})
	practice.insert(ignore_permissions=True)
	return practice


def _create_user(full_name: str, email: str, mobile: str):
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
		"roles": [{"role": "Practice Doctor"}],
	})
	user.insert(ignore_permissions=True)
	return user


def _create_practitioner(
	full_name: str, email: str, hpcsa_number: str, practice_number: str
):
	practitioner = frappe.get_doc({
		"doctype": "Healthcare Practitioner",
		"first_name": full_name.split()[0],
		"last_name": " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "",
		"user_id": email,
		"custom_hpcsa_number": hpcsa_number,
		"custom_practice_number": practice_number,
	})
	practitioner.insert(ignore_permissions=True)
	return practitioner


def _create_practice_member(practice: str, user: str, practitioner: str):
	member = frappe.get_doc({
		"doctype": "Practice Member",
		"practice": practice,
		"user": user,
		"role": "Doctor",
		"practitioner": practitioner,
	})
	member.insert(ignore_permissions=True)
	return member


def _create_dispensary_warehouse(practice_name: str, practice: str) -> str:
	default_company = frappe.defaults.get_global_default("company")
	if not default_company:
		frappe.throw(
			_("Cannot provision dispensary: no default company is configured on this site."),
			frappe.ValidationError,
		)

	warehouse_name = f"{practice_name} - Dispensary"
	warehouse = frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": warehouse_name,
		"company": default_company,
		"custom_practice": practice,
	})
	warehouse.insert(ignore_permissions=True)
	return warehouse.name
