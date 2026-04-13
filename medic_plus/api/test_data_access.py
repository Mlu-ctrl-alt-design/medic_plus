"""
Tests for patient data masking and two-sided OTP consent flow.

All external calls (frappe.db, frappe.sendmail, frappe.session) are mocked.
No documents are created in the database.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from medic_plus.api.data_access import (
    _hash_otp,
    _mask,
)


def setUpModule():
    """
    Bind frappe's LocalProxy objects so mock patching works correctly.

    frappe.session, frappe.conf, frappe.db, frappe.lang, and frappe.cache are all
    LocalProxy objects backed by a ContextVar.  In Python 3.14, mock.__enter__
    calls hasattr(original, '__func__') on the original object before creating the
    replacement mock.  If the ContextVar is unset, LocalProxy.__getattr__ raises
    RuntimeError (not AttributeError), which propagates out of hasattr and crashes
    the patch context manager.

    Initializing these attributes here binds the ContextVar so the proxies resolve
    to real objects, making hasattr work as expected.

    Additionally, frappe.throw() → frappe._() → frappe.translate.get_all_translations()
    requires frappe.cache.hget() and a site log directory.  We stub frappe.cache with
    a MagicMock that returns an empty translations dict (pass-through, no translations),
    and set frappe.local.lang = "en" to short-circuit the language detection path.
    """
    frappe.local.session = frappe._dict(user="test@example.test")
    frappe.local.conf = frappe._dict(developer_mode=0)
    frappe.local.flags = frappe._dict()
    frappe.local.lang = "en"
    # frappe.throw() → frappe.msgprint() appends to message_log, error_log, debug_log
    frappe.local.message_log = []
    frappe.local.error_log = []
    frappe.local.debug_log = []
    frappe.local.response = frappe._dict()

    # frappe.cache is a plain module attribute (not a LocalProxy), default None.
    # get_all_translations() calls frappe.cache.hget() — stub it so _("...") passes
    # strings through unchanged without hitting Redis or the log filesystem.
    cache_mock = MagicMock()
    cache_mock.hget.return_value = {}
    frappe.cache = cache_mock


class TestMaskHelpers(unittest.TestCase):
    """Unit tests for mask display helpers."""

    def test_sa_id_masks_all_but_last_four(self):
        self.assertEqual(_mask("9001014800088", "custom_sa_id_number"), "*** *** 0088")

    def test_mobile_masks_all_but_last_three(self):
        result = _mask("0821234567", "mobile")
        self.assertIn("567", result)
        self.assertNotIn("0821234", result)

    def test_membership_number_masks_prefix(self):
        result = _mask("MED123456", "custom_membership_number")
        self.assertTrue(result.endswith("456"))
        self.assertIn("*", result)

    def test_empty_value_returns_dash(self):
        self.assertEqual(_mask(None, "custom_sa_id_number"), "—")
        self.assertEqual(_mask("", "mobile"), "—")

    def test_short_value_does_not_crash(self):
        # value shorter than the slice window
        self.assertIsNotNone(_mask("AB", "custom_sa_id_number"))


class TestOtpHash(unittest.TestCase):
    """OTP hash is deterministic and one-way."""

    def test_same_otp_same_hash(self):
        self.assertEqual(_hash_otp("123456"), _hash_otp("123456"))

    def test_different_otp_different_hash(self):
        self.assertNotEqual(_hash_otp("123456"), _hash_otp("654321"))

    def test_hash_is_64_chars(self):
        self.assertEqual(len(_hash_otp("000000")), 64)  # SHA-256 hex


class TestRequestUnmask(unittest.TestCase):
    """request_unmask() creates a Data Unmask Request and dispatches OTPs."""

    def _make_mock_doc(self, name="DMR-2026-00001"):
        doc = MagicMock()
        doc.name = name
        return doc

    @patch("medic_plus.api.data_access.frappe.has_permission")
    @patch("medic_plus.api.data_access.frappe.get_roles", return_value=["Practice Doctor"])
    @patch("medic_plus.api.data_access.frappe.session", user="doctor@example.test")
    @patch("medic_plus.api.data_access.frappe.conf", {"developer_mode": True})
    @patch("medic_plus.api.data_access.frappe.db", new_callable=MagicMock)
    @patch("medic_plus.api.data_access.frappe.get_doc")
    @patch("medic_plus.api.data_access.frappe.sendmail")
    @patch("medic_plus.api.data_access.now_datetime",
           return_value=__import__("datetime").datetime(2026, 4, 13, 12, 0, 0))
    @patch("medic_plus.api.data_access.add_to_date",
           return_value="2026-04-13 12:10:00")
    def test_request_creates_record_and_returns_name(
        self, mock_add, mock_now, mock_mail, mock_get_doc, mock_db, mock_session, mock_roles, mock_perm
    ):
        from medic_plus.api.data_access import request_unmask

        # db.get_value: practice member lookup → "PRAC-00001",
        # patient resolution → "PAT-00001",
        # patient contact → {"email": "pat@x.test", "mobile": "0821234567"}
        # user email lookup → "doctor@example.test"
        mock_db.get_value.side_effect = [
            "PRAC-00001",   # _get_practice_for_user
            "PAT-00001",    # _resolve_patient_from_doc (Patient doctype → returns docname)
            {"email": "pat@x.test", "mobile": "0821234567"},  # _resolve_patient_contact
            "doctor@example.test",  # requester email lookup
        ]
        mock_db.set_value.return_value = None
        mock_db.commit.return_value = None

        mock_doc_instance = self._make_mock_doc()
        mock_get_doc.return_value = mock_doc_instance

        result = request_unmask(
            doctype="Patient",
            docname="PAT-00001",
            field="custom_sa_id_number",
        )

        self.assertIn("request", result)
        self.assertEqual(result["request"], "DMR-2026-00001")
        # In developer_mode, OTPs should be visible for QA
        self.assertIn("_dev_requester_otp", result)
        self.assertIn("_dev_patient_otp", result)
        # OTPs are 6 digits
        self.assertEqual(len(result["_dev_requester_otp"]), 6)

    @patch("medic_plus.api.data_access.frappe.has_permission")
    @patch("medic_plus.api.data_access.frappe.get_roles", return_value=["Practice Doctor"])
    @patch("medic_plus.api.data_access.frappe.session", user="doctor@example.test")
    @patch("medic_plus.api.data_access.frappe.db", new_callable=MagicMock)
    @patch("medic_plus.api.data_access.frappe.get_doc")
    @patch("medic_plus.api.data_access.frappe.sendmail")
    def test_non_protected_field_raises(
        self, mock_mail, mock_get_doc, mock_db, mock_session, mock_roles, mock_perm
    ):
        from medic_plus.api.data_access import request_unmask
        import frappe as _frappe

        with self.assertRaises(_frappe.ValidationError):
            request_unmask(
                doctype="Patient",
                docname="PAT-00001",
                field="patient_name",  # not in PROTECTED_FIELDS
            )


class TestVerifyUnmask(unittest.TestCase):
    """verify_unmask() validates both OTPs and returns plaintext on success."""

    FUTURE = "2099-12-31 23:59:59"
    PAST = "2000-01-01 00:00:00"

    def _make_req(self, status="Pending", requester="doctor@example.test", expires_at=None):
        req = MagicMock()
        req.name = "DMR-2026-00001"
        req.requested_by = requester
        req.status = status
        req.target_doctype = "Patient"
        req.target_docname = "PAT-00001"
        req.target_field = "custom_sa_id_number"
        req.patient = "PAT-00001"
        req.practice = "PRAC-00001"
        req.requester_otp_hash = _hash_otp("111111")
        req.patient_otp_hash = _hash_otp("222222")
        req.expires_at = expires_at or self.FUTURE
        return req

    def _run_verify(self, req_mock, requester_otp, patient_otp, db_value="9001014800088"):
        """
        Run verify_unmask with targeted patches.
        We patch _get_unmask_request (private helper) instead of frappe.get_doc
        to avoid contaminating the global frappe.get_doc used by the cache layer.
        """
        from medic_plus.api.data_access import verify_unmask
        import datetime as dt

        with patch("medic_plus.api.data_access._get_unmask_request", return_value=req_mock), \
             patch("medic_plus.api.data_access.now_datetime",
                   return_value=dt.datetime(2026, 4, 13, 12, 0, 0)), \
             patch("medic_plus.api.data_access.frappe.has_permission"), \
             patch("medic_plus.api.data_access.frappe.session", user=req_mock.requested_by), \
             patch("medic_plus.api.data_access.frappe.db", new_callable=MagicMock) as mock_db, \
             patch("medic_plus.api.data_access._log_access"):
            mock_db.get_value.return_value = db_value
            mock_db.set_value.return_value = None
            mock_db.commit.return_value = None
            return verify_unmask(
                request_name="DMR-2026-00001",
                requester_otp=requester_otp,
                patient_otp=patient_otp,
            )

    def test_correct_otps_return_value(self):
        result = self._run_verify(self._make_req(), "111111", "222222")
        self.assertEqual(result["value"], "9001014800088")

    def test_wrong_requester_otp_raises(self):
        import frappe as _frappe
        with self.assertRaises(_frappe.ValidationError):
            self._run_verify(self._make_req(), "999999", "222222")

    def test_wrong_patient_otp_raises(self):
        import frappe as _frappe
        with self.assertRaises(_frappe.ValidationError):
            self._run_verify(self._make_req(), "111111", "999999")

    def test_expired_request_raises(self):
        import frappe as _frappe
        from medic_plus.api.data_access import verify_unmask
        import datetime as dt

        req = self._make_req(expires_at=self.PAST)
        with patch("medic_plus.api.data_access._get_unmask_request", return_value=req), \
             patch("medic_plus.api.data_access.now_datetime",
                   return_value=dt.datetime(2026, 4, 13, 12, 0, 0)), \
             patch("medic_plus.api.data_access.frappe.session", user="doctor@example.test"), \
             patch("medic_plus.api.data_access.frappe.db", new_callable=MagicMock) as mock_db:
            mock_db.set_value.return_value = None
            mock_db.commit.return_value = None
            with self.assertRaises(_frappe.ValidationError):
                verify_unmask("DMR-2026-00001", "111111", "222222")

    def test_different_user_cannot_verify(self):
        import frappe as _frappe
        from medic_plus.api.data_access import verify_unmask

        req = self._make_req(requester="doctor@example.test")
        with patch("medic_plus.api.data_access._get_unmask_request", return_value=req), \
             patch("medic_plus.api.data_access.frappe.session", user="other@example.test"), \
             patch("medic_plus.api.data_access.frappe.db", new_callable=MagicMock):
            with self.assertRaises(_frappe.PermissionError):
                verify_unmask("DMR-2026-00001", "111111", "222222")
