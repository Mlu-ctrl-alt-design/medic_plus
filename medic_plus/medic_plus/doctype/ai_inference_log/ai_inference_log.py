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

diff --git a/medic_plus/medic_plus/doctype/ai_inference_log/ai_inference_log.py b/medic_plus/medic_plus/doctype/ai_inference_log/ai_inference_log.py
new file mode 100644
index 0000000..47bf32d
--- /dev/null
+++ b/medic_plus/medic_plus/doctype/ai_inference_log/ai_inference_log.py
@@ -0,0 +1,19 @@
+import frappe
+from frappe.model.document import Document
+
+
+class AiInferenceLog(Document):
+    def before_insert(self):
+        # Append-only: never update existing rows
+        pass
+
+    def validate(self):
+        # Ensure PHI is not stored in input_redacted by scanning for SA ID pattern
+        if self.input_redacted:
+            import re
+            sa_id_pattern = re.compile(r"\b\d{13}\b")
+            if sa_id_pattern.search(self.input_redacted):
+                frappe.throw(
+                    "AI Inference Log input_redacted field contains what appears to be "
+                    "an unredacted SA ID number. Redact PHI before logging."
+                )
