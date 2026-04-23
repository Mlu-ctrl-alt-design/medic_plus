"""
Tests for Practice Member invitation flow.

Verifies:
1. Staff invitation — creates User, sets status=Sent, triggers checklist step 3
2. Patient invitation — creates Patient record, sets status=Sent, triggers checklist step 4
3. Duplicate guard — same email in same practice is rejected
4. Tenant isolation — PQC scopes members to the correct practice

IGNORE_TEST_RECORD_DEPENDENCIES prevents the test runner from traversing
into Company and Healthcare Practitioner modules (which trigger ERPNext's
BootStrapTestData at import time, conflicting with the site's 2026-2027 FY).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner", "Patient", "User"]


def _make_practice(suffix: str) -> str:
	"""Create a minimal Practice and its Setup Checklist. Returns practice name."""
	practice = frappe.get_doc({
		"doctype": "Practice",
		"practice_name": f"PM Test Practice {suffix}",
		"is_active": 1,
	})
	practice.insert(ignore_permissions=True)

	frappe.get_doc({
		"doctype": "Practice Setup Checklist",
		"practice": practice.name,
	}).insert(ignore_permissions=True)

	return practice.name


def _make_pm(practice: str, role: str, suffix: str, **kwargs) -> object:
	"""Create a Practice Member with status=Pending and return the doc."""
	email = f"pm.test.{suffix}@example.com"
	doc = frappe.get_doc({
		"doctype": "Practice Member",
		"practice": practice,
		"full_name": f"Test {suffix}",
		"email": email,
		"role": role,
		"status": "Pending",
		**kwargs,
	})
	doc.insert(ignore_permissions=True)
	return doc


def _get_checklist(practice: str):
	name = frappe.db.get_value("Practice Setup Checklist", {"practice": practice}, "name")
	return frappe.get_doc("Practice Setup Checklist", name)


class TestPracticeMemberInvitation(FrappeTestCase):

	# ------------------------------------------------------------------
	# 1. Staff invitation
	# ------------------------------------------------------------------

	def test_staff_invitation_creates_user(self):
		practice = _make_practice("StaffInv")
		pm = _make_pm(practice, "Receptionist", "StaffInv")

		pm.reload()
		self.assertIsNotNone(pm.user, "User should be set after staff invitation")
		self.assertEqual(pm.status, "Sent")
		self.assertIsNotNone(pm.invitation_sent_on)

		# The created User should exist
		self.assertTrue(frappe.db.exists("User", pm.user))

	def test_staff_invitation_assigns_frappe_role(self):
		practice = _make_practice("StaffRole")
		pm = _make_pm(practice, "Receptionist", "StaffRole")

		pm.reload()
		user = frappe.get_doc("User", pm.user)
		user_roles = [r.role for r in user.roles]
		self.assertIn("Practice Receptionist", user_roles)

	def test_staff_invitation_ticks_checklist_step_3(self):
		practice = _make_practice("StaffChk")
		_make_pm(practice, "Receptionist", "StaffChk")

		checklist = _get_checklist(practice)
		self.assertEqual(checklist.step_staff_invited, 1)

	# ------------------------------------------------------------------
	# 2. Patient invitation
	# ------------------------------------------------------------------

	def test_patient_invitation_creates_patient_record(self):
		practice = _make_practice("PatInv")
		pm = _make_pm(practice, "Patient", "PatInv")

		pm.reload()
		self.assertIsNotNone(pm.patient_record, "Patient record should be set after patient invitation")
		self.assertEqual(pm.status, "Sent")
		self.assertIsNone(pm.user, "Patient invitation must NOT create a User (Phase 2 scope)")

		# Patient record should exist and be scoped to this practice
		self.assertTrue(frappe.db.exists("Patient", pm.patient_record))
		patient_practice = frappe.db.get_value("Patient", pm.patient_record, "custom_practice")
		self.assertEqual(patient_practice, practice)

	def test_patient_invitation_ticks_checklist_step_4(self):
		practice = _make_practice("PatChk")
		_make_pm(practice, "Patient", "PatChk")

		checklist = _get_checklist(practice)
		self.assertEqual(checklist.step_patients_invited, 1)

	# ------------------------------------------------------------------
	# 3. Duplicate guard
	# ------------------------------------------------------------------

	def test_duplicate_email_in_same_practice_is_rejected(self):
		practice = _make_practice("DupGuard")
		_make_pm(practice, "Receptionist", "DupA")

		with self.assertRaises(frappe.ValidationError):
			# Same email, same practice — should fail
			frappe.get_doc({
				"doctype": "Practice Member",
				"practice": practice,
				"full_name": "Dup B",
				"email": "pm.test.DupA@example.com",
				"role": "Receptionist",
				"status": "Pending",
			}).insert(ignore_permissions=True)

	def test_same_email_different_practice_is_allowed(self):
		practice_a = _make_practice("DupPA")
		practice_b = _make_practice("DupPB")
		_make_pm(practice_a, "Receptionist", "CrossA")

		# Same email, different practice — should succeed
		try:
			pm_b = frappe.get_doc({
				"doctype": "Practice Member",
				"practice": practice_b,
				"full_name": "Cross B",
				"email": "pm.test.CrossA@example.com",
				"role": "Receptionist",
				"status": "Pending",
			})
			pm_b.insert(ignore_permissions=True)
		except frappe.ValidationError:
			self.fail("Same email in different practice should be allowed")

	# ------------------------------------------------------------------
	# 4. Tenant isolation (PQC)
	# ------------------------------------------------------------------

	def test_pqc_scopes_to_correct_practice(self):
		from medic_plus.api.permissions import get_practice_member_permission_query

		practice_a = _make_practice("IsoA")
		practice_b = _make_practice("IsoB")

		# Create a user linked to practice_a
		email_a = "pm.iso.a@example.com"
		if not frappe.db.exists("User", email_a):
			frappe.get_doc({
				"doctype": "User",
				"email": email_a,
				"first_name": "IsoA",
				"send_welcome_email": 0,
			}).insert(ignore_permissions=True)

		frappe.get_doc({
			"doctype": "Practice Member",
			"practice": practice_a,
			"full_name": "Iso A User",
			"email": email_a,
			"user": email_a,
			"role": "Receptionist",
			"status": "Accepted",
		}).insert(ignore_permissions=True)

		condition_a = get_practice_member_permission_query(user=email_a)
		self.assertIn(practice_a, condition_a)
		self.assertNotIn(practice_b, condition_a)
