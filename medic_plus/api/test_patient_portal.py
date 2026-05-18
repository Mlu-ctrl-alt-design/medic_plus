"""Patient Portal — Python tests.

Per medic_plus CLAUDE.md, IGNORE_TEST_RECORD_DEPENDENCIES prevents the test
framework from importing ERPNext test modules that crash at BootStrapTestData.
"""
import frappe
import unittest
from medic_plus.api import patient_portal


IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


def _purge_test_practice(slug: str, email: str):
	"""Idempotent cleanup — removes leftover rows from prior aborted test runs."""
	frappe.set_user("Administrator")
	frappe.db.delete("Patient", {"email": email})
	frappe.db.delete("Practice", {"slug": slug})
	frappe.db.delete("Notification Settings", {"user": email})
	frappe.db.delete("User", {"email": email})
	frappe.db.commit()


class TestPortalOTP(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.slug = "ttp-otp"
		cls.email = "ttp-patient@example.com"
		_purge_test_practice(cls.slug, cls.email)
		cls.practice = frappe.get_doc({
			"doctype": "Practice",
			"practice_name": "TTP OTP Practice",
			"slug": cls.slug,
			"is_active": 1,
			"email": "ttp-otp@example.com",
		}).insert(ignore_permissions=True)

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
		# Reset session before cleanup — verify_portal_otp may have changed it,
		# and a non-Administrator session user contaminates subsequent test classes
		# (e.g. Notification Settings link validation picks up stale session.user).
		frappe.set_user("Administrator")
		# Cascade: delete patient, then practice. Ignore_permissions because
		# PQCs may be hostile in the post-test cleanup user context.
		frappe.db.delete("Patient", {"name": cls.patient.name})
		frappe.db.delete("Practice", {"name": cls.practice.name})
		frappe.db.delete("Notification Settings", {"user": cls.email})
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


class TestPortalProfile(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.slug = "ttp-prof"
		cls.email = "ttp-prof-patient@example.com"
		_purge_test_practice(cls.slug, cls.email)
		cls.practice = frappe.get_doc({
			"doctype": "Practice", "practice_name": "TTP Prof", "slug": cls.slug,
			"is_active": 1, "email": "ttp-prof@example.com",
		}).insert(ignore_permissions=True)
		cls.patient = frappe.get_doc({
			"doctype": "Patient", "first_name": "Prof", "last_name": "User",
			"sex": "Female", "email": cls.email, "custom_practice": cls.practice.name,
			"status": "Active", "invite_user": 0,
		}).insert(ignore_permissions=True)
		# Provision a User with Patient role
		cls.user = frappe.get_doc({
			"doctype": "User", "email": cls.email, "first_name": "Prof",
			"enabled": 1, "user_type": "Website User", "send_welcome_email": 0,
			"roles": [{"role": "Patient"}],
		}).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete("Patient", {"name": cls.patient.name})
		frappe.db.delete("Practice", {"name": cls.practice.name})
		frappe.db.delete("Notification Settings", {"user": cls.email})
		frappe.db.delete("User", {"email": cls.email})
		frappe.db.commit()

	def setUp(self):
		frappe.set_user(self.email)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_get_me_returns_editable_and_masked(self):
		me = patient_portal.get_me(self.slug)
		self.assertEqual(me["email"], self.email)
		self.assertNotIn("custom_nhid", me)
		self.assertEqual(me["first_name"], "Prof")

	def test_update_me_accepts_allowed_field(self):
		result = patient_portal.update_me(self.slug, {"mobile": "+27821234567"})
		self.assertEqual(result["mobile"], "+27821234567")

	def test_update_me_rejects_forbidden_field(self):
		with self.assertRaises(frappe.ValidationError):
			patient_portal.update_me(self.slug, {"custom_practice": "OTHER"})

	def test_update_me_rejects_unknown_field(self):
		with self.assertRaises(frappe.ValidationError):
			patient_portal.update_me(self.slug, {"is_admin": True})

	def test_resolve_my_patient_rejects_guest(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			patient_portal._resolve_my_patient(self.slug)


from frappe.utils import add_days, add_to_date, now_datetime as _ndt, today as fr_today


class TestPortalAppointments(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.slug = "ttp-appt"
		cls.email = "ttp-appt-patient@example.com"
		_purge_test_practice(cls.slug, cls.email)
		frappe.db.delete("Patient Appointment", {"appointment_date": [">=", "1900-01-01"], "patient": ""})
		cls.practice = frappe.get_doc({
			"doctype": "Practice", "practice_name": "TTP Appt", "slug": cls.slug,
			"is_active": 1, "email": "ttp-appt@example.com",
		}).insert(ignore_permissions=True)
		cls.patient = frappe.get_doc({
			"doctype": "Patient", "first_name": "Appt", "last_name": "User",
			"sex": "Male", "email": cls.email, "custom_practice": cls.practice.name,
			"status": "Active", "invite_user": 0,
		}).insert(ignore_permissions=True)
		cls.user = frappe.get_doc({
			"doctype": "User", "email": cls.email, "first_name": "Appt",
			"enabled": 1, "user_type": "Website User", "send_welcome_email": 0,
			"roles": [{"role": "Patient"}],
		}).insert(ignore_permissions=True)

		# Patient Appointment requires a practitioner — reuse any existing one
		# on this site rather than fabricating one (Practitioner creation pulls
		# in Company/Employee/Schedule deps that crash the bench test runner).
		practitioner = frappe.db.get_value("Healthcare Practitioner", {}, "name")
		appt_type = frappe.db.get_value("Appointment Type", {}, "name")
		if not practitioner or not appt_type:
			raise unittest.SkipTest("No Healthcare Practitioner or Appointment Type exists on this site")

		# Build an appointment 5 days out (cancellable) and one 2 hours out (not cancellable)
		cls.far_appt = frappe.get_doc({
			"doctype": "Patient Appointment",
			"patient": cls.patient.name,
			"practitioner": practitioner,
			"appointment_type": appt_type,
			"appointment_for": "Practitioner",
			"appointment_date": add_days(fr_today(), 5),
			"appointment_time": "10:00:00",
			"duration": 30,
			"custom_practice": cls.practice.name,
			"status": "Open",
		}).insert(ignore_permissions=True)
		soon = add_to_date(_ndt(), hours=2)
		cls.soon_appt = frappe.get_doc({
			"doctype": "Patient Appointment",
			"patient": cls.patient.name,
			"practitioner": practitioner,
			"appointment_type": appt_type,
			"appointment_for": "Practitioner",
			"appointment_date": str(soon.date()),
			"appointment_time": soon.time().strftime("%H:%M:%S"),
			"duration": 30,
			"custom_practice": cls.practice.name,
			"status": "Open",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete("Patient Appointment", {"patient": cls.patient.name})
		frappe.db.delete("Patient", {"name": cls.patient.name})
		frappe.db.delete("Practice", {"name": cls.practice.name})
		frappe.db.delete("Notification Settings", {"user": cls.email})
		frappe.db.delete("User", {"email": cls.email})
		frappe.db.commit()

	def setUp(self):
		# Reset appointment statuses — alphabetical test ordering means cancel
		# tests run before list tests and would otherwise leave far_appt Cancelled.
		frappe.set_user("Administrator")
		frappe.db.set_value("Patient Appointment", self.far_appt.name, "status", "Scheduled")
		frappe.db.set_value("Patient Appointment", self.soon_appt.name, "status", "Scheduled")
		frappe.db.commit()
		frappe.set_user(self.email)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_list_my_appointments_returns_upcoming(self):
		result = patient_portal.list_my_appointments(self.slug)
		names = [a["name"] for a in result["upcoming"]]
		self.assertIn(self.far_appt.name, names)

	def test_cancel_appointment_24h_out_succeeds(self):
		result = patient_portal.cancel_my_appointment(self.slug, self.far_appt.name)
		self.assertTrue(result["ok"])
		self.assertEqual(
			frappe.db.get_value("Patient Appointment", self.far_appt.name, "status"),
			"Cancelled",
		)

	def test_cancel_appointment_within_24h_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			patient_portal.cancel_my_appointment(self.slug, self.soon_appt.name)

	def test_resolve_my_practices_lists_active(self):
		result = patient_portal.resolve_my_practices()
		slugs = [p["slug"] for p in result]
		self.assertIn(self.slug, slugs)

	def test_get_boot_returns_practice_and_has_patient(self):
		result = patient_portal.get_boot(self.slug)
		self.assertEqual(result["practice"]["slug"], self.slug)
		self.assertTrue(result["is_authed"])
		self.assertTrue(result["has_patient"])


class TestPortalCrossTenantIsolation(unittest.TestCase):
	"""The headline POPIA-relevant test: a Patient at Practice A cannot read
	Patient B's appointments / sick notes / records / invoices at Practice B."""

	@classmethod
	def setUpClass(cls):
		# Practice A + Patient A
		cls.slug_a = "ttp-iso-a"
		cls.email_a = "ttp-iso-a-patient@example.com"
		cls.slug_b = "ttp-iso-b"
		cls.email_b = "ttp-iso-b-patient@example.com"
		_purge_test_practice(cls.slug_a, cls.email_a)
		_purge_test_practice(cls.slug_b, cls.email_b)

		cls.practice_a = frappe.get_doc({
			"doctype": "Practice", "practice_name": "TTP Iso A", "slug": cls.slug_a,
			"is_active": 1, "email": "ttp-iso-a@example.com",
		}).insert(ignore_permissions=True)
		cls.patient_a = frappe.get_doc({
			"doctype": "Patient", "first_name": "Iso", "last_name": "A",
			"sex": "Male", "email": cls.email_a, "custom_practice": cls.practice_a.name,
			"status": "Active", "invite_user": 0,
		}).insert(ignore_permissions=True)
		cls.user_a = frappe.get_doc({
			"doctype": "User", "email": cls.email_a, "first_name": "Iso A",
			"enabled": 1, "user_type": "Website User", "send_welcome_email": 0,
			"roles": [{"role": "Patient"}],
		}).insert(ignore_permissions=True)

		# Practice B + Patient B + Appointment B
		cls.practice_b = frappe.get_doc({
			"doctype": "Practice", "practice_name": "TTP Iso B", "slug": cls.slug_b,
			"is_active": 1, "email": "ttp-iso-b@example.com",
		}).insert(ignore_permissions=True)
		cls.patient_b = frappe.get_doc({
			"doctype": "Patient", "first_name": "Iso", "last_name": "B",
			"sex": "Female", "email": cls.email_b, "custom_practice": cls.practice_b.name,
			"status": "Active", "invite_user": 0,
		}).insert(ignore_permissions=True)

		practitioner = frappe.db.get_value("Healthcare Practitioner", {}, "name")
		appt_type = frappe.db.get_value("Appointment Type", {}, "name")
		if not practitioner or not appt_type:
			raise unittest.SkipTest("No Healthcare Practitioner or Appointment Type exists on this site")

		cls.appt_b = frappe.get_doc({
			"doctype": "Patient Appointment",
			"patient": cls.patient_b.name,
			"practitioner": practitioner,
			"appointment_type": appt_type,
			"appointment_for": "Practitioner",
			"appointment_date": add_days(fr_today(), 7),
			"appointment_time": "09:00:00", "duration": 30,
			"custom_practice": cls.practice_b.name, "status": "Open",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete("Patient Appointment", {"name": cls.appt_b.name})
		for d in (cls.patient_a.name, cls.patient_b.name):
			frappe.db.delete("Patient", {"name": d})
		for d in (cls.practice_a.name, cls.practice_b.name):
			frappe.db.delete("Practice", {"name": d})
		for d in (cls.email_a, cls.email_b):
			frappe.db.delete("Notification Settings", {"user": d})
			frappe.db.delete("User", {"email": d})
		frappe.db.commit()

	def test_patient_a_cannot_resolve_practice_b(self):
		frappe.set_user(self.email_a)
		try:
			with self.assertRaises(frappe.PermissionError):
				patient_portal._resolve_my_patient(self.slug_b)
		finally:
			frappe.set_user("Administrator")

	def test_patient_a_cannot_list_practice_b_appointments(self):
		# Direct PQC call (don't rely on session role cache)
		from medic_plus.api.permissions import get_patient_appointment_permission_query
		condition = get_patient_appointment_permission_query(user=self.email_a)
		# Condition should scope to Patient A's name, not B's
		self.assertIn(self.patient_a.name, condition)
		self.assertNotIn(self.patient_b.name, condition)
		self.assertNotIn(self.appt_b.name, condition)
