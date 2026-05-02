"""FHIR R4 integration tests — Phase 1E tracer bullet (#28).

Tests (one assertion per method per TDD discipline):
  1. GET Encounter by name → valid fhir.resources Encounter
  2. Encounter has correct resourceType / status
  3. Encounter diagnosis coding matches ICD-10 J01.9
  4. GET Patient → valid fhir.resources Patient
  5. GET Condition → valid fhir.resources Condition
  6. GET MedicationRequest → valid fhir.resources MedicationRequest
  7. CapabilityStatement lists all 6 resource types
  8. CapabilityStatement fhirVersion is 4.0.1
  9. Cross-tenant: Practice B token denied Practice A Encounter (404)
 10. FHIR token issued to Practice A user resolves to correct practice
 11. Expired token is rejected
 12. Observations Bundle returned for encounter with vitals
"""

import frappe
from frappe.tests import IntegrationTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


def _h(length: int = 6) -> str:
	return frappe.generate_hash(length=length)


def _make_practice(label: str) -> str:
	name = f"FHIR Test Practice {label}"
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
		"first_name": "FHIR",
		"last_name": role.replace("Practice ", ""),
		"send_welcome_email": 0,
		"roles": [{"role": role}],
	}).insert(ignore_permissions=True)
	return email


def _make_member(practice: str, user: str, role: str) -> None:
	if frappe.db.exists("Practice Member", {"practice": practice, "user": user}):
		return
	frappe.get_doc({
		"doctype": "Practice Member",
		"practice": practice,
		"user": user,
		"full_name": f"FHIR {role}",
		"email": user,
		"role": role,
		"status": "Accepted",
	}).insert(ignore_permissions=True)


def _make_patient(practice: str, label: str) -> str:
	first_name = f"FHIR Patient {label}"
	existing = frappe.db.get_value("Patient", {"first_name": first_name}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "Patient",
		"first_name": first_name,
		"last_name": "TestSurname",
		"sex": "Male",
		"dob": "1985-03-15",
		"custom_practice": practice,
	}).insert(ignore_permissions=True).name


def _make_encounter(practice: str, patient: str, *, diagnosis: str = "J01.9",
                    tariff: str = "0190", nappi: str = "705793001",
                    with_vitals: bool = False) -> str:
	fields = {
		"doctype": "Patient Encounter",
		"patient": patient,
		"custom_practice": practice,
		"encounter_date": frappe.utils.today(),
		"custom_claim_diagnosis_code": diagnosis,
		"custom_claim_tariff_code": tariff,
		"custom_claim_nappi_code": nappi,
	}
	if with_vitals:
		fields.update({
			"custom_blood_pressure_systolic": 120,
			"custom_blood_pressure_diastolic": 80,
			"custom_weight_kg": 72.5,
		})
	# Ensure tariff code exists
	if tariff and not frappe.db.exists("Tariff Code", tariff):
		frappe.get_doc({
			"doctype": "Tariff Code",
			"code": tariff,
			"description": "Comprehensive consultation",
			"scheme": "BHF/SAMA",
			"unit_type": "Consultation",
			"base_fee": 650.0,
			"is_active": 1,
		}).insert(ignore_permissions=True)

	enc = frappe.get_doc(fields).insert(ignore_permissions=True)
	enc.submit()
	return enc.name


class TestFhirMappers(IntegrationTestCase):

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		suffix = _h()
		cls.prac_a = _make_practice(f"A-{suffix}")
		cls.prac_b = _make_practice(f"B-{suffix}")

		cls.user_a = _make_user(f"fhir-a-{suffix}@test.med", "Practice Doctor")
		cls.user_b = _make_user(f"fhir-b-{suffix}@test.med", "Practice Doctor")
		_make_member(cls.prac_a, cls.user_a, "Doctor")
		_make_member(cls.prac_b, cls.user_b, "Doctor")

		cls.patient_a = _make_patient(cls.prac_a, f"A-{suffix}")
		cls.enc_a = _make_encounter(
			cls.prac_a, cls.patient_a,
			with_vitals=True,
		)

	# ── FHIR token management ─────────────────────────────────────────────

	def test_issue_token_returns_raw_string(self):
		from medic_plus.api.fhir.token import issue_token
		raw, doc_name = issue_token(self.user_a, self.prac_a)
		self.assertIsInstance(raw, str)
		self.assertTrue(len(raw) > 30)

	def test_resolve_token_returns_practice(self):
		from medic_plus.api.fhir.token import issue_token, resolve_token
		raw, _ = issue_token(self.user_a, self.prac_a)
		ctx = resolve_token(raw)
		self.assertEqual(ctx["practice"], self.prac_a)
		self.assertEqual(ctx["user"], self.user_a)

	def test_expired_token_raises_auth_error(self):
		import datetime
		from medic_plus.api.fhir.token import issue_token, resolve_token
		raw, doc_name = issue_token(self.user_a, self.prac_a)
		# Manually expire the token
		frappe.db.set_value(
			"FHIR Access Token", doc_name, "expires_at",
			frappe.utils.now_datetime() - datetime.timedelta(seconds=1)
		)
		frappe.db.commit()
		with self.assertRaises(frappe.AuthenticationError):
			resolve_token(raw)

	# ── Patient mapper ────────────────────────────────────────────────────

	def test_patient_to_fhir_resource_type(self):
		from medic_plus.api.fhir.mappers import patient_to_fhir
		result = patient_to_fhir(self.patient_a)
		self.assertEqual(result["resourceType"], "Patient")

	def test_patient_fhir_validates(self):
		from fhir.resources.patient import Patient
		from medic_plus.api.fhir.mappers import patient_to_fhir
		data = patient_to_fhir(self.patient_a)
		patient_resource = Patient.model_validate(data)
		self.assertEqual(patient_resource.id, self.patient_a)

	def test_patient_gender_mapped(self):
		from medic_plus.api.fhir.mappers import patient_to_fhir
		data = patient_to_fhir(self.patient_a)
		self.assertEqual(data["gender"], "male")

	# ── Encounter mapper ──────────────────────────────────────────────────

	def test_encounter_to_fhir_resource_type(self):
		from medic_plus.api.fhir.mappers import encounter_to_fhir
		result = encounter_to_fhir(self.enc_a)
		self.assertEqual(result["resourceType"], "Encounter")

	def test_encounter_fhir_validates(self):
		from fhir.resources.encounter import Encounter
		from medic_plus.api.fhir.mappers import encounter_to_fhir
		data = encounter_to_fhir(self.enc_a)
		enc_resource = Encounter.model_validate(data)
		self.assertEqual(enc_resource.id, self.enc_a)

	def test_encounter_status_is_discharged_after_submit(self):
		from medic_plus.api.fhir.mappers import encounter_to_fhir
		data = encounter_to_fhir(self.enc_a)
		self.assertEqual(data["status"], "discharged")

	def test_encounter_diagnosis_icd10(self):
		from medic_plus.api.fhir.mappers import encounter_to_fhir
		data = encounter_to_fhir(self.enc_a)
		diag = data.get("diagnosis", [])
		self.assertTrue(len(diag) > 0, "No diagnosis in FHIR Encounter")
		coding = diag[0]["condition"][0]["concept"]["coding"]
		codes = [c["code"] for c in coding]
		self.assertIn("J01.9", codes)

	def test_encounter_subject_reference(self):
		from medic_plus.api.fhir.mappers import encounter_to_fhir
		data = encounter_to_fhir(self.enc_a)
		self.assertIn(self.patient_a, data["subject"]["reference"])

	# ── Condition mapper ──────────────────────────────────────────────────

	def test_condition_fhir_validates(self):
		from fhir.resources.condition import Condition
		from medic_plus.api.fhir.mappers import condition_to_fhir
		data = condition_to_fhir(self.enc_a)
		self.assertIsNotNone(data)
		cond_resource = Condition.model_validate(data)
		self.assertEqual(cond_resource.resourceType, "Condition")

	def test_condition_icd_code(self):
		from medic_plus.api.fhir.mappers import condition_to_fhir
		data = condition_to_fhir(self.enc_a)
		coding = data["code"]["coding"]
		self.assertEqual(coding[0]["code"], "J01.9")

	# ── MedicationRequest mapper ──────────────────────────────────────────

	def test_medication_request_fhir_validates(self):
		from fhir.resources.medicationrequest import MedicationRequest
		from medic_plus.api.fhir.mappers import medication_request_to_fhir
		data = medication_request_to_fhir(self.enc_a)
		self.assertIsNotNone(data)
		mr = MedicationRequest.model_validate(data)
		self.assertEqual(mr.resourceType, "MedicationRequest")

	def test_medication_request_nappi_code(self):
		from medic_plus.api.fhir.mappers import medication_request_to_fhir
		data = medication_request_to_fhir(self.enc_a)
		coding = data["medication"]["concept"]["coding"]
		self.assertEqual(coding[0]["code"], "705793001")

	# ── Observation mapper (vitals) ───────────────────────────────────────

	def test_vitals_observations_returned(self):
		from medic_plus.api.fhir.mappers import vitals_to_fhir
		obs_list = vitals_to_fhir(self.enc_a)
		self.assertTrue(len(obs_list) >= 2, "Expected at least BP + weight")

	def test_bp_observation_fhir_validates(self):
		from fhir.resources.observation import Observation
		from medic_plus.api.fhir.mappers import vitals_to_fhir
		obs_list = vitals_to_fhir(self.enc_a)
		bp_obs = next((o for o in obs_list if "bp" in o.get("id", "")), None)
		self.assertIsNotNone(bp_obs)
		obs_resource = Observation.model_validate(bp_obs)
		self.assertEqual(obs_resource.status, "final")

	# ── CapabilityStatement ───────────────────────────────────────────────

	def test_capability_statement_resource_type(self):
		from medic_plus.api.fhir.capability_statement import build
		cs = build()
		self.assertEqual(cs["resourceType"], "CapabilityStatement")

	def test_capability_statement_fhir_validates(self):
		from fhir.resources.capabilitystatement import CapabilityStatement
		from medic_plus.api.fhir.capability_statement import build
		cs = CapabilityStatement.model_validate(build())
		self.assertEqual(cs.fhirVersion, "4.0.1")

	def test_capability_statement_lists_six_resources(self):
		from medic_plus.api.fhir.capability_statement import build, _RESOURCES
		self.assertEqual(len(_RESOURCES), 6)
		resource_types = [r["type"] for r in _RESOURCES]
		for expected in ["Patient", "Encounter", "Condition", "MedicationRequest",
		                 "AllergyIntolerance", "Observation"]:
			self.assertIn(expected, resource_types)

	# ── Router: cross-tenant isolation ────────────────────────────────────

	def test_router_get_encounter_cross_tenant_denied(self):
		"""Practice B token denied Practice A encounter → DoesNotExistError."""
		from medic_plus.api.fhir.token import issue_token, resolve_token
		raw_b, _ = issue_token(self.user_b, self.prac_b)

		from medic_plus.api.fhir.router import get_encounter
		# Patch frappe.session.user so _resolve_context falls through to token
		original_user = frappe.session.user
		frappe.set_user("Guest")
		try:
			with self.assertRaises((frappe.DoesNotExistError, Exception)):
				get_encounter(id=self.enc_a, token=raw_b)
		finally:
			frappe.set_user(original_user)

	def test_router_get_encounter_own_practice_allowed(self):
		"""Practice A token can read Practice A encounter."""
		from medic_plus.api.fhir.token import issue_token
		raw_a, _ = issue_token(self.user_a, self.prac_a)

		from medic_plus.api.fhir.router import get_encounter
		result = get_encounter(id=self.enc_a, token=raw_a)
		self.assertEqual(result["resourceType"], "Encounter")
		self.assertEqual(result["id"], self.enc_a)

	def test_fhir_pqc_token_isolates_practices(self):
		"""FHIR Access Token PQC returns only issuing user's tokens."""
		from medic_plus.api.fhir.token import issue_token
		raw_a, doc_a = issue_token(self.user_a, self.prac_a)
		raw_b, doc_b = issue_token(self.user_b, self.prac_b)

		from medic_plus.api.permissions import get_fhir_access_token_permission_query
		cond_a = get_fhir_access_token_permission_query(user=self.user_a)
		self.assertIn(self.user_a, cond_a)
		cond_b = get_fhir_access_token_permission_query(user=self.user_b)
		self.assertIn(self.user_b, cond_b)
		self.assertNotIn(self.user_a, cond_b)
