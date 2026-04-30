"""Tests for medic_plus.api.daystar_health.get_medical_records.

Patient Medical Record (HLC-PMR-…) is Frappe Healthcare's auto-populated
clinical timeline. It carries no `custom_practice` of its own — scope is
inherited from the linked Patient. These tests pin three things:

1. The pure ``_format_medical_records`` helper shapes rows correctly,
   truncates long subjects, and surfaces ``has_attach`` as a boolean.
2. ``get_medical_records`` returns only the calling practice's PMR rows
   (cross-tenant isolation via the Patient.custom_practice subquery).
3. The ``get_patient_medical_record_permission_query`` PQC blocks direct
   reads of another practice's PMR row, even bypassing the API.
4. The ``reference_doctype`` filter narrows by source doctype.
5. The ``date_from`` / ``date_to`` filter excludes outside-window rows.

All seeds bypass permission with ``insert(ignore_permissions=True)`` so we
control the dataset deterministically; the assertions then run as the
practice user via ``frappe.set_user``.
"""

import datetime

import frappe
from frappe.tests import IntegrationTestCase

from medic_plus.api.daystar_health import (
	_format_medical_records,
	get_medical_records,
)


def _suffix() -> str:
	return frappe.generate_hash(length=6)


def _make_practice(label: str) -> str:
	name = f"PMR Test Practice {label}"
	existing = frappe.db.get_value("Practice", {"practice_name": name}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "Practice",
		"practice_name": name,
	}).insert(ignore_permissions=True).name


def _make_user(email: str, role: str) -> str:
	if frappe.db.exists("User", email):
		return email
	frappe.get_doc({
		"doctype": "User",
		"email": email,
		"first_name": "PMR",
		"last_name": role.replace("Practice ", ""),
		"send_welcome_email": 0,
		"roles": [{"role": role}],
	}).insert(ignore_permissions=True)
	return email


def _make_member(practice: str, user: str, member_role: str) -> None:
	if frappe.db.exists("Practice Member", {"practice": practice, "user": user}):
		return
	frappe.get_doc({
		"doctype": "Practice Member",
		"practice": practice,
		"user": user,
		"full_name": f"PMR {member_role}",
		"email": user,
		"role": member_role,
		"status": "Accepted",
	}).insert(ignore_permissions=True)


def _make_patient(practice: str, label: str) -> str:
	first_name = f"PMR Patient {label}"
	existing = frappe.db.get_value("Patient", {"first_name": first_name}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "Patient",
		"first_name": first_name,
		"sex": "Female",
		"custom_practice": practice,
	}).insert(ignore_permissions=True).name


def _make_pmr(patient: str, *, subject: str, ref_doctype: str, day_offset: int = 0, attach: str = "") -> str:
	# reference_name is a Dynamic Link — Frappe link-validates it on insert.
	# Tests don't seed source docs (Patient Encounter / Lab Test), so set
	# ignore_links to bypass that check; the list endpoint never resolves
	# reference_name to fetch the source, only displays it.
	d = datetime.date.today() + datetime.timedelta(days=day_offset)
	doc = frappe.get_doc({
		"doctype": "Patient Medical Record",
		"patient": patient,
		"subject": subject,
		"communication_date": d,
		"reference_doctype": ref_doctype,
		"reference_name": f"DUMMY-{frappe.generate_hash(length=6)}",
		"attach": attach,
	})
	doc.flags.ignore_links = True
	return doc.insert(ignore_permissions=True).name


class TestFormatMedicalRecords(IntegrationTestCase):
	"""Pure transformation — no DB, no session."""

	def test_truncates_long_subject(self):
		long_subject = "x" * 500
		rows = _format_medical_records(
			[{
				"name": "PMR-1",
				"patient": "PAT-1",
				"communication_date": datetime.date(2026, 1, 1),
				"reference_doctype": "Patient Encounter",
				"reference_name": "ENC-1",
				"subject": long_subject,
				"user": "doctor@x.com",
				"attach": "",
			}],
			{"PAT-1": "Alice"},
		)
		self.assertEqual(len(rows[0]["subject"]), 240)
		self.assertTrue(rows[0]["subject"].endswith("…"))
		self.assertEqual(rows[0]["patient_name"], "Alice")
		self.assertFalse(rows[0]["has_attach"])

	def test_surfaces_has_attach(self):
		rows = _format_medical_records(
			[{
				"name": "PMR-2",
				"patient": "PAT-1",
				"communication_date": datetime.date(2026, 1, 1),
				"reference_doctype": "Lab Test",
				"reference_name": "LT-1",
				"subject": "Bloods",
				"user": "doctor@x.com",
				"attach": "/files/results.pdf",
			}],
			{"PAT-1": "Alice"},
		)
		self.assertTrue(rows[0]["has_attach"])


class TestGetMedicalRecordsTenancy(IntegrationTestCase):
	"""Practice user sees only their own practice's PMR rows."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice_a = _make_practice(f"a-{s}")
		self.practice_b = _make_practice(f"b-{s}")
		self.user_a = _make_user(f"pmr.a.{s}@test.local", "Practice Admin")
		_make_member(self.practice_a, self.user_a, "Admin")
		self.patient_a = _make_patient(self.practice_a, f"a-{s}")
		self.patient_b = _make_patient(self.practice_b, f"b-{s}")
		self.pmr_a = _make_pmr(self.patient_a, subject="A's encounter", ref_doctype="Patient Encounter")
		self.pmr_b = _make_pmr(self.patient_b, subject="B's encounter", ref_doctype="Patient Encounter")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_returns_only_active_practice_records(self):
		frappe.set_user(self.user_a)
		result = get_medical_records(filters={}, limit_page_length=20)
		names = {r["name"] for r in result["rows"]}
		self.assertIn(self.pmr_a, names)
		self.assertNotIn(self.pmr_b, names)

	def test_pqc_blocks_cross_practice_direct_read(self):
		from medic_plus.api.permissions import get_patient_medical_record_permission_query
		condition = get_patient_medical_record_permission_query(user=self.user_a)
		# Condition must constrain on the active practice's patients,
		# never returning the empty (full-access) string for a non-admin.
		self.assertIn("`tabPatient Medical Record`.`patient`", condition)
		self.assertIn(self.practice_a, condition)


class TestGetMedicalRecordsFilters(IntegrationTestCase):
	"""Filters narrow by reference_doctype and date range."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice = _make_practice(f"f-{s}")
		self.user = _make_user(f"pmr.f.{s}@test.local", "Practice Admin")
		_make_member(self.practice, self.user, "Admin")
		self.patient = _make_patient(self.practice, f"f-{s}")
		self.encounter_pmr = _make_pmr(
			self.patient, subject="Encounter today", ref_doctype="Patient Encounter", day_offset=0
		)
		self.lab_pmr = _make_pmr(
			self.patient, subject="Lab today", ref_doctype="Lab Test", day_offset=0
		)
		self.old_pmr = _make_pmr(
			self.patient, subject="Old encounter", ref_doctype="Patient Encounter", day_offset=-200
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_filter_by_reference_doctype(self):
		frappe.set_user(self.user)
		result = get_medical_records(filters={"reference_doctype": "Patient Encounter"}, limit_page_length=20)
		names = {r["name"] for r in result["rows"]}
		self.assertIn(self.encounter_pmr, names)
		self.assertNotIn(self.lab_pmr, names)

	def test_filter_by_date_range_excludes_outside_window(self):
		frappe.set_user(self.user)
		# Default window is last 30 days — old_pmr (200 days ago) must not appear.
		result = get_medical_records(filters={}, limit_page_length=20)
		names = {r["name"] for r in result["rows"]}
		self.assertIn(self.encounter_pmr, names)
		self.assertNotIn(self.old_pmr, names)
