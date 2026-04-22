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


class TestCompletionToken(FrappeTestCase):
	"""verify_signup_completion_token + set_password_and_login happy and sad paths."""

	def setUp(self):
		frappe.set_user("Administrator")
		# set_password_and_login calls frappe.local.login_manager.login_as(),
		# which is only set up during an HTTP request. Stub it with a no-op
		# so the consume + redirect flow is exercisable in tests. (Real HTTP
		# calls always have a fully initialised LoginManager.)
		class _StubLoginManager:
			def login_as(self, user, **_kwargs):
				frappe.set_user(user)

		frappe.local.login_manager = _StubLoginManager()
		self.email = f"tok.{frappe.generate_hash(length=6)}@test.local"
		# Unique SA-format mobile to dodge User.mobile_no unique index
		# collisions with pre-existing staging data.
		self.mobile = "082" + "".join(str(random.randint(0, 9)) for _ in range(7))
		# Pre-create a User (simulates post-provisioning state)
		frappe.get_doc({
			"doctype": "User",
			"email": self.email,
			"first_name": "Token",
			"last_name": "Tester",
			"send_welcome_email": 0,
		}).insert(ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Practice Registration Request",
			"practice_name": f"Tok Practice {frappe.generate_hash(length=6)}",
			"full_name": "Token Tester",
			"email": self.email,
			"mobile": self.mobile,
			"hpcsa_number": "MP11111",
			"practice_number": "1234567",
			"status": "Provisioned",
		}).insert(ignore_permissions=True)
		self.req_name = frappe.db.get_value("Practice Registration Request", {"email": self.email}, "name")

	def tearDown(self):
		frappe.db.rollback()

	def test_issue_and_consume_token(self):
		from medic_plus.api.signup import (
			issue_completion_token,
			verify_signup_completion_token,
			set_password_and_login,
		)
		token = issue_completion_token(email=self.email, request_name=self.req_name)
		self.assertEqual(len(token), 48)

		info = verify_signup_completion_token(token=token)
		self.assertEqual(info["email"], self.email)
		self.assertGreater(info["expires_in"], 0)

		# Consumed -> second verify fails
		result = set_password_and_login(token=token, password="S0meLongP@ssword123")
		self.assertEqual(result["redirect"], "/app/practice")
		with self.assertRaises(frappe.ValidationError):
			verify_signup_completion_token(token=token)

	def test_invalid_token(self):
		from medic_plus.api.signup import verify_signup_completion_token
		with self.assertRaises(frappe.ValidationError):
			verify_signup_completion_token(token="nope-not-a-real-token")
