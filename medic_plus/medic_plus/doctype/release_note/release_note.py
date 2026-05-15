"""Release Note controller.

A platform-authored changelog entry. Published notes are surfaced to users
of the Daystar Health SPA via a one-time modal on their next login — see
medic_plus/api/release_notes.py for the seen-tracking logic.
"""

import frappe
from frappe.model.document import Document


class ReleaseNote(Document):
	def validate(self):
		if not self.published_on:
			self.published_on = frappe.utils.today()
