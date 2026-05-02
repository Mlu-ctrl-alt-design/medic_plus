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

diff --git a/medic_plus/api/test_tele.py b/medic_plus/api/test_tele.py
new file mode 100644
index 0000000..f6019a3
--- /dev/null
+++ b/medic_plus/api/test_tele.py
@@ -0,0 +1,134 @@
+"""
+Tests for medic_plus.api.tele — telemedicine room creation and consent checks.
+All external video-provider API calls are mocked.
+"""
+
+import unittest
+from unittest.mock import MagicMock, patch
+
+import frappe
+
+
+def setUpModule():
+    frappe.local.session = frappe._dict(user="doctor@example.test")
+    frappe.local.conf = frappe._dict(developer_mode=0)
+    frappe.local.flags = frappe._dict()
+    frappe.local.lang = "en"
+    frappe.local.message_log = []
+    frappe.local.error_log = []
+    frappe.local.debug_log = []
+    frappe.local.response = frappe._dict()
+
+    cache_mock = MagicMock()
+    cache_mock.hget.return_value = {}
+    frappe.cache = cache_mock
+
+
+class TestCreateRoom(unittest.TestCase):
+    """create_room() generates a video_room_id and patient_join_url."""
+
+    def _import(self):
+        from medic_plus.api.tele import create_room
+        return create_room
+
+    @patch("medic_plus.api.tele._provision_jitsi_room")
+    @patch("medic_plus.api.tele.frappe")
+    def test_create_room_returns_room_id_and_urls(self, mock_frappe, mock_jitsi):
+        mock_frappe.db.get_single_value.return_value = "jitsi"
+        mock_frappe.generate_hash.return_value = "tok_abc123"
+        mock_frappe.utils.now_datetime.return_value = MagicMock(
+            strftime=lambda fmt: "2026-05-02T10:00:00"
+        )
+        mock_jitsi.return_value = {
+            "room_id": "medic-ROOM123",
+            "practitioner_url": "https://meet.jitsi.example/medic-ROOM123",
+        }
+
+        create_room = self._import()
+        result = create_room(
+            appointment="PA-00001",
+            practice="PRAC-00001",
+            patient="PAT-00001",
+        )
+
+        self.assertIn("room_id", result)
+        self.assertIn("practitioner_url", result)
+        self.assertIn("patient_join_url", result)
+        self.assertIn("patient_token", result)
+        # Token must be one-time (opaque) — not the plain appointment name
+        self.assertNotEqual(result["patient_token"], "PA-00001")
+
+    @patch("medic_plus.api.tele._provision_jitsi_room")
+    @patch("medic_plus.api.tele.frappe")
+    def test_patient_join_url_contains_token(self, mock_frappe, mock_jitsi):
+        mock_frappe.db.get_single_value.return_value = "jitsi"
+        mock_frappe.generate_hash.return_value = "onetimet0k3n"
+        mock_frappe.utils.now_datetime.return_value = MagicMock(
+            strftime=lambda fmt: "2026-05-02T10:00:00"
+        )
+        mock_jitsi.return_value = {
+            "room_id": "medic-ABC",
+            "practitioner_url": "https://meet.jitsi.example/medic-ABC",
+        }
+
+        create_room = self._import()
+        result = create_room(
+            appointment="PA-00001",
+            practice="PRAC-00001",
+            patient="PAT-00001",
+        )
+        self.assertIn("onetimet0k3n", result["patient_join_url"])
+
+
+class TestTelemedicineConsentCheck(unittest.TestCase):
+    """get_or_create_tele_consent() handles 12-month validity + re-prompt."""
+
+    def _import(self):
+        from medic_plus.api.tele import get_tele_consent_status
+        return get_tele_consent_status
+
+    @patch("medic_plus.api.tele.frappe")
+    def test_valid_consent_returns_active(self, mock_frappe):
+        from frappe.utils import add_days, today
+        mock_frappe.utils.today.return_value = today()
+        mock_frappe.db.get_value.return_value = {
+            "name": "TC-00001",
+            "expiry_date": add_days(today(), 30),
+            "revoked": 0,
+        }
+        get_tele_consent_status = self._import()
+        result = get_tele_consent_status(patient="PAT-00001", practice="PRAC-00001")
+        self.assertEqual(result["status"], "active")
+
+    @patch("medic_plus.api.tele.frappe")
+    def test_expired_consent_returns_expired(self, mock_frappe):
+        from frappe.utils import add_days, today
+        mock_frappe.utils.today.return_value = today()
+        mock_frappe.db.get_value.return_value = {
+            "name": "TC-00001",
+            "expiry_date": add_days(today(), -1),
+            "revoked": 0,
+        }
+        get_tele_consent_status = self._import()
+        result = get_tele_consent_status(patient="PAT-00001", practice="PRAC-00001")
+        self.assertEqual(result["status"], "expired")
+
+    @patch("medic_plus.api.tele.frappe")
+    def test_no_consent_returns_required(self, mock_frappe):
+        mock_frappe.db.get_value.return_value = None
+        get_tele_consent_status = self._import()
+        result = get_tele_consent_status(patient="PAT-00001", practice="PRAC-00001")
+        self.assertEqual(result["status"], "required")
+
+    @patch("medic_plus.api.tele.frappe")
+    def test_revoked_consent_returns_revoked(self, mock_frappe):
+        from frappe.utils import add_days, today
+        mock_frappe.utils.today.return_value = today()
+        mock_frappe.db.get_value.return_value = {
+            "name": "TC-00001",
+            "expiry_date": add_days(today(), 30),
+            "revoked": 1,
+        }
+        get_tele_consent_status = self._import()
+        result = get_tele_consent_status(patient="PAT-00001", practice="PRAC-00001")
+        self.assertEqual(result["status"], "revoked")
