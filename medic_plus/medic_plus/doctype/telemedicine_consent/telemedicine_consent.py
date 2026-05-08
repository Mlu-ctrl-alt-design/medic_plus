import frappe
from frappe.model.document import Document
from frappe.utils import add_years, today

CONSENT_TEXT = """TELEMEDICINE INFORMED CONSENT

In accordance with the Health Professions Council of South Africa (HPCSA)
Booklet 10 — Guidelines on the Use of Telemedicine in Health Care, I, the patient,
consent to:

1. Receiving healthcare services via telemedicine (video consultation).
2. The recording, storage, and processing of consultation data required for
   my clinical record.
3. Understanding that telemedicine consultations are subject to the same
   confidentiality obligations as in-person consultations under the
   National Health Act 61 of 2003 and POPIA.
4. Understanding that I may withdraw this consent at any time.

This consent is valid for 12 months from the date of signing. I will be
re-prompted for consent upon expiry.
"""


class TelemedicineConsent(Document):
    def before_insert(self):
        if not self.consent_text:
            self.consent_text = CONSENT_TEXT
        self.expiry_date = add_years(self.consent_date or today(), 1)

    def validate(self):
        if not self.hpcsa_booklet_10_acknowledged:
            frappe.throw(
                "Patient must acknowledge HPCSA Booklet 10 before telemedicine consent can be recorded."
            )
        if self.revoked and not self.revocation_date:
            self.revocation_date = today()
