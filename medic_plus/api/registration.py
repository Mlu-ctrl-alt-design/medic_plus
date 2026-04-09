"""
Self-service registration API for doctors and patients.

Two guest-callable endpoints create a Registration Request and
trigger Frappe's standard sign_up flow (email verification).

Post-verification provisioning is handled by on_user_verified,
wired via doc_events on User in hooks.py.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils.html_utils import escape_html


# ---------------------------------------------------------------------------
# Guest endpoints
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=3600)
def register_doctor(
	full_name: str,
	email: str,
	mobile: str,
	hpcsa_number: str,
	practice_number: str,
	practice_name: str,
	is_dispensing_doctor: bool = False,
) -> dict:
	"""Create a Registration Request and trigger email verification.

	Returns:
		{"status": "pending", "message": "..."}
	"""
	email = email.strip().lower()
	full_name = escape_html(full_name.strip())

	if mobile:
		_validate_mobile(mobile)
	_validate_registration(email, practice_name=practice_name)

	frappe.get_doc({
		"doctype": "Registration Request",
		"email": email,
		"full_name": full_name,
		"mobile": mobile,
		"registration_type": "Doctor",
		"status": "Pending",
		"hpcsa_number": hpcsa_number,
		"practice_number": practice_number,
		"practice_name": practice_name,
		"is_dispensing_doctor": frappe.utils.cint(is_dispensing_doctor),
	}).insert(ignore_permissions=True)

	_trigger_signup(email, full_name, redirect_to="/")

	return {
		"status": "pending",
		"message": _("Registration received. Please check your email to verify your account."),
	}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=3600)
def register_patient(
	full_name: str,
	email: str,
	mobile: str,
	date_of_birth: str | None = None,
	preferred_practice: str | None = None,
) -> dict:
	"""Create a patient Registration Request and trigger email verification."""
	email = email.strip().lower()
	full_name = escape_html(full_name.strip())

	if mobile:
		_validate_mobile(mobile)
	_validate_registration(email)

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

	_trigger_signup(email, full_name, redirect_to="/")

	return {
		"status": "pending",
		"message": _("Registration received. Please check your email to verify your account."),
	}


# ---------------------------------------------------------------------------
# Post-verification doc_events handler
# ---------------------------------------------------------------------------

def on_user_verified(doc, method=None) -> None:
	"""Fires on every User save. Provisions when enabled flips 0 → 1."""
	if not doc.has_value_changed("enabled") or not doc.enabled:
		return

	req = frappe.db.get_value(
		"Registration Request",
		{"email": doc.email, "status": "Pending"},
		["name", "registration_type", "full_name", "mobile",
		 "hpcsa_number", "practice_number", "practice_name", "is_dispensing_doctor",
		 "date_of_birth", "preferred_practice"],
		as_dict=True,
	)
	if not req:
		return

	try:
		if req.registration_type == "Doctor":
			_provision_doctor_from_request(req, doc)
		else:
			_provision_patient_from_request(req, doc)

		frappe.db.set_value("Registration Request", req.name, {
			"status": "Provisioned",
			"user": doc.name,
		})
		frappe.db.commit()

	except Exception as exc:
		frappe.db.rollback()
		frappe.db.set_value("Registration Request", req.name, {
			"status": "Failed",
			"error_log": str(exc),
		})
		frappe.db.commit()
		frappe.log_error(
			title=f"Registration provisioning failed for {doc.email}",
			message=frappe.get_traceback(),
		)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _validate_mobile(mobile: str) -> None:
	digits = "".join(c for c in mobile if c.isdigit())
	if len(digits) > 10:
		frappe.throw(_("Mobile number must be 10 digits (e.g. 0821234567)."), frappe.ValidationError)


def _validate_registration(email: str, practice_name: str | None = None) -> None:
	if frappe.db.exists("User", email):
		frappe.throw(_("An account with this email already exists."), frappe.ValidationError)
	if frappe.db.exists("Registration Request", {"email": email, "status": "Pending"}):
		frappe.throw(
			_("A pending registration for this email already exists. Please check your inbox."),
			frappe.ValidationError,
		)
	if practice_name and frappe.db.exists("Practice", {"practice_name": practice_name}):
		frappe.throw(
			_("A practice named '{0}' already exists. Please choose a different name.").format(practice_name),
			frappe.ValidationError,
		)


def _trigger_signup(email: str, full_name: str, redirect_to: str) -> None:
	"""Delegates to Frappe's built-in sign_up which sends the verification email."""
	from frappe.core.doctype.user.user import sign_up
	code, message = sign_up(email=email, full_name=full_name, redirect_to=redirect_to)
	# code 0 = already exists (handled by _validate_registration above)
	# code 1 = email sent, code 2 = awaiting admin approval
	if code == 0:
		frappe.throw(_("An account with this email already exists."), frappe.ValidationError)


def _provision_doctor_from_request(req, user_doc) -> None:
	from medic_plus.api._provisioning import provision_doctor
	# Add roles to the already-created User
	user_doc.add_roles("Practice Doctor", "Practice Admin")
	provision_doctor(
		full_name=req.full_name,
		email=req.email,
		mobile=user_doc.mobile_no or "",
		hpcsa_number=req.hpcsa_number or "",
		practice_number=req.practice_number or "",
		practice_name=req.practice_name,
		is_dispensing_doctor=bool(req.is_dispensing_doctor),
	)


def _provision_patient_from_request(req, user_doc) -> None:
	from medic_plus.api._provisioning import provision_patient
	user_doc.add_roles("Patient")
	provision_patient(
		full_name=req.full_name,
		email=req.email,
		mobile=user_doc.mobile_no or "",
		date_of_birth=req.date_of_birth,
		preferred_practice=req.preferred_practice,
	)
