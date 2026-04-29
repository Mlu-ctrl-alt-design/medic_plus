"""Tests for Practice role DocPerm fixtures (Issue #12).

The three custom roles shipped by medic_plus — Practice Admin, Practice Doctor,
Practice Receptionist — must be granted DocPerms on the Healthcare doctypes
Practice users actually consume (Patient, Patient Appointment, Patient
Encounter, Vital Signs, Lab Test, Healthcare Practitioner, Inpatient Record).

Without these DocPerms, role-based permission checks fire BEFORE the medic_plus
PQC runs, so a correctly-scoped Practice user gets 403 on every list/get call.

These tests use a fresh practice + user + patient triple, set the session user
to that practice user (not Administrator), and assert read access works. They
will fail until the fixture file ships and migrate runs.
"""

import frappe
from frappe.tests import IntegrationTestCase


def _suffix() -> str:
	return frappe.generate_hash(length=6)


def _make_practice(label: str) -> str:
	practice_name = f"DocPerm Practice {label}"
	if frappe.db.exists("Practice", {"practice_name": practice_name}):
		return frappe.db.get_value("Practice", {"practice_name": practice_name}, "name")
	return frappe.get_doc({
		"doctype": "Practice",
		"practice_name": practice_name,
	}).insert(ignore_permissions=True).name


def _make_user(email: str, frappe_role: str) -> str:
	if frappe.db.exists("User", email):
		return email
	frappe.get_doc({
		"doctype": "User",
		"email": email,
		"first_name": "DocPerm",
		"last_name": frappe_role.replace("Practice ", ""),
		"send_welcome_email": 0,
		"roles": [{"role": frappe_role}],
	}).insert(ignore_permissions=True)
	return email


def _make_member(practice: str, user: str, member_role: str) -> str:
	"""member_role is one of Admin / Doctor / Receptionist (Practice Member.role)."""
	existing = frappe.db.get_value(
		"Practice Member",
		{"practice": practice, "user": user},
		"name",
	)
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "Practice Member",
		"practice": practice,
		"user": user,
		"full_name": f"DocPerm {member_role}",
		"email": user,
		"role": member_role,
		"status": "Accepted",
	}).insert(ignore_permissions=True).name


def _make_patient(practice: str, label: str) -> str:
	first_name = f"DocPerm Patient {label}"
	existing = frappe.db.get_value("Patient", {"first_name": first_name}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "Patient",
		"first_name": first_name,
		"sex": "Female",
		"custom_practice": practice,
	}).insert(ignore_permissions=True).name


class TestPracticeAdminPatientAccess(IntegrationTestCase):
	"""Practice Admin must be able to list + read Patient via REST."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice = _make_practice(s)
		self.admin_email = _make_user(f"docperm.admin.{s}@test.local", "Practice Admin")
		_make_member(self.practice, self.admin_email, "Admin")
		self.patient = _make_patient(self.practice, s)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_practice_admin_can_list_patients(self):
		"""Tracer bullet: Practice Admin signs in, lists Patients via the same path the
		REST API and SPA use (frappe.client.get_list → has_permission)."""
		from frappe.client import get_list

		original = frappe.session.user
		try:
			frappe.set_user(self.admin_email)
			rows = get_list("Patient", fields=["name"], limit_page_length=10)
			self.assertIn(self.patient, [r["name"] for r in rows])
		finally:
			frappe.set_user(original)

	def test_practice_admin_cannot_see_other_practices_patients(self):
		"""PQC must still enforce tenant isolation after DocPerms unlock the role gate."""
		from frappe.client import get_list

		other_practice = _make_practice(f"other-{_suffix()}")
		other_patient = _make_patient(other_practice, f"otherp-{_suffix()}")

		original = frappe.session.user
		try:
			frappe.set_user(self.admin_email)
			rows = get_list("Patient", fields=["name"], limit_page_length=200)
			names = [r["name"] for r in rows]
			self.assertIn(self.patient, names)
			self.assertNotIn(other_patient, names)
		finally:
			frappe.set_user(original)


class TestPracticeReceptionistVitalSignsWrite(IntegrationTestCase):
	"""Practice Receptionist must be able to create Vital Signs (per matrix)."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice = _make_practice(s)
		self.recept_email = _make_user(f"docperm.recept.{s}@test.local", "Practice Receptionist")
		_make_member(self.practice, self.recept_email, "Receptionist")
		self.patient = _make_patient(self.practice, s)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_receptionist_has_create_perm_for_vital_signs(self):
		original = frappe.session.user
		try:
			frappe.set_user(self.recept_email)
			# has_permission("create") is the gate REST/SPA payloads pass through.
			self.assertTrue(frappe.has_permission("Vital Signs", "create"))
		finally:
			frappe.set_user(original)


class TestPracticeAdminEncounterReadOnly(IntegrationTestCase):
	"""Practice Admin gets read-only on Patient Encounter (per matrix)."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice = _make_practice(s)
		self.admin_email = _make_user(f"docperm.adminonly.{s}@test.local", "Practice Admin")
		_make_member(self.practice, self.admin_email, "Admin")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_admin_has_read_but_not_submit_for_patient_encounter(self):
		original = frappe.session.user
		try:
			frappe.set_user(self.admin_email)
			self.assertTrue(frappe.has_permission("Patient Encounter", "read"))
			self.assertFalse(frappe.has_permission("Patient Encounter", "submit"))
		finally:
			frappe.set_user(original)
