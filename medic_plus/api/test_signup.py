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
		from unittest.mock import patch
		from medic_plus.api.signup import notify_admins_of_new_request
		# Build a minimal PRR-shaped object; we only verify the import + no-throw.
		doc = frappe._dict({
			"name": "PRR-TEST-00000",
			"practice_name": "X",
			"full_name": "Y",
			"email": "z@example.com",
			"hpcsa_number": "MP1",
			"is_dispensing_doctor": 0,
		})
		# Real recipients (e.g. Administrator getting the Healthcare Administrator
		# role on staging) would make Email Queue reject the unmailable name —
		# stub sendmail so the assertion is purely "function executes cleanly".
		with patch("medic_plus.api.signup.frappe.sendmail"):
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
		from unittest.mock import patch
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

		# Stub sendmail so we don't queue real emails; assert it was called.
		with patch("medic_plus.api.signup.frappe.sendmail") as send_mock:
			result = set_password_and_login(token=token, password="S0meLongP@ssword123")
		self.assertEqual(result["redirect"], "/app/practice")
		# Owner welcome email queued; admin alert is conditional on real
		# Healthcare Administrator users existing — count 1 or 2 is OK.
		self.assertGreaterEqual(send_mock.call_count, 1)
		# welcome_email_sent_at stamped exactly once (idempotent path).
		self.assertTrue(
			frappe.db.get_value("Practice Registration Request", self.req_name, "welcome_email_sent_at")
		)
		# Consumed -> second verify fails
		with self.assertRaises(frappe.ValidationError):
			verify_signup_completion_token(token=token)

	def test_invalid_token(self):
		from medic_plus.api.signup import verify_signup_completion_token
		with self.assertRaises(frappe.ValidationError):
			verify_signup_completion_token(token="nope-not-a-real-token")

	def test_welcome_email_idempotent(self):
		"""send_owner_welcome_email skips if welcome_email_sent_at is set."""
		from unittest.mock import patch
		from medic_plus.api.signup import send_owner_welcome_email
		# Pre-stamp the timestamp; the function should no-op.
		frappe.db.set_value(
			"Practice Registration Request", self.req_name,
			"welcome_email_sent_at", frappe.utils.now(),
		)
		with patch("medic_plus.api.signup.frappe.sendmail") as send_mock:
			send_owner_welcome_email(self.req_name)
		send_mock.assert_not_called()

	def test_admin_notify_skips_administrator(self):
		"""Built-in 'Administrator' user is excluded from recipient list."""
		from unittest.mock import patch
		from medic_plus.api.signup import notify_admins_of_provisioned_practice
		with patch("medic_plus.api.signup.frappe.sendmail") as send_mock:
			notify_admins_of_provisioned_practice(self.req_name)
		# If sendmail was called, recipients must not include "Administrator".
		for call in send_mock.call_args_list:
			recipients = call.kwargs.get("recipients") or (call.args[0] if call.args else [])
			self.assertNotIn("Administrator", recipients)


class TestSignupStatus(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.req = frappe.get_doc({
			"doctype": "Practice Registration Request",
			"practice_name": f"Stat Practice {frappe.generate_hash(length=6)}",
			"full_name": "Stat Tester",
			"email": f"stat.{frappe.generate_hash(length=6)}@test.local",
			"mobile": "0821234567",
			"hpcsa_number": "MP22222",
			"practice_number": "1234567",
			"status": "Pending",
			"payment_status": "Unpaid",
		}).insert(ignore_permissions=True)
		# PRAC-00001 may not exist on every environment; fetch any real
		# Practice name to satisfy the Link field on provisioned_practice.
		self.existing_practice = frappe.db.get_value("Practice", {}, "name")

	def tearDown(self):
		frappe.db.rollback()

	def test_status_not_ready_before_provisioning(self):
		from medic_plus.api.signup import signup_status
		r = signup_status(request_name=self.req.name)
		self.assertFalse(r["ready"])
		self.assertEqual(r["payment_status"], "Unpaid")
		self.assertEqual(r["status"], "Pending")

	def test_status_ready_after_provisioning(self):
		from medic_plus.api.signup import signup_status
		if not self.existing_practice:
			self.skipTest("At least one Practice must exist on the site to run this test.")
		frappe.db.set_value("Practice Registration Request", self.req.name, {
			"payment_status": "Paid",
			"status": "Provisioned",
			"provisioned_practice": self.existing_practice,
			"completion_email_sent_at": frappe.utils.now(),
		})
		r = signup_status(request_name=self.req.name)
		self.assertTrue(r["ready"])

	def test_status_unknown_request_returns_empty(self):
		from medic_plus.api.signup import signup_status
		r = signup_status(request_name="PRR-99999999")
		self.assertFalse(r["ready"])
		self.assertIsNone(r["status"])
		self.assertIsNone(r["payment_status"])


class TestYocoAutoProvision(FrappeTestCase):
	"""_handle_payment_succeeded must provision + emit completion token."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.mobile = "082" + "".join(str(random.randint(0, 9)) for _ in range(7))
		self.req = frappe.get_doc({
			"doctype": "Practice Registration Request",
			"practice_name": f"Webhook Practice {frappe.generate_hash(length=6)}",
			"full_name": "Webhook Tester",
			"email": f"hook.{frappe.generate_hash(length=6)}@test.local",
			"mobile": self.mobile,
			"hpcsa_number": "MP33333",
			"practice_number": "1234567",
			"status": "Pending",
			"payment_status": "Pending",
			"yoco_checkout_id": "ch_test_abc",
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def _fake_yoco_payload(self):
		return {"metadata": {"request_name": self.req.name}, "checkoutId": "ch_test_abc"}

	def test_webhook_provisions_once(self):
		from medic_plus.api.yoco import _handle_payment_succeeded
		_handle_payment_succeeded(self._fake_yoco_payload())

		row = frappe.db.get_value(
			"Practice Registration Request", self.req.name,
			["payment_status", "status", "provisioned_practice", "completion_email_sent_at"],
			as_dict=True,
		)
		self.assertEqual(row.payment_status, "Paid")
		self.assertEqual(row.status, "Provisioned")
		self.assertTrue(row.provisioned_practice, "provisioned_practice not set")
		self.assertTrue(row.completion_email_sent_at, "completion_email_sent_at not set")
		self.assertTrue(frappe.db.exists("User", self.req.email))
		self.assertTrue(frappe.db.exists("Practice", row.provisioned_practice))

	def test_webhook_idempotent(self):
		from medic_plus.api.yoco import _handle_payment_succeeded
		_handle_payment_succeeded(self._fake_yoco_payload())
		first_practice = frappe.db.get_value("Practice Registration Request", self.req.name, "provisioned_practice")
		_handle_payment_succeeded(self._fake_yoco_payload())
		second_practice = frappe.db.get_value("Practice Registration Request", self.req.name, "provisioned_practice")
		self.assertEqual(first_practice, second_practice, "Double-fired webhook changed provisioned_practice")

	def test_webhook_marks_failure_on_exception(self):
		"""If provision_doctor raises, PRR flips to Provisioning Failed."""
		from medic_plus.api.yoco import _handle_payment_succeeded
		from unittest.mock import patch
		with patch("medic_plus.api.yoco.provision_doctor", side_effect=RuntimeError("boom")):
			_handle_payment_succeeded(self._fake_yoco_payload())
		row = frappe.db.get_value(
			"Practice Registration Request", self.req.name,
			["payment_status", "status", "provisioning_error"],
			as_dict=True,
		)
		self.assertEqual(row.payment_status, "Paid")
		self.assertEqual(row.status, "Provisioning Failed")
		self.assertIn("boom", row.provisioning_error or "")


class TestRetryScheduler(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.mobile = "082" + "".join(str(random.randint(0, 9)) for _ in range(7))
		self.req = frappe.get_doc({
			"doctype": "Practice Registration Request",
			"practice_name": f"Retry Practice {frappe.generate_hash(length=6)}",
			"full_name": "Retry Tester",
			"email": f"retry.{frappe.generate_hash(length=6)}@test.local",
			"mobile": self.mobile,
			"hpcsa_number": "MP44444",
			"practice_number": "1234567",
			"status": "Provisioning Failed",
			"payment_status": "Paid",
			"yoco_checkout_id": "ch_retry_xyz",
			"provisioning_error": "simulated boom",
		}).insert(ignore_permissions=True)
		# Rewind `modified` past the 5-min cutoff so retry picks it up.
		six_min_ago = frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=-6)
		frappe.db.sql(
			"UPDATE `tabPractice Registration Request` SET modified=%s WHERE name=%s",
			(six_min_ago, self.req.name),
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_retry_provisions_stuck_request(self):
		from medic_plus.api.signup import retry_failed_provisioning
		retry_failed_provisioning()
		row = frappe.db.get_value(
			"Practice Registration Request", self.req.name,
			["status", "provisioned_practice"],
			as_dict=True,
		)
		self.assertEqual(row.status, "Provisioned")
		self.assertTrue(row.provisioned_practice)
