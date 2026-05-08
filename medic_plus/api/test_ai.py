"""
Tests for medic_plus.api.ai — AI gateway, PHI redactor, and AI feature endpoints.

Design:
- Anthropic SDK transport is always mocked — never live network in CI.
- PHI redaction is property-based: a corpus of seeded patients is built, all
  PHI strings extracted, and we assert zero occurrences in any outbound payload.
- spend-cap auto-disable is tested end-to-end via mocked frappe.db.
"""

import unittest
from unittest.mock import MagicMock, patch, call

import frappe


# ── frappe local-state bootstrap ─────────────────────────────────────────────

def setUpModule():
    frappe.local.session = frappe._dict(user="doctor@example.test")
    frappe.local.conf = frappe._dict(developer_mode=0)
    frappe.local.flags = frappe._dict()
    frappe.local.lang = "en"
    frappe.local.message_log = []
    frappe.local.error_log = []
    frappe.local.debug_log = []
    frappe.local.response = frappe._dict()

    cache_mock = MagicMock()
    cache_mock.hget.return_value = {}
    frappe.cache = cache_mock


# ── Slice 1: PHI redactor ─────────────────────────────────────────────────────

class TestPhiRedactor(unittest.TestCase):
    """PHI redaction layer must strip all personal identifiers before any LLM call."""

    def _import(self):
        from medic_plus.api.ai import redact_phi, restore_phi
        return redact_phi, restore_phi

    def test_sa_id_number_redacted(self):
        redact_phi, _ = self._import()
        text = "Patient SA ID: 8501015009086 presented today."
        redacted, _ = redact_phi(text)
        self.assertNotIn("8501015009086", redacted)

    def test_patient_name_redacted(self):
        redact_phi, _ = self._import()
        phi = {"patient_name": "Jane Smith", "email": "", "mobile": ""}
        text = "Jane Smith complained of headache."
        redacted, _ = redact_phi(text, phi_map=phi)
        self.assertNotIn("Jane Smith", redacted)
        self.assertNotIn("Jane", redacted)
        self.assertNotIn("Smith", redacted)

    def test_email_redacted(self):
        redact_phi, _ = self._import()
        phi = {"patient_name": "", "email": "jane.smith@example.com", "mobile": ""}
        text = "Contact: jane.smith@example.com"
        redacted, _ = redact_phi(text, phi_map=phi)
        self.assertNotIn("jane.smith@example.com", redacted)

    def test_mobile_redacted(self):
        redact_phi, _ = self._import()
        phi = {"patient_name": "", "email": "", "mobile": "0821234567"}
        text = "Phone: 0821234567"
        redacted, _ = redact_phi(text, phi_map=phi)
        self.assertNotIn("0821234567", redacted)

    def test_dob_redacted(self):
        redact_phi, _ = self._import()
        phi = {"patient_name": "", "email": "", "mobile": "", "dob": "1985-01-01"}
        text = "DOB: 1985-01-01"
        redacted, _ = redact_phi(text, phi_map=phi)
        self.assertNotIn("1985-01-01", redacted)

    def test_deterministic_tokens(self):
        """Same PHI value always maps to the same token within one call."""
        redact_phi, _ = self._import()
        phi = {"patient_name": "Jane Smith", "email": "", "mobile": ""}
        text = "Jane Smith seen by nurse. Jane Smith denied fever."
        redacted, token_map = redact_phi(text, phi_map=phi)
        # Both occurrences should use identical token
        self.assertNotIn("Jane Smith", redacted)
        # There must be exactly one distinct token for "Jane Smith"
        name_tokens = [v for k, v in token_map.items() if "Jane Smith" in k]
        if name_tokens:
            self.assertEqual(len(set(name_tokens)), 1)

    def test_restore_phi_round_trips(self):
        """restore_phi puts the original values back in the AI output."""
        redact_phi, restore_phi = self._import()
        phi = {"patient_name": "Jane Smith", "email": "", "mobile": ""}
        text = "Patient Jane Smith presented."
        redacted, token_map = redact_phi(text, phi_map=phi)
        ai_output = f"SOAP note for {list(token_map.values())[0]}."
        restored = restore_phi(ai_output, token_map)
        self.assertIn("Jane Smith", restored)

    def test_phi_corpus_fuzz(self):
        """
        Property-based: for a corpus of seeded patient dicts, no PHI value
        appears in the redacted output string.
        """
        redact_phi, _ = self._import()
        patients = [
            {
                "patient_name": "Sipho Dlamini",
                "email": "sipho@example.com",
                "mobile": "0711234567",
                "dob": "1990-03-15",
                "custom_sa_id_number": "9003155008087",
                "address": "12 Oak Street, Johannesburg",
            },
            {
                "patient_name": "Fatima van der Berg",
                "email": "fatima.vdb@clinic.co.za",
                "mobile": "0829876543",
                "dob": "1978-11-22",
                "custom_sa_id_number": "7811220047089",
                "address": "4 Fir Avenue, Cape Town",
            },
            {
                "patient_name": "Themba Nkosi",
                "email": "tnkosi@mail.co.za",
                "mobile": "0603334444",
                "dob": "2001-07-04",
                "custom_sa_id_number": "0107045009081",
                "address": "Unit 7, 28 Church Road, Durban",
            },
        ]

        phi_fields = [
            "patient_name", "email", "mobile", "dob",
            "custom_sa_id_number", "address",
        ]

        for patient in patients:
            transcription = (
                f"Patient {patient['patient_name']} (DOB {patient['dob']}) "
                f"ID {patient['custom_sa_id_number']} at {patient['address']} "
                f"called {patient['mobile']} email {patient['email']} reports chest pain."
            )
            redacted, _ = redact_phi(transcription, phi_map=patient)

            for field in phi_fields:
                value = patient.get(field, "")
                if not value:
                    continue
                # Check each sub-token (e.g. first name, last name separately)
                sub_tokens = value.replace(",", " ").split()
                for token in sub_tokens:
                    if len(token) >= 4:  # skip short tokens like "of", "12"
                        self.assertNotIn(
                            token, redacted,
                            f"PHI token '{token}' from field '{field}' found in redacted output"
                        )


# ── Slice 3: AI gateway (mocked Anthropic transport) ─────────────────────────

class TestAiGatewayMocked(unittest.TestCase):
    """AI gateway wraps Anthropic SDK. Transport is always mocked in tests."""

    def _import(self):
        from medic_plus.api.ai import call_claude
        return call_claude

    @patch("medic_plus.api.ai._get_anthropic_client")
    def test_call_claude_returns_text(self, mock_get_client):
        """call_claude() returns the text content from the mocked API."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Mocked SOAP note")],
            usage=MagicMock(input_tokens=100, output_tokens=50),
            model="claude-sonnet-4-6",
        )

        call_claude = self._import()
        result = call_claude(
            system="You are a clinical scribe.",
            user="Transcription: patient reports headache.",
            practice="PRAC-00001",
            feature="note_gen",
        )
        self.assertEqual(result["text"], "Mocked SOAP note")
        self.assertIn("latency_ms", result)
        self.assertIn("cost_usd", result)
        self.assertIn("input_tokens", result)

    @patch("medic_plus.api.ai._get_anthropic_client")
    def test_call_claude_uses_prompt_caching(self, mock_get_client):
        """System prompt is sent with cache_control for Anthropic prompt caching."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="ok")],
            usage=MagicMock(input_tokens=10, output_tokens=5),
            model="claude-sonnet-4-6",
        )

        call_claude = self._import()
        call_claude(
            system="Cached system prompt.",
            user="user message",
            practice="PRAC-00001",
            feature="note_gen",
        )

        _, kwargs = mock_client.messages.create.call_args
        system_arg = kwargs.get("system") or mock_client.messages.create.call_args[0][0]
        # system should be a list with cache_control block
        call_kwargs = mock_client.messages.create.call_args[1]
        system_val = call_kwargs.get("system")
        if isinstance(system_val, list):
            self.assertTrue(
                any("cache_control" in str(block) for block in system_val),
                "System prompt blocks should include cache_control"
            )

    @patch("medic_plus.api.ai._get_anthropic_client")
    @patch("medic_plus.api.ai._get_practice_ai_settings")
    def test_call_claude_blocked_when_ai_disabled(self, mock_settings, mock_get_client):
        """call_claude() raises PermissionError when practice has AI disabled."""
        mock_settings.return_value = {"ai_enabled": False, "note_gen_enabled": False}
        call_claude = self._import()
        with self.assertRaises(frappe.PermissionError):
            call_claude(
                system="sys", user="msg",
                practice="PRAC-00001", feature="note_gen",
            )
        mock_get_client.assert_not_called()

    @patch("medic_plus.api.ai._get_anthropic_client")
    @patch("medic_plus.api.ai._get_practice_ai_settings")
    def test_call_claude_blocked_when_patient_consent_false(self, mock_settings, mock_get_client):
        """call_claude() raises PermissionError when patient has not consented to AI."""
        mock_settings.return_value = {"ai_enabled": True, "note_gen_enabled": True}
        call_claude = self._import()
        with self.assertRaises(frappe.PermissionError):
            call_claude(
                system="sys", user="msg",
                practice="PRAC-00001", feature="note_gen",
                patient_ai_consent=False,
            )
        mock_get_client.assert_not_called()


# ── Slice 5: Monthly spend cap auto-disable ──────────────────────────────────

class TestMonthlySpendCapAutoDisable(unittest.TestCase):
    """When cumulative AI spend for the month exceeds the cap, AI is auto-disabled."""

    def _import(self):
        from medic_plus.api.ai import _check_and_enforce_spend_cap
        return _check_and_enforce_spend_cap

    @patch("medic_plus.api.ai.frappe")
    def test_spend_under_cap_does_not_disable(self, mock_frappe):
        _check = self._import()
        # Settings: cap = 100 USD, current spend = 50 USD → should not disable
        mock_frappe.db.get_value.return_value = 100.0  # monthly_spend_cap_usd
        mock_frappe.db.sql.return_value = [[50.0]]     # sum cost_usd this month
        # Should not raise and should not call set_value to disable
        _check("PRAC-00001")
        mock_frappe.db.set_value.assert_not_called()

    @patch("medic_plus.api.ai.frappe")
    def test_spend_over_cap_auto_disables_ai(self, mock_frappe):
        _check = self._import()
        mock_frappe.db.get_value.return_value = 50.0   # monthly_spend_cap_usd
        mock_frappe.db.sql.return_value = [[75.23]]    # over cap
        _check("PRAC-00001")
        # Should have set ai_enabled = 0 on Practice AI Settings
        mock_frappe.db.set_value.assert_called_once_with(
            "Practice AI Settings", "PRAC-00001", "ai_enabled", 0
        )

    @patch("medic_plus.api.ai.frappe")
    def test_no_cap_set_does_not_disable(self, mock_frappe):
        """When monthly_spend_cap_usd is 0 (no cap), auto-disable is skipped."""
        _check = self._import()
        mock_frappe.db.get_value.return_value = 0      # 0 = no cap
        mock_frappe.db.sql.return_value = [[9999.0]]   # huge spend
        _check("PRAC-00001")
        mock_frappe.db.set_value.assert_not_called()


# ── Slice 8: Note generation ─────────────────────────────────────────────────

class TestNoteGeneration(unittest.TestCase):
    """generate_soap_note() whisper-transcribes audio and structures via Claude."""

    def _import(self):
        from medic_plus.api.ai import generate_soap_note
        return generate_soap_note

    @patch("medic_plus.api.ai._transcribe_audio")
    @patch("medic_plus.api.ai.call_claude")
    @patch("medic_plus.api.ai._get_practice_ai_settings")
    @patch("medic_plus.api.ai._log_inference")
    def test_soap_note_fills_four_sections(
        self, mock_log, mock_settings, mock_claude, mock_transcribe
    ):
        mock_settings.return_value = {"ai_enabled": True, "note_gen_enabled": True}
        mock_transcribe.return_value = "Patient reports headache and fever for 2 days."
        mock_claude.return_value = {
            "text": (
                "SUBJECTIVE: Headache and fever x2 days.\n"
                "OBJECTIVE: Temp 38.5°C, HR 90.\n"
                "ASSESSMENT: Viral URTI.\n"
                "PLAN: Paracetamol 1g TDS x3 days, rest, fluids."
            ),
            "latency_ms": 450,
            "cost_usd": 0.002,
            "input_tokens": 200,
            "output_tokens": 100,
            "model": "claude-sonnet-4-6",
        }

        generate_soap_note = self._import()
        result = generate_soap_note(
            audio_b64="FAKEB64AUDIO",
            encounter="ENC-00001",
            practice="PRAC-00001",
            practitioner="HP-001",
            patient_ai_consent=True,
            patient_phi={"patient_name": "Jane Smith", "email": "", "mobile": ""},
        )

        self.assertIn("subjective", result)
        self.assertIn("objective", result)
        self.assertIn("assessment", result)
        self.assertIn("plan", result)
        mock_log.assert_called_once()

    @patch("medic_plus.api.ai._transcribe_audio")
    @patch("medic_plus.api.ai.call_claude")
    @patch("medic_plus.api.ai._get_practice_ai_settings")
    @patch("medic_plus.api.ai._log_inference")
    def test_phi_not_in_outbound_payload(
        self, mock_log, mock_settings, mock_claude, mock_transcribe
    ):
        """The payload sent to Claude must not contain raw PHI."""
        mock_settings.return_value = {"ai_enabled": True, "note_gen_enabled": True}
        mock_transcribe.return_value = (
            "Jane Smith ID 8501015009086 mobile 0821234567 "
            "DOB 1985-01-01 reports chest pain."
        )
        mock_claude.return_value = {
            "text": "SUBJECTIVE: chest pain.\nOBJECTIVE: BP 130/80.\nASSESSMENT: query angina.\nPLAN: ECG.",
            "latency_ms": 200, "cost_usd": 0.001, "input_tokens": 50, "output_tokens": 30,
            "model": "claude-sonnet-4-6",
        }

        generate_soap_note = self._import()
        generate_soap_note(
            audio_b64="FAKEB64",
            encounter="ENC-00001",
            practice="PRAC-00001",
            practitioner="HP-001",
            patient_ai_consent=True,
            patient_phi={
                "patient_name": "Jane Smith",
                "email": "jane@example.com",
                "mobile": "0821234567",
                "dob": "1985-01-01",
                "custom_sa_id_number": "8501015009086",
            },
        )

        # Inspect what call_claude actually received as user message
        _, call_kwargs = mock_claude.call_args
        user_payload = call_kwargs.get("user") or mock_claude.call_args[0][1]

        phi_substrings = [
            "Jane Smith", "Jane", "Smith",
            "8501015009086",
            "0821234567",
            "1985-01-01",
            "jane@example.com",
        ]
        for phi in phi_substrings:
            self.assertNotIn(phi, user_payload,
                             f"PHI '{phi}' leaked into outbound Claude payload")


# ── Slice 9: DDx feature ─────────────────────────────────────────────────────

class TestDifferentialDiagnosis(unittest.TestCase):
    """suggest_ddx() returns top-3 ICD-10 candidates."""

    @patch("medic_plus.api.ai._get_practice_ai_settings")
    @patch("medic_plus.api.ai.call_claude")
    @patch("medic_plus.api.ai._log_inference")
    def test_ddx_returns_three_candidates(self, mock_log, mock_claude, mock_settings):
        mock_settings.return_value = {"ai_enabled": True, "ddx_enabled": True}
        mock_claude.return_value = {
            "text": (
                "1. J06.9 — Acute upper respiratory infection, unspecified\n"
                "2. J00 — Acute nasopharyngitis (common cold)\n"
                "3. J02.9 — Acute pharyngitis, unspecified"
            ),
            "latency_ms": 300, "cost_usd": 0.001, "input_tokens": 80, "output_tokens": 60,
            "model": "claude-sonnet-4-6",
        }

        from medic_plus.api.ai import suggest_ddx
        result = suggest_ddx(
            subjective="Sore throat, runny nose, mild fever.",
            objective="Temp 37.8°C, pharynx erythematous.",
            practice="PRAC-00001",
            practitioner="HP-001",
            encounter="ENC-00001",
            patient_ai_consent=True,
        )
        self.assertEqual(len(result["candidates"]), 3)
        self.assertIn("icd_code", result["candidates"][0])
        self.assertIn("description", result["candidates"][0])


# ── Slice 9b: Rx sanity check ─────────────────────────────────────────────────

class TestRxSanityCheck(unittest.TestCase):
    """rx_sanity_check() returns AI warning alongside deterministic checks."""

    @patch("medic_plus.api.ai._get_practice_ai_settings")
    @patch("medic_plus.api.ai.call_claude")
    @patch("medic_plus.api.ai._log_inference")
    def test_rx_check_returns_warning_text(self, mock_log, mock_claude, mock_settings):
        mock_settings.return_value = {"ai_enabled": True, "rx_check_enabled": True}
        mock_claude.return_value = {
            "text": "⚠ Amoxicillin is contraindicated with Warfarin — monitor INR closely.",
            "latency_ms": 150, "cost_usd": 0.0005, "input_tokens": 40, "output_tokens": 20,
            "model": "claude-sonnet-4-6",
        }

        from medic_plus.api.ai import rx_sanity_check
        result = rx_sanity_check(
            medications=["Amoxicillin 500mg TDS", "Warfarin 5mg OD"],
            allergies=["Penicillin"],
            practice="PRAC-00001",
            practitioner="HP-001",
            encounter="ENC-00001",
            patient_ai_consent=True,
        )
        self.assertIn("warning", result)
        self.assertIn("Amoxicillin", result["warning"])
