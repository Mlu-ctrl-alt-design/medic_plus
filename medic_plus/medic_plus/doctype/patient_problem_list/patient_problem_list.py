import frappe
from frappe.model.document import Document


class PatientProblemList(Document):
    def before_insert(self):
        if not self.custom_practice and self.patient:
            self.custom_practice = frappe.db.get_value("Patient", self.patient, "custom_practice")
