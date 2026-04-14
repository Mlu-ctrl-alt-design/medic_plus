"""
Doctor onboarding API.

Two entry points:
  1. submit_registration_request — public, creates a pending request for admin review
  2. onboard_doctor              — internal/admin, provisions the full tenant

Provisioning path: Practice → User → Practice Member → (Warehouse if dispensing)
Wrapped in a transaction — any failure rolls back all inserts.
"""

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
# Public self-registration
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def submit_registration_request(
	practice_name: str,
	full_name: str,
	email: str,
	mobile: str,
	hpcsa_number: str,
	practice_number: str = "",
	is_dispensing_doctor: bool = False,
) -> dict:
	"""Submit a practice registration request for admin review.

	Guest-accessible. Does NOT provision anything — a Healthcare Administrator
	must approve the request before the practice is created.

	Returns:
		dict with the request name and a confirmation message.

	Raises:
		frappe.ValidationError: If a pending/approved request or user already exists.
	"""
	email = email.strip().lower()

	if frappe.db.exists("User", email):
		frappe.throw(_("An account with this email already exists."), frappe.ValidationError)

	duplicate = frappe.db.exists(
		"Practice Registration Request",
		{"email": email, "status": ["in", ["Pending", "Approved"]]},
	)
	if duplicate:
		frappe.throw(
			_("A registration request for {0} is already pending or approved.").format(email),
			frappe.ValidationError,
		)

	doc = frappe.get_doc({
		"doctype": "Practice Registration Request",
		"practice_name": practice_name.strip(),
		"full_name": full_name.strip(),
		"email": email,
		"mobile": mobile.strip(),
		"hpcsa_number": hpcsa_number.strip(),
		"practice_number": (practice_number or "").strip(),
		"is_dispensing_doctor": frappe.utils.cint(is_dispensing_doctor),
		"status": "Pending",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	_notify_admins_of_new_request(doc)

	return {
		"name": doc.name,
		"message": _("Registration submitted. You will receive login details once approved."),
	}


def _notify_admins_of_new_request(doc) -> None:
	"""Email Healthcare Administrators about a new registration request."""
	admin_users = frappe.get_all(
		"Has Role",
		filters={"role": "Healthcare Administrator", "parenttype": "User"},
		pluck="parent",
	)
	recipients = [u for u in admin_users if frappe.db.get_value("User", u, "enabled")]
	if not recipients:
		return

	frappe.sendmail(
		recipients=recipients,
		subject=f"[Medic Plus] New Registration: {doc.practice_name}",
		message=f"""
		<p>A new practice registration request has been submitted and is awaiting your review.</p>
		<table style="border-collapse:collapse;font-size:14px;">
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">Practice</td><td><strong>{doc.practice_name}</strong></td></tr>
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">Doctor</td><td>{doc.full_name}</td></tr>
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">Email</td><td>{doc.email}</td></tr>
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">HPCSA</td><td>{doc.hpcsa_number}</td></tr>
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">Dispensing</td><td>{"Yes" if doc.is_dispensing_doctor else "No"}</td></tr>
		</table>
		<p style="margin-top:16px;">
		  <a href="/app/practice-registration-request/{doc.name}"
		     style="background:#2563eb;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none;">
		    Review Request
		  </a>
		</p>
		""",
		now=False,
	)


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
