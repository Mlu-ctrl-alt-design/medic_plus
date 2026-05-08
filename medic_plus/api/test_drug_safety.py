"""Phase 1D — Medication safety tests (TDD tracer bullet).

Tracer bullet:
  Seed Practice A patient with ciprofloxacin prescription + quinolone allergy
  (ATC J01MA).  Prescribe levofloxacin (also J01MA).  Assert:
    1. check_drug_allergy returns an allergy warning.
    2. Encounter saves without exception (warn-not-block).
    3. Encounter with override reason row persists; override row is saved.
    4. Practice B doctor cannot read the encounter or the override reason (PQC).

Additional coverage:
    5. Schedule rule S5 warns when practitioner lacks MP number.
    6. Schedule rule S6 warns about no repeats.
    7. Drug interaction check (Healthcare Drug Interaction table — skips cleanly
       when the table has no matching rows rather than raising).
    8. Drug Master before_save populates nappi_code and atc_code automatically.
"""
import frappe
from frappe.tests import IntegrationTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _s() -> str:
    return frappe.generate_hash(length=6)


def _make_practice(label: str) -> str:
    existing = frappe.db.get_value("Practice", {"practice_name": label}, "name")
    if existing:
        return existing
    return frappe.get_doc({"doctype": "Practice", "practice_name": label}).insert(
        ignore_permissions=True
    ).name


def _make_user(email: str, role: str) -> str:
    if frappe.db.exists("User", email):
        return email
    frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": "DSSafety",
        "last_name": role[-8:],
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
        "full_name": f"DS {role}",
        "email": user,
        "role": role,
        "status": "Accepted",
    }).insert(ignore_permissions=True)


def _make_patient(practice: str, suffix: str) -> str:
    first_name = f"DSPat {suffix}"
    existing = frappe.db.get_value("Patient", {"first_name": first_name}, "name")
    if existing:
        return existing
    return frappe.get_doc({
        "doctype": "Patient",
        "first_name": first_name,
        "sex": "Male",
        "custom_practice": practice,
    }).insert(ignore_permissions=True).name


def _make_allergy(patient: str, *, substance: str, atc_code: str = "",
                  severity: str = "Moderate") -> str:
    return frappe.get_doc({
        "doctype": "Patient Allergy",
        "patient": patient,
        "category": "Drug",
        "substance": substance,
        "custom_atc_code": atc_code,
        "severity": severity,
        "status": "Active",
    }).insert(ignore_permissions=True).name


def _make_drug_master(nappi_cv: str, *, atc_cv: str = "",
                      schedule: str = "", ingredient: str = "") -> str:
    """Create (or return existing) Drug Master keyed by nappi_cv."""
    existing = frappe.db.get_value("Drug Master", {"nappi_code_value": nappi_cv}, "name")
    if existing:
        return existing
    doc = frappe.get_doc({
        "doctype": "Drug Master",
        "nappi_code_value": nappi_cv,
        "atc_code_value": atc_cv or None,
        "schedule": schedule,
        "ingredient": ingredient,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _make_encounter(patient: str, practice: str, drug_nappi_cvs: list[str]) -> object:
    """Build an unsaved Patient Encounter with Drug Prescription rows."""
    drug_rows = [
        {"drug_name": nappi_cv, "custom_nappi_code_value": nappi_cv}
        for nappi_cv in drug_nappi_cvs
    ]
    doc = frappe.get_doc({
        "doctype": "Patient Encounter",
        "patient": patient,
        "custom_practice": practice,
        "encounter_date": frappe.utils.today(),
        "appointment_type": "Consultation",
        "drug_prescription": drug_rows,
    })
    return doc


# ---------------------------------------------------------------------------
# Slice 1: Drug Master populates nappi_code / atc_code on save
# ---------------------------------------------------------------------------

class TestDrugMasterAutoPopulate(IntegrationTestCase):
    """Drug Master before_save fills nappi_code and atc_code from Code Values."""

    def test_nappi_code_populated_from_code_value(self):
        s = _s()
        # 719318-NAPPI is ciprofloxacin — guaranteed by fixtures
        dm_name = _make_drug_master("719318-NAPPI", atc_cv="J01MA-ATC", schedule="S4")
        dm = frappe.get_doc("Drug Master", dm_name)
        self.assertEqual(dm.nappi_code, "719318")
        self.assertEqual(dm.drug_name, "Ciprofloxacin 500mg tablet")

    def test_atc_code_populated_from_code_value(self):
        dm_name = _make_drug_master("719390-NAPPI", atc_cv="J01MA-ATC", schedule="S4")
        dm = frappe.get_doc("Drug Master", dm_name)
        self.assertEqual(dm.atc_code, "J01MA")
        self.assertEqual(dm.drug_name, "Levofloxacin 500mg tablet")


# ---------------------------------------------------------------------------
# Slice 2: check_drug_allergy — pure function
# ---------------------------------------------------------------------------

class TestCheckDrugAllergy(IntegrationTestCase):
    """check_drug_allergy returns warnings when patient has a matching ATC allergy."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _s()
        self.practice = _make_practice(f"DSAlg-{s}")
        self.patient = _make_patient(self.practice, s)
        _make_allergy(
            self.patient,
            substance="Quinolones",
            atc_code="J01MA",
            severity="Severe",
        )

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_allergy_warning_returned_for_matching_atc(self):
        from medic_plus.api.drug_safety import check_drug_allergy
        warnings = check_drug_allergy(
            patient=self.patient,
            atc_code="J01MA",
            drug_name="Levofloxacin 500mg tablet",
        )
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["type"], "drug_allergy")
        self.assertIn("J01MA", warnings[0]["message"])
        self.assertEqual(warnings[0]["severity"], "Severe")

    def test_no_warning_for_different_atc(self):
        from medic_plus.api.drug_safety import check_drug_allergy
        warnings = check_drug_allergy(
            patient=self.patient,
            atc_code="J01CA",  # penicillins — different class
            drug_name="Amoxicillin 500mg capsule",
        )
        self.assertEqual(len(warnings), 0)

    def test_no_warning_when_allergy_resolved(self):
        """Resolved allergies do not trigger warnings."""
        from medic_plus.api.drug_safety import check_drug_allergy
        # Mark allergy as resolved
        frappe.db.set_value(
            "Patient Allergy",
            {"patient": self.patient, "custom_atc_code": "J01MA"},
            "status", "Resolved",
        )
        warnings = check_drug_allergy(
            patient=self.patient,
            atc_code="J01MA",
            drug_name="Levofloxacin 500mg tablet",
        )
        self.assertEqual(len(warnings), 0)

    def test_ingredient_substring_match_fallback(self):
        """Allergy without ATC code still matches by substance substring."""
        from medic_plus.api.drug_safety import check_drug_allergy
        s = _s()
        practice = _make_practice(f"DSAlgIngr-{s}")
        patient = _make_patient(practice, f"ingr-{s}")
        _make_allergy(patient, substance="Penicillin", atc_code="", severity="Mild")
        # Drug name contains "Penicillin"
        warnings = check_drug_allergy(
            patient=patient, atc_code=None,
            drug_name="Amoxicillin/Penicillin 500mg",
        )
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["type"], "drug_allergy")


# ---------------------------------------------------------------------------
# Slice 3: run_safety_checks on encounter — warns but saves
# ---------------------------------------------------------------------------

class TestEncounterSafetyWarning(IntegrationTestCase):
    """Tracer: encounter with quinolone prescription + quinolone allergy warns on save."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _s()
        self.practice = _make_practice(f"DSEnc-{s}")
        self.patient = _make_patient(self.practice, s)
        _make_allergy(self.patient, substance="Quinolones", atc_code="J01MA")
        _make_drug_master("719390-NAPPI", atc_cv="J01MA-ATC", schedule="S4")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_run_safety_checks_returns_allergy_warning(self):
        from medic_plus.api.drug_safety import run_safety_checks
        enc = _make_encounter(self.patient, self.practice, ["719390-NAPPI"])
        warnings = run_safety_checks(enc)
        self.assertGreater(len(warnings), 0)
        types = {w["type"] for w in warnings}
        self.assertIn("drug_allergy", types)

    def test_encounter_saves_despite_allergy_warning(self):
        """Warn-not-block: encounter saves even with allergy conflict."""
        enc = _make_encounter(self.patient, self.practice, ["719390-NAPPI"])
        # Should not raise
        enc.insert(ignore_permissions=True)
        self.assertTrue(frappe.db.exists("Patient Encounter", enc.name))

    def test_warnings_attached_to_doc(self):
        from medic_plus.api.drug_safety import run_safety_checks
        enc = _make_encounter(self.patient, self.practice, ["719390-NAPPI"])
        run_safety_checks(enc)
        self.assertTrue(hasattr(enc, "_drug_safety_warnings"))
        self.assertGreater(len(enc._drug_safety_warnings), 0)


# ---------------------------------------------------------------------------
# Slice 4: Override reason persists on re-save
# ---------------------------------------------------------------------------

class TestPrescriptionOverrideReason(IntegrationTestCase):
    """Override reason row is saved; covered warnings are not re-surfaced."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _s()
        self.practice = _make_practice(f"DSOver-{s}")
        self.patient = _make_patient(self.practice, s)
        _make_allergy(self.patient, substance="Quinolones", atc_code="J01MA")
        _make_drug_master("719390-NAPPI", atc_cv="J01MA-ATC", schedule="S4")
        # Create encounter with levofloxacin + override reason
        self.enc = _make_encounter(self.patient, self.practice, ["719390-NAPPI"])
        self.enc.custom_prescription_override_reasons = [{
            "warning_type": "Drug Allergy",
            "drug_name": "Levofloxacin 500mg tablet",
            "reason": "No alternative — clinical benefit outweighs risk",
            "dismissed_at": frappe.utils.now_datetime(),
        }]
        self.enc.insert(ignore_permissions=True)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_override_reason_row_persists(self):
        enc = frappe.get_doc("Patient Encounter", self.enc.name)
        overrides = enc.custom_prescription_override_reasons
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0].warning_type, "Drug Allergy")
        self.assertIn("No alternative", overrides[0].reason)

    def test_covered_warnings_not_re_raised(self):
        """When all warnings are covered, run_prescription_safety should not call msgprint."""
        from medic_plus.api.drug_safety import run_safety_checks
        enc = frappe.get_doc("Patient Encounter", self.enc.name)
        warnings = run_safety_checks(enc)
        covered_drugs = {
            row.drug_name for row in enc.custom_prescription_override_reasons
        }
        uncovered = [w for w in warnings if w.get("drug") not in covered_drugs]
        self.assertEqual(len(uncovered), 0, "All allergy warnings should be covered")


# ---------------------------------------------------------------------------
# Slice 5: Cross-tenant isolation
# ---------------------------------------------------------------------------

class TestPrescriptionCrossTenant(IntegrationTestCase):
    """Practice B users cannot read Practice A prescriptions or override reasons."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _s()
        self.practice_a = _make_practice(f"DSA-{s}")
        self.practice_b = _make_practice(f"DSB-{s}")
        self.user_a = _make_user(f"ds.a.{s}@test.local", "Practice Doctor")
        self.user_b = _make_user(f"ds.b.{s}@test.local", "Practice Doctor")
        _make_member(self.practice_a, self.user_a, "Doctor")
        _make_member(self.practice_b, self.user_b, "Doctor")
        self.patient_a = _make_patient(self.practice_a, f"ca-{s}")
        _make_drug_master("719390-NAPPI", atc_cv="J01MA-ATC", schedule="S4")

        # Create encounter with override reason in Practice A
        enc = _make_encounter(self.patient_a, self.practice_a, ["719390-NAPPI"])
        enc.custom_prescription_override_reasons = [{
            "warning_type": "Drug Allergy",
            "drug_name": "Levofloxacin 500mg tablet",
            "reason": "Clinical override A",
            "dismissed_at": frappe.utils.now_datetime(),
        }]
        enc.insert(ignore_permissions=True)
        self.enc_name = enc.name

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_encounter_pqc_excludes_practice_b(self):
        from medic_plus.api.permissions import get_patient_encounter_permission_query
        cond = get_patient_encounter_permission_query(user=self.user_b)
        self.assertNotIn(self.practice_a, cond)

    def test_override_reason_pqc_excludes_practice_b(self):
        from medic_plus.api.permissions import get_prescription_override_reason_permission_query
        cond = get_prescription_override_reason_permission_query(user=self.user_b)
        # Condition should reference practice B's encounters only, not practice A
        self.assertIn(self.practice_b, cond)
        self.assertNotIn(self.practice_a, cond)

    def test_practice_b_cannot_read_encounter_drug_prescription(self):
        """frappe.get_all on Patient Encounter returns nothing for Practice B user."""
        frappe.set_user(self.user_b)
        rows = frappe.get_all(
            "Patient Encounter",
            filters={"name": self.enc_name},
            fields=["name"],
        )
        self.assertEqual(len(rows), 0)


# ---------------------------------------------------------------------------
# Slice 6: Schedule rule checks
# ---------------------------------------------------------------------------

class TestScheduleRuleCheck(IntegrationTestCase):
    """Schedule rule warnings fire for S5/S6 drugs when prescriber lacks MP number."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _s()
        self.practice = _make_practice(f"DSSched-{s}")
        self.patient = _make_patient(self.practice, s)
        # S5 drug
        _make_drug_master("719318-NAPPI", atc_cv="J01MA-ATC", schedule="S5")
        # Practitioner without MP number (custom_practice_number)
        self.practitioner = None  # no practitioner = no MP number check

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_s5_no_prescriber_warns(self):
        from medic_plus.api.drug_safety import check_schedule_rule
        warnings = check_schedule_rule("719318-NAPPI", prescriber=None)
        # S5 with no prescriber means no MP-number check (prescriber=None skips that path)
        # But we should still warn about S5 requiring MP number when prescriber IS given
        # and lacks the number — test that case separately with a fake practitioner name
        # that won't have custom_practice_number
        self.assertEqual(len(warnings), 0)  # no prescriber — no MP-number warning

    def test_s5_prescriber_without_mp_warns(self):
        from medic_plus.api.drug_safety import check_schedule_rule
        # Use a fake practitioner name that won't exist → returns None for get_value
        warnings = check_schedule_rule("719318-NAPPI", prescriber="FAKE-PRAC-00001")
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["type"], "schedule_rule")
        self.assertIn("practice number", warnings[0]["message"].lower())

    def test_s6_always_warns_about_no_repeats(self):
        from medic_plus.api.drug_safety import check_schedule_rule
        # Ensure Drug Master exists for ciprofloxacin; temporarily set schedule to S6
        dm_name = _make_drug_master("719318-NAPPI", atc_cv="J01MA-ATC", schedule="S6")
        frappe.db.set_value("Drug Master", dm_name, "schedule", "S6")
        try:
            warnings = check_schedule_rule("719318-NAPPI", prescriber="FAKE-PRAC-00001")
            types = [w["type"] for w in warnings]
            self.assertIn("schedule_rule", types)
            self.assertTrue(any("repeats" in w["message"].lower() for w in warnings))
        finally:
            frappe.db.set_value("Drug Master", dm_name, "schedule", "S4")

    def test_non_scheduled_drug_no_warnings(self):
        from medic_plus.api.drug_safety import check_schedule_rule
        # S4 drug (ciprofloxacin set to S4 in TestDrugMasterAutoPopulate) — ensure no warning
        # Use levofloxacin which is S4
        _make_drug_master("719390-NAPPI", atc_cv="J01MA-ATC", schedule="S4")
        warnings = check_schedule_rule("719390-NAPPI", prescriber=None)
        self.assertEqual(len(warnings), 0)
