import frappe
from frappe.model.document import Document


class ClinicalAccessLog(Document):
    def before_insert(self):
        # Prevent any modifications to existing log entries
        pass

    def before_save(self):
        if not self.is_new():
            frappe.throw(
                "Clinical Access Log entries cannot be modified after creation.",
                frappe.PermissionError,
            )
