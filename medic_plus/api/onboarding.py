"""Admin-only doctor onboarding.

Single public endpoint delegating to _provisioning.provision_doctor so
the admin path and the paid signup path produce identical tenants.
"""

import frappe
from frappe import _

from medic_plus.api._provisioning import provision_doctor
from medic_plus.api.validators import (
	validate_hpcsa_number,
	validate_practice_number,
	validate_sa_mobile,
)


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
	"""Provision a new doctor tenant end-to-end (admin backdoor)."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can onboard doctors."), frappe.PermissionError)

	email = email.strip().lower()
	mobile = validate_sa_mobile(mobile)
	hpcsa_number = validate_hpcsa_number(hpcsa_number)
	practice_number = validate_practice_number(practice_number)
	is_dispensing_doctor = bool(frappe.utils.cint(is_dispensing_doctor))

	if frappe.db.exists("User", email):
		frappe.throw(_("A user with email {0} already exists.").format(email), frappe.ValidationError)
	if frappe.db.exists("Practice", {"practice_name": practice_name}):
		frappe.throw(
			_("A practice named '{0}' already exists.").format(practice_name), frappe.ValidationError
		)

	try:
		from medic_plus.api._provisioning import create_user
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
		**result,
		"user": email,
		"message": _("Doctor {0} onboarded successfully.").format(full_name),
	}
