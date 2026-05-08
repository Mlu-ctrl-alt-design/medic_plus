import frappe
from frappe.model.document import Document


class AiInferenceLog(Document):
    def before_insert(self):
        # Append-only: never update existing rows
        pass

    def validate(self):
        # Ensure PHI is not stored in input_redacted by scanning for SA ID pattern
        if self.input_redacted:
            import re
            sa_id_pattern = re.compile(r"\b\d{13}\b")
            if sa_id_pattern.search(self.input_redacted):
                frappe.throw(
                    "AI Inference Log input_redacted field contains what appears to be "
                    "an unredacted SA ID number. Redact PHI before logging."
                )
