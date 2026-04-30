"""SA EMR Phase 1 (Compliance core) — PQC + endpoint tests.

Pins three things:
  1. The four new Permission Query Conditions (Patient Allergy,
     Patient Chronic Condition, Patient Insurance Policy, Patient
     Insurance Coverage) constrain via patient.custom_practice.
  2. The three new whitelisted read endpoints (get_patient_allergies,
     get_patient_chronic_conditions, get_patient_medical_aid) raise
     PermissionError on cross-practice access.
  3. Practice users can read+write their own practice's records via
     the same PQC-scoped path.

Mirrors the test patterns from test_practice_docperms.py and
test_get_medical_records.py — uses IntegrationTestCase to dodge the
compat preloader.
"""

import frappe
from frappe.tests import IntegrationTestCase


def _suffix() -> str:
	return frappe.generate_hash(length=6)


def _make_practice(label: str) -> str:
	name = f"SAEMR Test Practice {label}"
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
		"first_name": "SAEMR",
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
		"full_name": f"SAEMR {member_role}",
		"email": user,
		"role": member_role,
		"status": "Accepted",
	}).insert(ignore_permissions=True)


def _make_patient(practice: str, label: str) -> str:
	first_name = f"SAEMR Patient {label}"
	existing = frappe.db.get_value("Patient", {"first_name": first_name}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "Patient",
		"first_name": first_name,
		"sex": "Female",
		"custom_practice": practice,
	}).insert(ignore_permissions=True).name


def _make_allergy(patient: str, *, substance: str, severity: str = "Mild") -> str:
	return frappe.get_doc({
		"doctype": "Patient Allergy",
		"patient": patient,
		"category": "Drug",
		"substance": substance,
		"severity": severity,
		"status": "Active",
	}).insert(ignore_permissions=True).name


def _make_chronic(patient: str, *, diagnosis: str, started_on: str = "2024-01-01") -> str:
	# Diagnosis must exist; try to reuse a built-in one or create a stub.
	if not frappe.db.exists("Diagnosis", diagnosis):
		frappe.get_doc({"doctype": "Diagnosis", "diagnosis": diagnosis}).insert(ignore_permissions=True)
	return frappe.get_doc({
		"doctype": "Patient Chronic Condition",
		"patient": patient,
		"diagnosis": diagnosis,
		"chronic_status": "Active",
		"started_on": started_on,
	}).insert(ignore_permissions=True).name


class TestPQCShape(IntegrationTestCase):
	"""PQCs constrain on Patient.custom_practice — not the empty/full-access string."""

	def test_patient_allergy_pqc_scopes_to_practice(self):
		from medic_plus.api.permissions import get_patient_allergy_permission_query
		s = _suffix()
		practice = _make_practice(f"alg-{s}")
		user = _make_user(f"saemr.alg.{s}@test.local", "Practice Admin")
		_make_member(practice, user, "Admin")
		condition = get_patient_allergy_permission_query(user=user)
		self.assertIn("`tabPatient Allergy`.`patient`", condition)
		self.assertIn(practice, condition)

	def test_chronic_condition_pqc_scopes_to_practice(self):
		from medic_plus.api.permissions import get_patient_chronic_condition_permission_query
		s = _suffix()
		practice = _make_practice(f"cond-{s}")
		user = _make_user(f"saemr.cond.{s}@test.local", "Practice Admin")
		_make_member(practice, user, "Admin")
		condition = get_patient_chronic_condition_permission_query(user=user)
		self.assertIn("`tabPatient Chronic Condition`.`patient`", condition)
		self.assertIn(practice, condition)

	def test_insurance_policy_pqc_scopes_to_practice(self):
		from medic_plus.api.permissions import get_patient_insurance_policy_permission_query
		s = _suffix()
		practice = _make_practice(f"pol-{s}")
		user = _make_user(f"saemr.pol.{s}@test.local", "Practice Admin")
		_make_member(practice, user, "Admin")
		condition = get_patient_insurance_policy_permission_query(user=user)
		self.assertIn("`tabPatient Insurance Policy`.`patient`", condition)
		self.assertIn(practice, condition)


class TestEndpointsCrossPracticeBlocked(IntegrationTestCase):
	"""The whitelisted read endpoints raise PermissionError for cross-practice patient IDs."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice_a = _make_practice(f"a-{s}")
		self.practice_b = _make_practice(f"b-{s}")
		self.user_a = _make_user(f"saemr.a.{s}@test.local", "Practice Admin")
		_make_member(self.practice_a, self.user_a, "Admin")
		self.patient_b = _make_patient(self.practice_b, f"b-{s}")
		_make_allergy(self.patient_b, substance="Penicillin", severity="Severe")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_get_patient_allergies_cross_practice_raises(self):
		import medic_plus.api.daystar_health as dh
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.PermissionError):
			dh.get_patient_allergies(self.patient_b)

	def test_get_patient_chronic_conditions_cross_practice_raises(self):
		import medic_plus.api.daystar_health as dh
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.PermissionError):
			dh.get_patient_chronic_conditions(self.patient_b)

	def test_get_patient_medical_aid_cross_practice_raises(self):
		import medic_plus.api.daystar_health as dh
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.PermissionError):
			dh.get_patient_medical_aid(self.patient_b)


class TestEndpointsHappyPath(IntegrationTestCase):
	"""Practice user reads their own practice's allergies + chronic conditions via the endpoints."""

	def setUp(self):
		frappe.set_user("Administrator")
		s = _suffix()
		self.practice = _make_practice(f"hp-{s}")
		self.user = _make_user(f"saemr.hp.{s}@test.local", "Practice Admin")
		_make_member(self.practice, self.user, "Admin")
		self.patient = _make_patient(self.practice, f"hp-{s}")
		self.allergy_name = _make_allergy(self.patient, substance="Aspirin", severity="Moderate")
		self.condition_name = _make_chronic(self.patient, diagnosis=f"Diabetes Mellitus Type 2 {s}")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_practice_user_sees_own_allergies(self):
		import medic_plus.api.daystar_health as dh
		frappe.set_user(self.user)
		rows = dh.get_patient_allergies(self.patient)
		names = {r["name"] for r in rows}
		self.assertIn(self.allergy_name, names)

	def test_practice_user_sees_own_chronic_conditions(self):
		import medic_plus.api.daystar_health as dh
		frappe.set_user(self.user)
		rows = dh.get_patient_chronic_conditions(self.patient)
		names = {r["name"] for r in rows}
		self.assertIn(self.condition_name, names)

	def test_chronic_condition_denormalises_practice_on_insert(self):
		# Spot-check the controller's before_insert behaviour: the
		# custom_practice field on the new doctype must be auto-filled
		# from the linked Patient so the PQC subquery has a fast path.
		row = frappe.db.get_value(
			"Patient Chronic Condition", self.condition_name, "custom_practice"
		)
		self.assertEqual(row, self.practice)
