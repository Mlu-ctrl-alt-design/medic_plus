"""
Tests for Practice Setup Checklist.

Verifies:
1. Checklist auto-creation and progress computation
2. Step hooks update the checklist in real-time
3. Tenant isolation — Practice A cannot read Practice B's checklist

Company creation (ERPNext fiscal-year interaction) is tested in
test_provisioning.py. Here we create Practice records directly to
keep these tests fast and isolated.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from medic_plus.medic_plus.doctype.practice_setup_checklist.practice_setup_checklist import (
	on_signature_saved,
	on_staff_accepted,
	on_patient_invited,
	STEP_FIELDS,
)


def _make_practice(suffix: str) -> str:
	"""Create a minimal Practice record and its checklist. Returns practice name."""
	practice = frappe.get_doc({
		"doctype": "Practice",
		"practice_name": f"PSC Test Practice {suffix}",
		"is_active": 1,
	})
	practice.insert(ignore_permissions=True)

	frappe.get_doc({
		"doctype": "Practice Setup Checklist",
		"practice": practice.name,
	}).insert(ignore_permissions=True)

	return practice.name


def _make_user(suffix: str, practice: str) -> str:
	"""Create a minimal Practice Doctor user and link them to the practice."""
	email = f"psc.test{suffix}@example.com"
	if not frappe.db.exists("User", email):
		frappe.get_doc({
			"doctype": "User",
			"email": email,
			"first_name": f"PSC{suffix}",
			"send_welcome_email": 0,
			"roles": [{"role": "Practice Doctor"}],
		}).insert(ignore_permissions=True)

	frappe.get_doc({
		"doctype": "Practice Member",
		"practice": practice,
		"full_name": f"PSC{suffix}",
		"email": email,
		"user": email,
		"role": "Receptionist",
		"status": "Accepted",
	}).insert(ignore_permissions=True)

	return email


def _get_checklist(practice: str):
	name = frappe.db.get_value("Practice Setup Checklist", {"practice": practice}, "name")
	return frappe.get_doc("Practice Setup Checklist", name)


class TestPracticeSetupChecklist(FrappeTestCase):

	# ------------------------------------------------------------------
	# 1. Progress computation
	# ------------------------------------------------------------------

	def test_initial_state(self):
		practice = _make_practice("Init")
		checklist = _get_checklist(practice)
		self.assertEqual(checklist.completion_pct, 0)
		self.assertEqual(checklist.current_step, 1)

	def test_partial_progress(self):
		practice = _make_practice("Partial")
		checklist = _get_checklist(practice)

		checklist.step_practice_profile = 1
		checklist.step_signature = 1
		checklist.save(ignore_permissions=True)
		checklist.reload()

		self.assertEqual(checklist.completion_pct, 25)  # 2 of 8
		self.assertEqual(checklist.current_step, 3)     # first unchecked = step 3

	def test_all_complete(self):
		practice = _make_practice("Complete")
		checklist = _get_checklist(practice)

		for field in STEP_FIELDS:
			checklist.set(field, 1)
		checklist.save(ignore_permissions=True)
		checklist.reload()

		self.assertEqual(checklist.completion_pct, 100)
		self.assertEqual(checklist.current_step, len(STEP_FIELDS) + 1)

	# ------------------------------------------------------------------
	# 2. Step hooks
	# ------------------------------------------------------------------

	def test_signature_hook_ticks_step_2(self):
		practice = _make_practice("Sig")
		on_signature_saved(practice)
		checklist = _get_checklist(practice)
		self.assertEqual(checklist.step_signature, 1)

	def test_staff_accepted_hook_ticks_step_3(self):
		practice = _make_practice("Staff")
		on_staff_accepted(practice)
		checklist = _get_checklist(practice)
		self.assertEqual(checklist.step_staff_invited, 1)

	def test_patient_invited_hook_ticks_step_4(self):
		practice = _make_practice("Pat")
		on_patient_invited(practice)
		checklist = _get_checklist(practice)
		self.assertEqual(checklist.step_patients_invited, 1)

	def test_tick_is_idempotent(self):
		"""Calling a hook twice must not fail or double-count."""
		practice = _make_practice("Idem")
		on_staff_accepted(practice)
		on_staff_accepted(practice)  # second call — should be a no-op
		checklist = _get_checklist(practice)
		self.assertEqual(checklist.step_staff_invited, 1)

	# ------------------------------------------------------------------
	# 3. Tenant isolation
	# ------------------------------------------------------------------

	def test_checklist_tenant_isolation(self):
		"""The PQC for Practice A's user must not expose Practice B's checklist.

		We test the PQC output directly rather than going through frappe.get_all()
		because frappe.set_user() in tests does not fully flush the roles cache
		that frappe.get_roles() reads, making ORM-level permission assertions
		unreliable in the test runner.
		"""
		from medic_plus.api.permissions import get_practice_setup_checklist_permission_query

		practice_a = _make_practice("IsoA")
		practice_b = _make_practice("IsoB")
		user_a = _make_user("IsoA", practice_a)

		# The PQC for user_a should scope to practice_a only
		condition = get_practice_setup_checklist_permission_query(user=user_a)
		self.assertIn(practice_a, condition)
		self.assertNotIn(practice_b, condition)
		# Sanity check: practice_b's user has no Practice Member → returns "1=0"
		condition_b = get_practice_setup_checklist_permission_query(user="nobody@example.com")
		self.assertEqual(condition_b, "1=0")
