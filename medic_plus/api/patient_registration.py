"""Patient self-registration (kept as-is; doctor flow moved to signup.py)."""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils.html_utils import escape_html

from medic_plus.api.validators import validate_sa_mobile


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=3600)
def register_patient(
	full_name: str,
	email: str,
	mobile: str,
	date_of_birth: str | None = None,
	preferred_practice: str | None = None,
) -> dict:
	"""Create a patient Registration Request and trigger Frappe email verification.

	Provisioning of the Patient record happens on first login via a dedicated
	controller elsewhere; this endpoint only creates the pending request and
	triggers the verification email.
	"""
	from frappe.core.doctype.user.user import sign_up

	email = email.strip().lower()
	full_name = escape_html(full_name.strip())
	mobile = validate_sa_mobile(mobile)

	if frappe.db.exists("User", email):
		frappe.throw(_("An account with this email already exists."), frappe.ValidationError)

	frappe.get_doc({
		"doctype": "Registration Request",
		"email": email,
		"full_name": full_name,
		"mobile": mobile,
		"registration_type": "Patient",
		"status": "Pending",
		"date_of_birth": date_of_birth,
		"preferred_practice": preferred_practice,
	}).insert(ignore_permissions=True)

	code, _msg = sign_up(email=email, full_name=full_name, redirect_to="/")
	if code == 0:
		frappe.throw(_("An account with this email already exists."), frappe.ValidationError)

	return {
		"status": "pending",
		"message": _("Registration received. Please check your email to verify your account."),
	}
