"""Practice owner invites staff into their tenant.

Single whitelisted endpoint that creates a User (with Frappe's standard
welcome+set-password email), assigns the appropriate role, links the user
to the practice via Practice Member, and — for Doctor invites — also
provisions a Healthcare Practitioner row pre-scoped to the practice.

Authorization: caller must be a Practice Admin of the target practice
(or a System Manager / Healthcare Administrator for ops support).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from medic_plus.api.validators import validate_sa_mobile

# Practice Member.role enum → Frappe role name applied to the User
_ROLE_MAP = {
	"Admin": "Practice Admin",
	"Doctor": "Practice Doctor",
	"Receptionist": "Practice Receptionist",
}


def _caller_can_invite(practice: str) -> bool:
	if "System Manager" in frappe.get_roles() or "Healthcare Administrator" in frappe.get_roles():
		return True
	# Caller must be a Practice Admin of the same practice.
	return bool(
		frappe.db.exists(
			"Practice Member",
			{"practice": practice, "user": frappe.session.user, "role": "Admin"},
		)
	)


@frappe.whitelist()
@rate_limit(limit=30, seconds=3600)
def invite_staff(
	practice: str,
	email: str,
	full_name: str,
	role: str,
	mobile: str | None = None,
	hpcsa_number: str | None = None,
	practice_number: str | None = None,
) -> dict:
	"""Invite a staff member into a practice.

	Args:
		practice: Practice docname.
		email: Invitee email (becomes the User name).
		full_name: Display name.
		role: One of "Admin", "Doctor", "Receptionist".
		mobile: Optional SA mobile (validated if supplied).
		hpcsa_number / practice_number: Required when role == "Doctor".

	Returns: dict with the created user, practice member name, and (for
	doctors) the practitioner name.
	"""
	practice = (practice or "").strip()
	email = (email or "").strip().lower()
	full_name = (full_name or "").strip()
	role = (role or "").strip()

	if not practice or not frappe.db.exists("Practice", practice):
		frappe.throw(_("Unknown practice."), frappe.ValidationError)
	if not email or "@" not in email:
		frappe.throw(_("A valid email is required."), frappe.ValidationError)
	if not full_name:
		frappe.throw(_("Full name is required."), frappe.ValidationError)
	if role not in _ROLE_MAP:
		frappe.throw(
			_("Role must be one of: {0}").format(", ".join(_ROLE_MAP.keys())),
			frappe.ValidationError,
		)

	if not _caller_can_invite(practice):
		frappe.throw(
			_("You don't have permission to invite staff into this practice."),
			frappe.PermissionError,
		)

	if mobile:
		mobile = validate_sa_mobile(mobile)

	if frappe.db.exists("Practice Member", {"practice": practice, "user": email}):
		frappe.throw(
			_("{0} is already a member of this practice.").format(email),
			frappe.ValidationError,
		)

	frappe_role = _ROLE_MAP[role]
	practitioner_name: str | None = None

	try:
		# Re-use the existing User if one happens to share this email; else
		# create a new one. Frappe's send_welcome_email triggers the
		# password-setup link automatically.
		if frappe.db.exists("User", email):
			user_doc = frappe.get_doc("User", email)
			existing_roles = {r.role for r in (user_doc.roles or [])}
			if frappe_role not in existing_roles:
				user_doc.append("roles", {"role": frappe_role})
				user_doc.save(ignore_permissions=True)
		else:
			parts = full_name.split()
			first = parts[0]
			last = " ".join(parts[1:]) if len(parts) > 1 else ""
			user_doc = frappe.get_doc({
				"doctype": "User",
				"email": email,
				"first_name": first,
				"last_name": last,
				"mobile_no": mobile or "",
				"send_welcome_email": 1,
				"roles": [{"role": frappe_role}],
			})
			user_doc.insert(ignore_permissions=True)

		# Practitioner only for Doctor invites; receptionists/admins don't
		# need a Healthcare Practitioner record.
		if role == "Doctor":
			if not (hpcsa_number and practice_number):
				frappe.throw(
					_("HPCSA number and practice number are required for doctor invites."),
					frappe.ValidationError,
				)
			from medic_plus.api._provisioning import create_practitioner
			practitioner = create_practitioner(
				full_name=full_name,
				email=email,
				hpcsa_number=hpcsa_number,
				practice_number=practice_number,
			)
			practitioner_name = practitioner.name

		from medic_plus.api._provisioning import create_practice_member
		member = create_practice_member(
			practice=practice,
			user=email,
			practitioner=practitioner_name,
			role=role,
			full_name=full_name,
			email=email,
		)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		raise

	return {
		"user": user_doc.name,
		"practice_member": member.name,
		"practitioner": practitioner_name,
		"message": _("Invited {0} to {1}. They've been emailed a set-password link.").format(
			full_name, practice
		),
	}
