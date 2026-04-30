import frappe
from frappe.model.document import Document


class PatientChronicCondition(Document):
	def before_insert(self):
		if not self.custom_practice and self.patient:
			self.custom_practice = frappe.db.get_value("Patient", self.patient, "custom_practice")

	def validate(self):
		if self.patient:
			actual = frappe.db.get_value("Patient", self.patient, "custom_practice")
			if actual and actual != self.custom_practice:
				self.custom_practice = actual
