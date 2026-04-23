"""Integration tests for the practice invitation API."""

import random

import frappe
from frappe.tests.utils import FrappeTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


def _suffix() -> str:
	return frappe.generate_hash(length=6)


def _make_practice(name_suffix: str) -> str:
	practice_name = f"Inv Practice {name_suffix}"
	if frappe.db.exists("Practice", {"practice_name": practice_name}):
		return frappe.db.get_value("Practice", {"practice_name": practice_name}, "name")
	doc = frappe.get_doc({
		"doctype": "Practice",
		"practice_name": practice_name,
	}).insert(ignore_permissions=True)
	return doc.name


class TestInviteStaff(FrappeTestCase):
	"""invite_staff requires Practice Admin (or platform admin) and creates User + Member."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice = _make_practice(s)
		self.invitee = f"invitee.{s}@test.local"
		self.invitee_mobile = "082" + "".join(str(random.randint(0, 9)) for _ in range(7))

	def tearDown(self):
		frappe.db.rollback()

	def test_administrator_can_invite_receptionist(self):
		from medic_plus.api.invitations import invite_staff
		result = invite_staff(
			practice=self.practice,
			email=self.invitee,
			full_name="Recep Test",
			role="Receptionist",
			mobile=self.invitee_mobile,
		)
		self.assertEqual(result["user"], self.invitee)
		self.assertTrue(frappe.db.exists("User", self.invitee))
		self.assertTrue(
			frappe.db.exists("Practice Member", {
				"practice": self.practice,
				"user": self.invitee,
				"role": "Receptionist",
			})
		)
		# Receptionist invites do NOT spin up a Healthcare Practitioner row.
		self.assertIsNone(result["practitioner"])
		# Frappe role applied
		user = frappe.get_doc("User", self.invitee)
		role_names = {r.role for r in user.roles}
		self.assertIn("Practice Receptionist", role_names)

	def test_doctor_invite_creates_practitioner(self):
		from medic_plus.api.invitations import invite_staff
		result = invite_staff(
			practice=self.practice,
			email=self.invitee,
			full_name="Doc Test",
			role="Doctor",
			mobile=self.invitee_mobile,
			hpcsa_number="MP78901",
			practice_number="9876543",
		)
		self.assertTrue(result["practitioner"], "practitioner not created for Doctor invite")
		self.assertTrue(frappe.db.exists("Healthcare Practitioner", result["practitioner"]))
		user = frappe.get_doc("User", self.invitee)
		role_names = {r.role for r in user.roles}
		self.assertIn("Practice Doctor", role_names)

	def test_doctor_invite_requires_hpcsa(self):
		from medic_plus.api.invitations import invite_staff
		with self.assertRaises(frappe.ValidationError):
			invite_staff(
				practice=self.practice,
				email=self.invitee,
				full_name="Doc No Reg",
				role="Doctor",
				mobile=self.invitee_mobile,
				# no hpcsa_number / practice_number
			)

	def test_duplicate_member_rejected(self):
		from medic_plus.api.invitations import invite_staff
		invite_staff(
			practice=self.practice,
			email=self.invitee,
			full_name="First Add",
			role="Receptionist",
			mobile=self.invitee_mobile,
		)
		with self.assertRaises(frappe.ValidationError):
			invite_staff(
				practice=self.practice,
				email=self.invitee,
				full_name="Second Add",
				role="Doctor",
				mobile=self.invitee_mobile,
				hpcsa_number="MP00001",
				practice_number="0000001",
			)

	def test_non_admin_cannot_invite(self):
		from medic_plus.api.invitations import invite_staff
		# Make a throwaway user and switch to them — they have no roles on this
		# practice, so the auth check should reject.
		non_admin_email = f"outsider.{_suffix()}@test.local"
		frappe.get_doc({
			"doctype": "User",
			"email": non_admin_email,
			"first_name": "Outsider",
			"send_welcome_email": 0,
		}).insert(ignore_permissions=True)
		original_user = frappe.session.user
		try:
			frappe.set_user(non_admin_email)
			with self.assertRaises(frappe.PermissionError):
				invite_staff(
					practice=self.practice,
					email=self.invitee,
					full_name="Should Fail",
					role="Receptionist",
					mobile=self.invitee_mobile,
				)
		finally:
			frappe.set_user(original_user)


class TestInviteStaffBulk(FrappeTestCase):
	"""invite_staff_bulk parses CSV and routes each row through invite_staff."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice = _make_practice(s)
		self.s = s

	def tearDown(self):
		frappe.db.rollback()

	def _csv(self, rows: list[list[str]]) -> str:
		header = "email,full_name,role,mobile,hpcsa_number,practice_number"
		lines = [header] + [",".join(r) for r in rows]
		return "\n".join(lines) + "\n"

	def test_bulk_happy_path(self):
		from medic_plus.api.invitations import invite_staff_bulk
		csv = self._csv([
			[f"r1.{self.s}@test.local", "Recep One", "Receptionist",
			 "082" + "".join(str(random.randint(0, 9)) for _ in range(7)), "", ""],
			[f"d1.{self.s}@test.local", "Dr Two", "Doctor",
			 "082" + "".join(str(random.randint(0, 9)) for _ in range(7)),
			 "MP10000", "1100001"],
		])
		result = invite_staff_bulk(practice=self.practice, csv_data=csv)
		self.assertEqual(len(result["succeeded"]), 2)
		self.assertEqual(len(result["failed"]), 0)
		self.assertTrue(frappe.db.exists("User", f"r1.{self.s}@test.local"))
		self.assertTrue(frappe.db.exists("User", f"d1.{self.s}@test.local"))

	def test_bulk_partial_failure_isolates_rows(self):
		"""A bad row shouldn't roll back good rows."""
		from medic_plus.api.invitations import invite_staff_bulk
		csv = self._csv([
			# Good
			[f"r2.{self.s}@test.local", "Good Recep", "Receptionist",
			 "082" + "".join(str(random.randint(0, 9)) for _ in range(7)), "", ""],
			# Bad: doctor without HPCSA
			[f"d2.{self.s}@test.local", "Bad Doc", "Doctor", "", "", ""],
			# Good
			[f"r3.{self.s}@test.local", "Another Recep", "Receptionist",
			 "082" + "".join(str(random.randint(0, 9)) for _ in range(7)), "", ""],
		])
		result = invite_staff_bulk(practice=self.practice, csv_data=csv)
		self.assertEqual(len(result["succeeded"]), 2)
		self.assertEqual(len(result["failed"]), 1)
		self.assertEqual(result["failed"][0]["row"], 3)  # 2nd data row, line 3
		self.assertTrue(frappe.db.exists("User", f"r2.{self.s}@test.local"))
		self.assertFalse(frappe.db.exists("User", f"d2.{self.s}@test.local"))
		self.assertTrue(frappe.db.exists("User", f"r3.{self.s}@test.local"))

	def test_bulk_missing_columns_rejected(self):
		from medic_plus.api.invitations import invite_staff_bulk
		bad_csv = "email,full_name\na@b.com,Name\n"  # no role column
		with self.assertRaises(frappe.ValidationError):
			invite_staff_bulk(practice=self.practice, csv_data=bad_csv)

	def test_bulk_blank_lines_skipped(self):
		from medic_plus.api.invitations import invite_staff_bulk
		csv = (
			"email,full_name,role,mobile,hpcsa_number,practice_number\n"
			f"r4.{self.s}@test.local,Solo Recep,Receptionist,082"
			+ "".join(str(random.randint(0, 9)) for _ in range(7))
			+ ",,\n"
			",,,,,\n"  # blank
			"\n"
		)
		result = invite_staff_bulk(practice=self.practice, csv_data=csv)
		self.assertEqual(len(result["succeeded"]), 1)
		self.assertEqual(len(result["failed"]), 0)


class TestPatientPracticeStamping(FrappeTestCase):
	"""Patient before_insert auto-stamps custom_practice from session user.

	Covers the Data Import path indirectly: Frappe's Data Import calls
	frappe.get_doc(...).insert() per row, which fires before_insert hooks —
	so this test guards the same code path that bulk patient CSV upload uses.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice = _make_practice(s)
		self.staff_email = f"staff.{s}@test.local"
		self.staff_mobile = "082" + "".join(str(random.randint(0, 9)) for _ in range(7))
		# Set up a Practice Member so the staff user has a practice
		from medic_plus.api.invitations import invite_staff
		invite_staff(
			practice=self.practice,
			email=self.staff_email,
			full_name="Stamp Tester",
			role="Receptionist",
			mobile=self.staff_mobile,
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_patient_insert_stamps_custom_practice(self):
		# Simulate a patient row inserted by the staff user (e.g. through
		# Data Import). The before_insert hook should populate custom_practice.
		original_user = frappe.session.user
		try:
			frappe.set_user(self.staff_email)
			patient = frappe.get_doc({
				"doctype": "Patient",
				"first_name": "Stamp",
				"last_name": "Tested",
				"sex": "Female",
			}).insert(ignore_permissions=True)
			self.assertEqual(patient.custom_practice, self.practice)
		finally:
			frappe.set_user(original_user)


class TestPractitionerSchedulePQC(FrappeTestCase):
	"""Practitioner Schedule PQC scopes by practitioner ∈ practice members."""

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_admin_sees_all(self):
		from medic_plus.api.permissions import get_practitioner_schedule_permission_query
		# Administrator is platform admin — empty filter (no scoping).
		condition = get_practitioner_schedule_permission_query(user="Administrator")
		self.assertEqual(condition, "")

	def test_unscoped_user_sees_nothing(self):
		from medic_plus.api.permissions import get_practitioner_schedule_permission_query
		nobody = f"nobody.{_suffix()}@test.local"
		frappe.get_doc({
			"doctype": "User",
			"email": nobody,
			"first_name": "Nobody",
			"send_welcome_email": 0,
			"roles": [{"role": "Practice Receptionist"}],
		}).insert(ignore_permissions=True)
		condition = get_practitioner_schedule_permission_query(user=nobody)
		self.assertEqual(condition, "1=0")
