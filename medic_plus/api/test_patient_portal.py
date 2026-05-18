"""Patient Portal — Python tests.

Per medic_plus CLAUDE.md, IGNORE_TEST_RECORD_DEPENDENCIES prevents the test
framework from importing ERPNext test modules that crash at BootStrapTestData.
"""
import frappe
import unittest
from medic_plus.api import patient_portal


IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


class TestPortalOTP(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.slug = "ttp-otp"
		cls.practice = frappe.get_doc({
			"doctype": "Practice",
			"practice_name": "TTP OTP Practice",
			"slug": cls.slug,
			"is_active": 1,
			"email": "ttp-otp@example.com",
		}).insert(ignore_permissions=True)

		cls.email = "ttp-patient@example.com"
		cls.patient = frappe.get_doc({
			"doctype": "Patient",
			"first_name": "Otp",
			"last_name": "Tester",
			"sex": "Male",
			"email": cls.email,
			"custom_practice": cls.practice.name,
			"status": "Active",
			"invite_user": 0,
		}).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Cascade: delete patient, then practice. Ignore_permissions because
		# PQCs may be hostile in the post-test cleanup user context.
		frappe.db.delete("Patient", {"name": cls.patient.name})
		frappe.db.delete("Practice", {"name": cls.practice.name})
		frappe.db.delete("User", {"email": cls.email})
		frappe.db.commit()

	def setUp(self):
		# Wipe OTP cache state between tests
		for key in (
			patient_portal._otp_cache_key(self.slug, self.email),
			patient_portal._otp_attempt_key(self.slug, self.email),
			patient_portal._otp_verify_attempt_key(self.slug, self.email),
		):
			frappe.cache.delete_value(key)

	def test_request_otp_existing_patient_emits_code(self):
		result = patient_portal.request_portal_otp(self.slug, self.email)
		self.assertEqual(result, {"ok": True})
		cached = frappe.cache.get_value(patient_portal._otp_cache_key(self.slug, self.email))
		self.assertIsNotNone(cached)
		self.assertEqual(len(cached), 6)
		self.assertTrue(cached.isdigit())

	def test_request_otp_unknown_email_does_not_emit_code(self):
		result = patient_portal.request_portal_otp(self.slug, "ghost@example.com")
		self.assertEqual(result, {"ok": True})
		cached = frappe.cache.get_value(patient_portal._otp_cache_key(self.slug, "ghost@example.com"))
		self.assertIsNone(cached)

	def test_request_otp_rate_limited_after_5_requests(self):
		for _ in range(5):
			patient_portal.request_portal_otp(self.slug, self.email)
		with self.assertRaises(frappe.ValidationError):
			patient_portal.request_portal_otp(self.slug, self.email)

	def test_verify_otp_correct_code_logs_user_in(self):
		patient_portal.request_portal_otp(self.slug, self.email)
		code = frappe.cache.get_value(patient_portal._otp_cache_key(self.slug, self.email))
		result = patient_portal.verify_portal_otp(self.slug, self.email, code)
		self.assertTrue(result["ok"])
		self.assertEqual(frappe.session.user, self.email)

	def test_verify_otp_wrong_code_increments_attempts(self):
		patient_portal.request_portal_otp(self.slug, self.email)
		with self.assertRaises(frappe.ValidationError):
			patient_portal.verify_portal_otp(self.slug, self.email, "000000")
		attempts = frappe.cache.get_value(patient_portal._otp_verify_attempt_key(self.slug, self.email))
		self.assertEqual(attempts, 1)

	def test_verify_otp_provisions_user_with_patient_role(self):
		patient_portal.request_portal_otp(self.slug, self.email)
		code = frappe.cache.get_value(patient_portal._otp_cache_key(self.slug, self.email))
		patient_portal.verify_portal_otp(self.slug, self.email, code)
		user_doc = frappe.get_doc("User", self.email)
		self.assertIn("Patient", [r.role for r in user_doc.roles])
		self.assertEqual(user_doc.user_type, "Website User")
