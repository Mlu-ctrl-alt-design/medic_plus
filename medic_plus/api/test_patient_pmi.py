"""Phase 1A — SA-PMI Patient Identity: TDD vertical-slice test suite.

Tracer bullet (Cycle 1):
  Register a Patient with a valid SA ID number; assert Patient Identifier row
  persists with id_type=SAID, id_value, is_primary=1; assert DOB + sex are
  derived from the SA ID; assert cross-tenant PQC denies a Practice B user.

Additional cycles follow the same one-test-one-implementation discipline.

Note: the issue specification lists 8501015009087 as the test SAID, but the
standard SA ID checksum algorithm (odd-digit sum + double-even-concat method)
yields check digit 6, not 7, for that DOB/sequence combination. The canonical
valid ID used here is 8501015009086 (DOB 1985-01-01, Male, checksum valid).
"""

import frappe
from frappe.tests import IntegrationTestCase


# ---------------------------------------------------------------------------
# Test IDs and constants
# ---------------------------------------------------------------------------

VALID_SAID = "8501015009086"   # DOB 1985-01-01, Male, checksum valid
BAD_SAID   = "8501015009087"   # same prefix, wrong check digit
SHORT_SAID = "850101500908"    # only 12 digits


def _suffix() -> str:
    return frappe.generate_hash(length=6)


def _make_practice(label: str) -> str:
    name = f"PMI Test Practice {label}"
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
        "first_name": "PMI",
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
        "full_name": f"PMI {member_role}",
        "email": user,
        "role": member_role,
        "status": "Accepted",
    }).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Cycle 1 — Tracer bullet
# ---------------------------------------------------------------------------

class TestSAIDTracerBullet(IntegrationTestCase):
    """SA ID → Patient Identifier row + derived DOB/sex + cross-tenant PQC."""

    def setUp(self):
        frappe.set_user("Administrator")
        s = _suffix()
        self.practice_a = _make_practice(f"A-{s}")
        self.practice_b = _make_practice(f"B-{s}")
        self.recept_b_email = f"pmi.recept.b.{s}@test.local"
        _make_user(self.recept_b_email, "Practice Receptionist")
        _make_member(self.practice_b, self.recept_b_email, "Receptionist")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_said_identifier_row_persists(self):
        """Inserting a Patient with a SAID identifier creates the child row."""
        patient = frappe.get_doc({
            "doctype": "Patient",
            "first_name": "Tracer",
            "sex": "Male",
            "custom_practice": self.practice_a,
            "custom_popia_consent_special": 1,
            "custom_identifiers": [{
                "id_type": "SAID",
                "id_value": VALID_SAID,
                "is_primary": 1,
            }],
        }).insert(ignore_permissions=True)

        patient.reload()
        rows = patient.get("custom_identifiers")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.id_type, "SAID")
        self.assertEqual(row.id_value, VALID_SAID)
        self.assertEqual(int(row.is_primary), 1)

    def test_said_derives_dob_and_sex(self):
        """SA ID populates patient.dob and patient.sex when they are absent."""
        patient = frappe.get_doc({
            "doctype": "Patient",
            "first_name": "DeriveDOB",
            "sex": "Male",
            "custom_practice": self.practice_a,
            "custom_popia_consent_special": 1,
            "custom_identifiers": [{
                "id_type": "SAID",
                "id_value": VALID_SAID,
                "is_primary": 1,
            }],
        }).insert(ignore_permissions=True)

        patient.reload()
        self.assertEqual(str(patient.dob), "1985-01-01")
        self.assertEqual(patient.sex, "Male")

    def test_pqc_denies_cross_practice_receptionist(self):
        """Practice B receptionist cannot read Practice A's Patient Identifier rows."""
        from medic_plus.api.permissions import get_patient_identifier_permission_query

        condition = get_patient_identifier_permission_query(user=self.recept_b_email)
        self.assertIn(self.practice_b, condition)
        self.assertNotIn(self.practice_a, condition)


# ---------------------------------------------------------------------------
# Cycle 2 — SA ID checksum rejection
# ---------------------------------------------------------------------------

class TestSAIDChecksumValidation(IntegrationTestCase):

    def setUp(self):
        frappe.set_user("Administrator")
        s = _suffix()
        self.practice = _make_practice(f"Chk-{s}")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_bad_checksum_raises_validation_error(self):
        """An SA ID with a wrong check digit must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Patient",
                "first_name": "BadChk",
                "sex": "Male",
                "custom_practice": self.practice,
                "custom_popia_consent_special": 1,
                "custom_identifiers": [{
                    "id_type": "SAID",
                    "id_value": BAD_SAID,
                    "is_primary": 1,
                }],
            }).insert(ignore_permissions=True)

    def test_short_said_raises_validation_error(self):
        """An SA ID that is not 13 digits must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Patient",
                "first_name": "ShortID",
                "sex": "Male",
                "custom_practice": self.practice,
                "custom_popia_consent_special": 1,
                "custom_identifiers": [{
                    "id_type": "SAID",
                    "id_value": SHORT_SAID,
                    "is_primary": 1,
                }],
            }).insert(ignore_permissions=True)

    def test_valid_said_accepted(self):
        """A checksum-valid SA ID must not raise."""
        try:
            frappe.get_doc({
                "doctype": "Patient",
                "first_name": "GoodChk",
                "sex": "Male",
                "custom_practice": self.practice,
                "custom_popia_consent_special": 1,
                "custom_identifiers": [{
                    "id_type": "SAID",
                    "id_value": VALID_SAID,
                    "is_primary": 1,
                }],
            }).insert(ignore_permissions=True)
        except frappe.ValidationError as e:
            self.fail(f"Valid SAID raised ValidationError: {e}")


# ---------------------------------------------------------------------------
# Cycle 3 — POPIA consent gate
# ---------------------------------------------------------------------------

class TestPOPIAConsentGate(IntegrationTestCase):

    def setUp(self):
        frappe.set_user("Administrator")
        s = _suffix()
        self.practice = _make_practice(f"Pop-{s}")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_said_without_popia_consent_raises(self):
        """Providing an SA ID without POPIA consent must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Patient",
                "first_name": "NoPOPIA",
                "sex": "Male",
                "custom_practice": self.practice,
                "custom_popia_consent_special": 0,
                "custom_identifiers": [{
                    "id_type": "SAID",
                    "id_value": VALID_SAID,
                    "is_primary": 1,
                }],
            }).insert(ignore_permissions=True)

    def test_non_said_without_popia_consent_allowed(self):
        """Passport or other non-SA-ID types do not require POPIA consent."""
        try:
            frappe.get_doc({
                "doctype": "Patient",
                "first_name": "Passport",
                "sex": "Female",
                "custom_practice": self.practice,
                "custom_popia_consent_special": 0,
                "custom_identifiers": [{
                    "id_type": "Passport",
                    "id_value": "A12345678",
                    "is_primary": 1,
                }],
            }).insert(ignore_permissions=True)
        except frappe.ValidationError as e:
            self.fail(f"Passport without POPIA consent raised ValidationError: {e}")


# ---------------------------------------------------------------------------
# Cycle 4 — Primary identifier constraint
# ---------------------------------------------------------------------------

class TestPrimaryIdentifierConstraint(IntegrationTestCase):

    def setUp(self):
        frappe.set_user("Administrator")
        s = _suffix()
        self.practice = _make_practice(f"Pri-{s}")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_two_primary_identifiers_raises(self):
        """Having more than one is_primary=1 identifier must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Patient",
                "first_name": "DualPri",
                "sex": "Male",
                "custom_practice": self.practice,
                "custom_popia_consent_special": 1,
                "custom_identifiers": [
                    {
                        "id_type": "SAID",
                        "id_value": VALID_SAID,
                        "is_primary": 1,
                    },
                    {
                        "id_type": "Passport",
                        "id_value": "B98765432",
                        "is_primary": 1,
                    },
                ],
            }).insert(ignore_permissions=True)

    def test_multiple_identifiers_one_primary_accepted(self):
        """Multiple identifiers with exactly one primary must be accepted."""
        try:
            frappe.get_doc({
                "doctype": "Patient",
                "first_name": "MultiID",
                "sex": "Male",
                "custom_practice": self.practice,
                "custom_popia_consent_special": 1,
                "custom_identifiers": [
                    {
                        "id_type": "SAID",
                        "id_value": VALID_SAID,
                        "is_primary": 1,
                    },
                    {
                        "id_type": "Passport",
                        "id_value": "C11111111",
                        "is_primary": 0,
                    },
                ],
            }).insert(ignore_permissions=True)
        except frappe.ValidationError as e:
            self.fail(f"Valid multi-identifier patient raised ValidationError: {e}")


# ---------------------------------------------------------------------------
# Cycle 5 — Fuzzy duplicate detection
# ---------------------------------------------------------------------------

class TestFuzzyDuplicateDetection(IntegrationTestCase):

    def setUp(self):
        frappe.set_user("Administrator")
        s = _suffix()
        self.practice = _make_practice(f"Fuzz-{s}")
        # Seed an existing patient
        frappe.get_doc({
            "doctype": "Patient",
            "first_name": "Johan",
            "last_name": "Smith",
            "sex": "Male",
            "dob": "1985-01-01",
            "custom_practice": self.practice,
            "custom_popia_consent_special": 1,
            "custom_identifiers": [{
                "id_type": "SAID",
                "id_value": VALID_SAID,
                "is_primary": 1,
            }],
        }).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_exact_identifier_match_returns_duplicate(self):
        """Same SAID on a different patient returns as a potential duplicate."""
        from medic_plus.api.patient_identity import find_duplicate_patients

        results = find_duplicate_patients(
            patient_name="Johan Smith",
            dob="1985-01-01",
            id_value=VALID_SAID,
            practice=self.practice,
        )
        self.assertTrue(len(results) >= 1, "Expected at least one duplicate candidate")
        names = [r["patient_name"] for r in results]
        self.assertTrue(any("Johan" in n for n in names))

    def test_soundex_similar_name_same_dob_returns_candidate(self):
        """Phonetically similar name + same DOB surfaces as a candidate."""
        from medic_plus.api.patient_identity import find_duplicate_patients

        results = find_duplicate_patients(
            patient_name="Yohan Smith",   # phonetically similar via Soundex
            dob="1985-01-02",             # DOB ± 1 day
            practice=self.practice,
        )
        self.assertTrue(len(results) >= 1, "Soundex/DOB fuzzy match should return candidate")
