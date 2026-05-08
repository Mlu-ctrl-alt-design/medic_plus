"""Phase 1C — Structured SOAP Encounter + Problem List + Encounter Order: TDD suite.

Tracer bullet (Cycle 1):
  Create a Patient Encounter for a Practice A patient with SOAP fields
  (chief_complaint, subjective, objective, assessment + ICD-10 code, plan),
  one Examination Finding row (body_part=Chest, finding=clear breath sounds),
  one Encounter Order row (Lab / Full Blood Count).  Submit.  Assert:
  - All SOAP fields persist on the submitted encounter.
  - Examination Finding child row persists with correct body_part + finding.
  - Encounter Order child row persists with status=Ordered after submit.
  - A Patient Problem List record is created for the patient carrying the
    assessment ICD-10 code and status=Active.
  - Practice B doctor cannot read the encounter (PQC blocks it).
  - Practice B doctor cannot read the Patient Problem List row.

Additional cycles follow the same one-test-one-implementation discipline.

IGNORE_TEST_RECORD_DEPENDENCIES stops the test framework traversing into
ERPNext Company/Healthcare Practitioner test modules (see CLAUDE.md).
"""

import frappe
from frappe.tests import IntegrationTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _suffix() -> str:
    return frappe.generate_hash(length=6)


def _make_practice(label: str) -> str:
    name = f"SOAP Test Practice {label}"
    existing = frappe.db.get_value("Practice", {"practice_name": name}, "name")
    if existing:
        return existing
    return frappe.get_doc({
        "doctype": "Practice",
        "practice_name": name,
    }).insert(ignore_permissions=True).name


def _make_user(email: str, frappe_role: str) -> str:
    if frappe.db.exists("User", email):
        return email
    frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": "SOAP",
        "last_name": frappe_role.replace("Practice ", ""),
        "send_welcome_email": 0,
        "roles": [{"role": frappe_role}],
    }).insert(ignore_permissions=True)
    return email


def _make_member(practice: str, user: str, member_role: str) -> None:
    if frappe.db.exists("Practice Member", {"practice": practice, "user": user}):
        return
    frappe.get_doc({
        "doctype": "Practice Member",
        "practice": practice,
        "user": user,
        "full_name": f"SOAP {member_role}",
        "email": user,
        "role": member_role,
        "status": "Accepted",
    }).insert(ignore_permissions=True)


def _make_patient(practice: str, label: str) -> str:
    first_name = f"SOAP Patient {label}"
    existing = frappe.db.get_value("Patient", {"first_name": first_name}, "name")
    if existing:
        return existing
    return frappe.get_doc({
        "doctype": "Patient",
        "first_name": first_name,
        "sex": "Female",
        "custom_practice": practice,
    }).insert(ignore_permissions=True).name


def _get_seed_icd10_code() -> str:
    """Return any ICD-10-ZA code from the terminology seed (Phase 1B)."""
    row = frappe.db.get_value(
        "Code Value", {"code_system": "ICD-10-ZA"}, ["name", "code"], as_dict=True
    )
    if not row:
        frappe.throw("No ICD-10-ZA seed data found — Phase 1B fixture must be loaded")
    return row.name


# ---------------------------------------------------------------------------
# Cycle 1 — Tracer bullet
# ---------------------------------------------------------------------------

class TestSOAPEncounterTracer(IntegrationTestCase):
    """SOAP fields + Examination Finding + Encounter Order + Problem List end-to-end."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _suffix()
        self.practice_a = _make_practice(f"A-{s}")
        self.practice_b = _make_practice(f"B-{s}")
        self.doctor_b_email = f"soap.doctor.b.{s}@test.local"
        _make_user(self.doctor_b_email, "Practice Doctor")
        _make_member(self.practice_b, self.doctor_b_email, "Doctor")
        self.patient = _make_patient(self.practice_a, f"A-{s}")
        self.icd10_code = _get_seed_icd10_code()

    def tearDown(self):
        frappe.set_user("Administrator")

    def _make_encounter(self):
        """Create and return a submitted Patient Encounter with all SOAP sections."""
        enc = frappe.get_doc({
            "doctype": "Patient Encounter",
            "patient": self.patient,
            "custom_practice": self.practice_a,
            "encounter_date": frappe.utils.today(),
            "encounter_time": "09:00:00",
            # SOAP fields
            "custom_chief_complaint": "Cough and fever for 3 days",
            "custom_hopi": "Patient reports productive cough, fever 38.5°C since Monday.",
            "custom_subjective": "Productive cough, fever, mild dyspnoea on exertion.",
            "custom_objective": "Temp 38.5°C, RR 22, O2 sat 97%. Chest: clear breath sounds bilaterally.",
            "custom_assessment_text": "Community-acquired pneumonia",
            "custom_assessment_code": self.icd10_code,
            "custom_plan": "Amoxicillin 500mg TDS x 5 days. Follow up in 1 week.",
            # Examination Findings child table
            "custom_examination_findings": [{
                "body_system": "Respiratory",
                "body_part": "Chest",
                "finding": "Clear breath sounds bilaterally",
            }],
            # Encounter Orders child table (already exists)
            "custom_encounter_orders": [{
                "order_type": "Lab",
                "order_name": "Full Blood Count",
                "status": "Draft",
            }],
        })
        enc.flags.ignore_mandatory = True
        enc.insert(ignore_permissions=True)
        enc.submit()
        enc.reload()
        return enc

    def test_soap_fields_persist_on_submit(self):
        """All SOAP text fields survive insert+submit and reload."""
        enc = self._make_encounter()
        self.assertEqual(enc.custom_chief_complaint, "Cough and fever for 3 days")
        self.assertEqual(enc.custom_subjective, "Productive cough, fever, mild dyspnoea on exertion.")
        self.assertIn("38.5", enc.custom_objective)
        self.assertEqual(enc.custom_assessment_text, "Community-acquired pneumonia")
        self.assertEqual(enc.custom_assessment_code, self.icd10_code)
        self.assertIn("Amoxicillin", enc.custom_plan)

    def test_examination_finding_row_persists(self):
        """Examination Finding child row retains body_part and finding after submit."""
        enc = self._make_encounter()
        rows = enc.get("custom_examination_findings") or []
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.body_part, "Chest")
        self.assertEqual(row.body_system, "Respiratory")
        self.assertIn("clear breath sounds", row.finding.lower())

    def test_encounter_order_row_persists(self):
        """Encounter Order child row persists with order_type=Lab and status updated to Ordered."""
        enc = self._make_encounter()
        orders = enc.get("custom_encounter_orders") or []
        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order.order_type, "Lab")
        self.assertEqual(order.order_name, "Full Blood Count")
        self.assertEqual(order.status, "Ordered")

    def test_patient_problem_list_created_on_submit(self):
        """Submitting an encounter with an ICD-10 assessment_code creates a Patient Problem List row."""
        enc = self._make_encounter()
        problem = frappe.db.get_value(
            "Patient Problem List",
            {"patient": self.patient, "icd10_code": self.icd10_code},
            ["name", "status", "custom_practice"],
            as_dict=True,
        )
        self.assertIsNotNone(problem, "Patient Problem List row must be created on encounter submit")
        self.assertEqual(problem.status, "Active")
        self.assertEqual(problem.custom_practice, self.practice_a)

    def test_practice_b_cannot_read_encounter(self):
        """Practice B doctor's PQC blocks reading Practice A's encounter."""
        from medic_plus.api.permissions import get_patient_encounter_permission_query
        self._make_encounter()
        condition = get_patient_encounter_permission_query(user=self.doctor_b_email)
        self.assertIn(self.practice_b, condition)
        self.assertNotIn(self.practice_a, condition)

    def test_practice_b_cannot_read_problem_list(self):
        """Practice B doctor's PQC blocks reading Practice A's Patient Problem List."""
        from medic_plus.api.permissions import get_patient_problem_list_permission_query
        self._make_encounter()
        condition = get_patient_problem_list_permission_query(user=self.doctor_b_email)
        self.assertIn(self.practice_b, condition)
        self.assertNotIn(self.practice_a, condition)


# ---------------------------------------------------------------------------
# Cycle 2 — PQC shape tests
# ---------------------------------------------------------------------------

class TestSOAPPQCShape(IntegrationTestCase):
    """PQCs for Patient Problem List constrain via patient.custom_practice."""

    def test_patient_problem_list_pqc_scopes_to_practice(self):
        from medic_plus.api.permissions import get_patient_problem_list_permission_query
        s = _suffix()
        practice = _make_practice(f"ppl-{s}")
        user = _make_user(f"soap.ppl.{s}@test.local", "Practice Admin")
        _make_member(practice, user, "Admin")
        condition = get_patient_problem_list_permission_query(user=user)
        self.assertIn("`tabPatient Problem List`", condition)
        self.assertIn(practice, condition)

    def test_platform_admin_gets_unrestricted_ppl_pqc(self):
        from medic_plus.api.permissions import get_patient_problem_list_permission_query
        condition = get_patient_problem_list_permission_query(user="Administrator")
        self.assertEqual(condition, "")

    def test_orphan_user_gets_1_eq_0_ppl_pqc(self):
        from medic_plus.api.permissions import get_patient_problem_list_permission_query
        s = _suffix()
        orphan = _make_user(f"soap.orphan.{s}@test.local", "Practice Doctor")
        condition = get_patient_problem_list_permission_query(user=orphan)
        self.assertEqual(condition, "1=0")


# ---------------------------------------------------------------------------
# Cycle 3 — Problem List upsert idempotency
# ---------------------------------------------------------------------------

class TestProblemListUpsert(IntegrationTestCase):
    """Repeated submits on different encounters don't duplicate Problem List rows."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _suffix()
        self.practice = _make_practice(f"Ups-{s}")
        self.patient = _make_patient(self.practice, f"Ups-{s}")
        self.icd10_code = _get_seed_icd10_code()

    def tearDown(self):
        frappe.set_user("Administrator")

    def _submit_encounter(self):
        enc = frappe.get_doc({
            "doctype": "Patient Encounter",
            "patient": self.patient,
            "custom_practice": self.practice,
            "encounter_date": frappe.utils.today(),
            "encounter_time": "10:00:00",
            "custom_chief_complaint": "Follow up",
            "custom_assessment_code": self.icd10_code,
        })
        enc.flags.ignore_mandatory = True
        enc.insert(ignore_permissions=True)
        enc.submit()
        return enc

    def test_second_encounter_with_same_code_does_not_duplicate_problem(self):
        """Two encounters with the same ICD-10 code produce exactly one Problem List row."""
        self._submit_encounter()
        self._submit_encounter()
        count = frappe.db.count(
            "Patient Problem List",
            {"patient": self.patient, "icd10_code": self.icd10_code},
        )
        self.assertEqual(count, 1, "Idempotent upsert must not create duplicate Problem List rows")


# ---------------------------------------------------------------------------
# Cycle 4 — POPIA-safe encounter payload
# ---------------------------------------------------------------------------

class TestEncounterPayloadPOPIA(IntegrationTestCase):
    """get_encounter_detail endpoint returns POPIA-safe payload (no SA ID)."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _suffix()
        self.practice = _make_practice(f"Enc-{s}")
        self.user = _make_user(f"soap.enc.{s}@test.local", "Practice Admin")
        _make_member(self.practice, self.user, "Admin")
        self.patient = _make_patient(self.practice, f"Enc-{s}")
        icd10 = _get_seed_icd10_code()
        enc = frappe.get_doc({
            "doctype": "Patient Encounter",
            "patient": self.patient,
            "custom_practice": self.practice,
            "encounter_date": frappe.utils.today(),
            "encounter_time": "11:00:00",
            "custom_chief_complaint": "Headache",
            "custom_assessment_code": icd10,
        })
        enc.flags.ignore_mandatory = True
        enc.insert(ignore_permissions=True)
        enc.submit()
        self.encounter_name = enc.name

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_get_encounter_detail_happy_path(self):
        """get_encounter_detail returns encounter fields + problem list + orders."""
        from medic_plus.api.daystar_health import get_encounter_detail
        frappe.set_user(self.user)
        payload = get_encounter_detail(self.encounter_name)
        self.assertIn("encounter", payload)
        self.assertIn("problem_list", payload)
        self.assertIn("orders", payload)
        enc = payload["encounter"]
        self.assertNotIn("custom_sa_id_number", enc)

    def test_get_encounter_detail_cross_practice_blocked(self):
        """get_encounter_detail raises PermissionError for a cross-practice caller."""
        s = _suffix()
        practice_b = _make_practice(f"EncB-{s}")
        user_b = _make_user(f"soap.encb.{s}@test.local", "Practice Admin")
        _make_member(practice_b, user_b, "Admin")
        from medic_plus.api.daystar_health import get_encounter_detail
        frappe.set_user(user_b)
        with self.assertRaises(frappe.PermissionError):
            get_encounter_detail(self.encounter_name)
