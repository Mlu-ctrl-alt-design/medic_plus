import frappe


def _get_user_practice() -> str | None:
	return frappe.db.get_value(
		"Practice Member", {"user": frappe.session.user}, "practice"
	)


def set_practice_on_insert(doc, method=None):
	"""Auto-set custom_practice on Healthcare DocTypes before insert."""
	if not doc.get("custom_practice"):
		practice = _get_user_practice()
		if practice:
			doc.custom_practice = practice
