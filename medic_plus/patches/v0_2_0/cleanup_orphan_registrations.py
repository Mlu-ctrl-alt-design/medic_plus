"""Delete orphan Users from the legacy `Registration Request` flow.

An orphan is a User whose email matches a `Registration Request` row and
has no corresponding `Practice Member` record. System Users are never
deleted automatically — they are logged for manual review.

Runs once. Idempotent (the Registration Request DocType itself is dropped
by a subsequent patch, so this patch has nothing to do on re-run).
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Registration Request"):
		return  # DocType already dropped — nothing to clean

	rows = frappe.get_all(
		"Registration Request",
		fields=["name", "email"],
	)
	deleted = []
	skipped = []

	for row in rows:
		email = (row.email or "").strip().lower()
		if not email:
			continue
		if not frappe.db.exists("User", email):
			continue
		if frappe.db.exists("Practice Member", {"email": email}):
			# This User already has a practice attached — leave them alone.
			continue
		user_type = frappe.db.get_value("User", email, "user_type")
		if user_type == "System User":
			skipped.append(email)
			continue
		try:
			frappe.delete_doc("User", email, force=1, ignore_permissions=True)
			deleted.append(email)
		except Exception as exc:
			frappe.log_error(
				title=f"orphan cleanup: could not delete User {email}",
				message=str(exc),
			)

	# Delete the Registration Request rows regardless.
	for row in rows:
		try:
			frappe.delete_doc("Registration Request", row.name, force=1, ignore_permissions=True)
		except Exception as exc:
			frappe.log_error(
				title=f"orphan cleanup: could not delete Registration Request {row.name}",
				message=str(exc),
			)

	frappe.db.commit()

	if deleted or skipped:
		frappe.log_error(
			title="Orphan Registration cleanup complete",
			message=(
				f"Deleted Users ({len(deleted)}): {deleted}\n"
				f"Skipped System Users ({len(skipped)}) — review manually: {skipped}"
			),
		)
