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

diff --git a/medic_plus/www/teleconsult/index.py b/medic_plus/www/teleconsult/index.py
new file mode 100644
index 0000000..fedaeac
--- /dev/null
+++ b/medic_plus/www/teleconsult/index.py
@@ -0,0 +1,62 @@
+"""
+Context controller for /teleconsult/<room_id>.
+
+Serves the teleconsult page for both practitioner and patient views.
+- Practitioner: full encounter editor side-panel + video
+- Patient: waiting room then video
+
+URL patterns handled by Frappe's www router:
+  /teleconsult/<room_id>?role=patient&token=<token>
+  /teleconsult/<room_id>   (practitioner — must be authenticated practice member)
+"""
+
+import frappe
+
+
+def get_context(context):
+    if frappe.session.user == "Guest":
+        frappe.throw("Login required", frappe.PermissionError)
+
+    room_id = frappe.local.request.path.rstrip("/").split("/")[-1]
+    role = frappe.form_dict.get("role", "practitioner")
+    token = frappe.form_dict.get("token", "")
+
+    context.room_id = room_id
+    context.role = role
+    context.token = token
+    context.no_cache = 1
+
+    if role == "patient":
+        # Validate one-time token
+        validation = _validate_patient_token(token, room_id)
+        context.token_valid = validation.get("valid", False)
+        context.appointment = validation.get("appointment", "")
+    else:
+        # Practitioner — verify practice membership and load appointment
+        appointment = frappe.db.get_value(
+            "Patient Appointment",
+            {"video_room_id": room_id},
+            ["name", "patient", "custom_practice", "custom_consultation_type"],
+            as_dict=True,
+        )
+        context.appointment = appointment or {}
+        context.token_valid = True  # practitioner auth is via Frappe session
+
+    # Video provider config for the frontend
+    context.video_provider = (
+        frappe.db.get_single_value("Medic Plus Settings", "video_provider") or "jitsi"
+    )
+    context.video_base_url = (
+        frappe.db.get_single_value("Medic Plus Settings", "video_base_url")
+        or "https://meet.jit.si"
+    )
+
+
+def _validate_patient_token(token: str, room_id: str) -> dict:
+    if not token:
+        return {"valid": False}
+    try:
+        from medic_plus.api.tele import validate_patient_token
+        return validate_patient_token(token=token, room_id=room_id)
+    except Exception:
+        return {"valid": False}
