import frappe
from frappe.model.document import Document


class PracticeRegistrationRequest(Document):
	def before_insert(self):
		if not self.submitted_at:
			self.submitted_at = frappe.utils.now()
		if self.email:
			self.email = self.email.strip().lower()

	def validate(self):
		if self.email:
			self.email = self.email.strip().lower()
