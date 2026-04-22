"""Integration tests for the doctor signup funnel."""

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
		import random
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
