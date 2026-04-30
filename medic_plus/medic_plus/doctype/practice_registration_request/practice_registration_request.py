import frappe
from frappe.model.document import Document

from medic_plus.api.validators import (
	validate_hpcsa_number,
	validate_practice_number,
	validate_sa_mobile,
)


class PracticeRegistrationRequest(Document):
	def before_insert(self):
		if not self.submitted_at:
			self.submitted_at = frappe.utils.now()
		if self.email:
			self.email = self.email.strip().lower()

	def validate(self):
		if self.email:
			self.email = self.email.strip().lower()
		if self.mobile:
			self.mobile = validate_sa_mobile(self.mobile)
		if self.hpcsa_number:
			self.hpcsa_number = validate_hpcsa_number(self.hpcsa_number)
		if self.practice_number:
			self.practice_number = validate_practice_number(self.practice_number)
