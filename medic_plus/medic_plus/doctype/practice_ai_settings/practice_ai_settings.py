import frappe
from frappe.model.document import Document


class PracticeAISettings(Document):
    def validate(self):
        if self.monthly_spend_cap_usd and self.monthly_spend_cap_usd < 0:
            frappe.throw("Monthly spend cap must be 0 (no cap) or a positive value.")
