"""Release notes feed for the Daystar Health SPA.

Published `Release Note` records are surfaced to each user once, via a modal
on their next login. "Seen" state is tracked server-side per user on the
`User.custom_release_notes_seen_at` Datetime field, so a dismissal sticks
across devices and browsers.
"""

import frappe
from frappe.utils import now

SEEN_FIELD = "custom_release_notes_seen_at"


@frappe.whitelist()
def get_unseen_release_notes() -> list[dict]:
	"""Return published release notes the current user has not yet acknowledged.

	On a user's very first call (no seen timestamp) we record "caught up as of
	now" and return nothing — new users are not shown the full historical
	changelog. From then on, only notes created after their last dismissal
	appear.
	"""
	user = frappe.session.user
	if user == "Guest":
		return []

	seen_at = frappe.db.get_value("User", user, SEEN_FIELD)
	if not seen_at:
		frappe.db.set_value("User", user, SEEN_FIELD, now())
		return []

	return frappe.get_all(
		"Release Note",
		filters={"is_published": 1, "creation": [">", seen_at]},
		fields=["name", "title", "version", "body", "published_on"],
		order_by="published_on asc, creation asc",
	)


@frappe.whitelist()
def mark_release_notes_seen() -> None:
	"""Acknowledge all currently-published release notes for the current user."""
	user = frappe.session.user
	if user == "Guest":
		return
	frappe.db.set_value("User", user, SEEN_FIELD, now())
