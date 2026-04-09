"""
Bulk invitation endpoint for Practice Members.

POST /api/method/medic_plus.api.invitation.bulk_invite
Body: {"members": [...]}
"""

import frappe
from frappe import _
from frappe.utils import cint


@frappe.whitelist()
def bulk_invite(members):
	"""
	Accept a JSON list of member dicts and create a Practice Member for each.

	Each dict must have: full_name, email, role, practice.
	Optional: mobile_number, practitioner (required when role == 'Doctor').

	Returns a list of results: {email, status, name, error}.
	"""
	if isinstance(members, str):
		import json
		members = json.loads(members)

	if not isinstance(members, list):
		frappe.throw(_("members must be a list."))

	caller = frappe.session.user
	allowed_roles = {"Healthcare Administrator", "Practice Admin", "Practice Doctor"}
	if not allowed_roles.intersection(set(frappe.get_roles(caller))):
		frappe.throw(_("Not permitted to invite members."), frappe.PermissionError)

	results = []
	for entry in members:
		try:
			_validate_entry(entry)
			doc = frappe.get_doc({
				"doctype": "Practice Member",
				"practice": entry["practice"],
				"full_name": entry["full_name"],
				"email": entry["email"],
				"mobile_number": entry.get("mobile_number", ""),
				"role": entry["role"],
				"practitioner": entry.get("practitioner", ""),
				"status": "Pending",
			})
			doc.insert(ignore_permissions=False)
			results.append({"email": entry["email"], "status": "invited", "name": doc.name})
		except Exception as exc:
			results.append({"email": entry.get("email", ""), "status": "error", "error": str(exc)})

	return results


def _validate_entry(entry: dict) -> None:
	required = ["practice", "full_name", "email", "role"]
	missing = [f for f in required if not entry.get(f)]
	if missing:
		frappe.throw(_("Missing required fields: {0}").format(", ".join(missing)))

	valid_roles = {"Admin", "Doctor", "Receptionist", "Patient"}
	if entry["role"] not in valid_roles:
		frappe.throw(_("Invalid role: {0}").format(entry["role"]))

	if entry["role"] == "Doctor" and not entry.get("practitioner"):
		frappe.throw(_("practitioner is required when role is Doctor."))
