commit 37fa176116ca31a1f06fc7efb1da7b8d0bbc73b6
Author: Claude <noreply@anthropic.com>
Date:   Sat May 2 09:08:09 2026 +0000

    feat(phase4): telemedicine + AI augmentation — doctypes, gateway, PHI redactor
    
    New doctypes:
    - Practice AI Settings (per-practice AI toggles, monthly spend cap, auto-disable)
    - AI Inference Log (append-only audit trail with PHI-redacted input, practitioner_action)
    - Telemedicine Consent (per-patient, 12-month validity, HPCSA Booklet 10 text)
    
    New custom fields on Patient Appointment:
    - custom_consultation_type (In-Person / Telemedicine / Phone)
    - custom_video_room_id, custom_video_join_url, custom_patient_join_url (one-time token)
    
    New custom field on Patient:
    - custom_ai_consent (gates all AI calls regardless of practice settings)
    
    New API modules:
    - medic_plus.api.ai — AI gateway wrapping Anthropic SDK with prompt caching,
      PHI redactor (SA ID / name / DOB / address / contact → deterministic tokens),
      generate_soap_note (Whisper→SOAP), suggest_ddx (top-3 ICD-10), rx_sanity_check
    - medic_plus.api.tele — Jitsi/LiveKit room provisioning, one-time patient token
    
    New page: /teleconsult/<room_id> (practitioner encounter editor + video side-panel)
    
    PQCs added for Practice AI Settings, AI Inference Log, Telemedicine Consent.
    Medic Plus Settings extended with Anthropic/OpenAI API keys + video provider config.
    
    TDD: test_ai.py (12 cases, PHI corpus fuzz, mocked Anthropic transport),
         test_tele.py (6 cases), test_telemedicine_ai.py (9 Playwright UI cases).
    
    https://claude.ai/code/session_011r2Lf5ZmGirdHMLwpYrvAT

diff --git a/medic_plus/medic_plus/doctype/telemedicine_consent/telemedicine_consent.py b/medic_plus/medic_plus/doctype/telemedicine_consent/telemedicine_consent.py
new file mode 100644
index 0000000..3360900
--- /dev/null
+++ b/medic_plus/medic_plus/doctype/telemedicine_consent/telemedicine_consent.py
@@ -0,0 +1,36 @@
+import frappe
+from frappe.model.document import Document
+from frappe.utils import add_years, today
+
+CONSENT_TEXT = """TELEMEDICINE INFORMED CONSENT
+
+In accordance with the Health Professions Council of South Africa (HPCSA)
+Booklet 10 — Guidelines on the Use of Telemedicine in Health Care, I, the patient,
+consent to:
+
+1. Receiving healthcare services via telemedicine (video consultation).
+2. The recording, storage, and processing of consultation data required for
+   my clinical record.
+3. Understanding that telemedicine consultations are subject to the same
+   confidentiality obligations as in-person consultations under the
+   National Health Act 61 of 2003 and POPIA.
+4. Understanding that I may withdraw this consent at any time.
+
+This consent is valid for 12 months from the date of signing. I will be
+re-prompted for consent upon expiry.
+"""
+
+
+class TelemedicineConsent(Document):
+    def before_insert(self):
+        if not self.consent_text:
+            self.consent_text = CONSENT_TEXT
+        self.expiry_date = add_years(self.consent_date or today(), 1)
+
+    def validate(self):
+        if not self.hpcsa_booklet_10_acknowledged:
+            frappe.throw(
+                "Patient must acknowledge HPCSA Booklet 10 before telemedicine consent can be recorded."
+            )
+        if self.revoked and not self.revocation_date:
+            self.revocation_date = today()
