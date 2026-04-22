"""Integration tests for the doctor signup funnel."""

import random

import frappe
from frappe.tests.utils import FrappeTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


class TestAdminOnboardDoctor(FrappeTestCase):
	"""onboard_doctor must produce the full tenant via provision_doctor."""

	def setUp(self):
		frappe.set_user("Administrator")
		suffix = frappe.generate_hash(length=6)
		self.email = f"adm.test.{suffix}@test.local"
		self.practice_name = f"Admin Test Practice {suffix}"
		# Use a unique mobile to avoid collisions with pre-existing staging data
		# (mobile_no is a unique index on the User table). SA mobile format
		# is 10 digits starting with 0 — e.g. 0821234567.
		self.mobile = "082" + "".join(str(random.randint(0, 9)) for _ in range(7))

	def tearDown(self):
		frappe.db.rollback()

	def test_admin_onboard_creates_full_tenant(self):
		from medic_plus.api.onboarding import onboard_doctor

		onboard_doctor(
			full_name="Dr Admin Test",
			email=self.email,
			mobile=self.mobile,
			hpcsa_number="MP12345",
			practice_number="1234567",
			practice_name=self.practice_name,
			is_dispensing_doctor=0,
		)

		practice = frappe.get_value("Practice", {"practice_name": self.practice_name}, "name")
		self.assertTrue(practice, "Practice not created")
		self.assertTrue(frappe.get_value("Practice", practice, "company"), "Company not linked")
		self.assertTrue(frappe.db.exists("User", self.email), "User not created")
		self.assertTrue(
			frappe.db.exists("Practice Member", {"practice": practice, "user": self.email}),
			"Practice Member not created",
		)
		self.assertTrue(
			frappe.db.exists("Practice Setup Checklist", {"practice": practice}),
			"Practice Setup Checklist not created",
		)


class TestNotifyAdminsRelocated(FrappeTestCase):
	"""notify_admins_of_new_request must be importable and callable from signup.py."""

	def test_function_exists_and_accepts_prr(self):
		from medic_plus.api.signup import notify_admins_of_new_request
		# Build a minimal PRR-shaped object; we only verify the import + no-throw.
		# frappe.get_all returns [] in test because no Healthcare Administrator roles typically assigned.
		doc = frappe._dict({
			"name": "PRR-TEST-00000",
			"practice_name": "X",
			"full_name": "Y",
			"email": "z@example.com",
			"hpcsa_number": "MP1",
			"is_dispensing_doctor": 0,
		})
		# Should not raise even if no recipients exist.
		notify_admins_of_new_request(doc)
