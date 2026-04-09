"""
Admin-only doctor onboarding API.

Restricted to System Manager. For self-service registration use
medic_plus.api.registration instead.
"""

import frappe
from frappe import _

from medic_plus.api._provisioning import create_user, provision_doctor


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
	"""Provision a new doctor tenant end-to-end (admin use only).

	Raises:
		frappe.PermissionError: If caller is not a System Manager.
		frappe.ValidationError: If email or practice_name already exists.
	"""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can onboard doctors."), frappe.PermissionError)

	is_dispensing_doctor = bool(frappe.utils.cint(is_dispensing_doctor))
	_validate_inputs(email, practice_name)

	try:
		create_user(full_name, email, mobile, roles=["Practice Doctor", "Practice Admin"])
		result = provision_doctor(
			full_name=full_name,
			email=email,
			mobile=mobile,
			hpcsa_number=hpcsa_number,
			practice_number=practice_number,
			practice_name=practice_name,
			is_dispensing_doctor=is_dispensing_doctor,
		)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		raise

	return {
		"user": email,
		**result,
		"message": _("Doctor {0} onboarded successfully.").format(full_name),
	}


def _validate_inputs(email: str, practice_name: str) -> None:
	if frappe.db.exists("User", email):
		frappe.throw(_("A user with email {0} already exists.").format(email), frappe.ValidationError)
	if frappe.db.exists("Practice", {"practice_name": practice_name}):
		frappe.throw(
			_("A practice named '{0}' already exists.").format(practice_name), frappe.ValidationError
		)
