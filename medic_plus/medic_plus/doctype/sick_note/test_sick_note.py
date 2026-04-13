"""
Tests for Sick Note PQC patient isolation.

Uses unittest.mock to patch DB calls — no document creation, no ERPNext
test-record traversal. Inherits from plain unittest.TestCase (not
FrappeTestCase) so the Frappe test-record dependency scanner never runs,
which prevents the BootStrapTestData import-time crash in erpnext.tests.utils.
"""

import unittest
from unittest.mock import patch

from medic_plus.api.permissions import (
    get_patient_appointment_permission_query,
    get_patient_permission_query,
    get_sick_note_permission_query,
)


class TestSickNotePQCPatientIsolation(unittest.TestCase):
    """PQC isolation tests — all DB calls are mocked; nothing is written to DB."""

    # ------------------------------------------------------------------
    # Sick Note PQC
    # ------------------------------------------------------------------

    def test_patient_sick_note_pqc_scopes_to_own_record(self):
        """Patient role → PQC uses patient name, not practice."""
        with patch("medic_plus.api.permissions.frappe.get_roles", return_value=["Patient"]), \
             patch("medic_plus.api.permissions.frappe.db.get_value", return_value="PAT-00001"):
            condition = get_sick_note_permission_query(user="patient@example.test")

        self.assertIn("`tabSick Note`.`patient`", condition)
        self.assertIn("PAT-00001", condition)
        self.assertNotIn("`tabSick Note`.`practice`", condition)

    def test_patient_sick_note_pqc_no_record_returns_1_0(self):
        """Patient with no Patient record → PQC returns '1=0'."""
        with patch("medic_plus.api.permissions.frappe.get_roles", return_value=["Patient"]), \
             patch("medic_plus.api.permissions.frappe.db.get_value", return_value=None):
            condition = get_sick_note_permission_query(user="orphan@example.test")

        self.assertEqual(condition, "1=0")

    def test_practice_doctor_sick_note_pqc_uses_practice(self):
        """Practice Doctor role → PQC scopes by practice, not by patient."""
        with patch("medic_plus.api.permissions.frappe.get_roles", return_value=["Practice Doctor"]), \
             patch("medic_plus.api.permissions.frappe.db.get_value", return_value="PRAC-00001"):
            condition = get_sick_note_permission_query(user="doctor@example.test")

        self.assertIn("`tabSick Note`.`practice`", condition)
        self.assertIn("PRAC-00001", condition)
        self.assertNotIn("`tabSick Note`.`patient`", condition)

    def test_practice_doctor_no_practice_returns_1_0(self):
        """Practice Doctor with no Practice Member record → '1=0'."""
        with patch("medic_plus.api.permissions.frappe.get_roles", return_value=["Practice Doctor"]), \
             patch("medic_plus.api.permissions.frappe.db.get_value", return_value=None):
            condition = get_sick_note_permission_query(user="orphan_doctor@example.test")

        self.assertEqual(condition, "1=0")

    def test_platform_admin_sick_note_pqc_returns_empty(self):
        """Healthcare Administrator → unrestricted access (empty string)."""
        with patch("medic_plus.api.permissions.frappe.get_roles",
                   return_value=["Healthcare Administrator"]):
            condition = get_sick_note_permission_query(user="admin@example.test")

        self.assertEqual(condition, "")

    # ------------------------------------------------------------------
    # Patient record PQC
    # ------------------------------------------------------------------

    def test_patient_record_pqc_scopes_to_own_name(self):
        """Patient role → PQC filters tabPatient by name."""
        with patch("medic_plus.api.permissions.frappe.get_roles", return_value=["Patient"]), \
             patch("medic_plus.api.permissions.frappe.db.get_value", return_value="PAT-00042"):
            condition = get_patient_permission_query(user="patient@example.test")

        self.assertIn("`tabPatient`.`name`", condition)
        self.assertIn("PAT-00042", condition)

    # ------------------------------------------------------------------
    # Patient Appointment PQC
    # ------------------------------------------------------------------

    def test_patient_appointment_pqc_scopes_to_own_patient(self):
        """Patient role → PQC filters Patient Appointment by patient field."""
        with patch("medic_plus.api.permissions.frappe.get_roles", return_value=["Patient"]), \
             patch("medic_plus.api.permissions.frappe.db.get_value", return_value="PAT-00007"):
            condition = get_patient_appointment_permission_query(user="patient@example.test")

        self.assertIn("`tabPatient Appointment`.`patient`", condition)
        self.assertIn("PAT-00007", condition)
        self.assertNotIn("`tabPatient Appointment`.`custom_practice`", condition)

    def test_patient_appointment_pqc_staff_uses_practice(self):
        """Practice staff → PQC filters Patient Appointment by custom_practice."""
        with patch("medic_plus.api.permissions.frappe.get_roles", return_value=["Practice Doctor"]), \
             patch("medic_plus.api.permissions.frappe.db.get_value", return_value="PRAC-00002"):
            condition = get_patient_appointment_permission_query(user="doctor@example.test")

        self.assertIn("`tabPatient Appointment`.`custom_practice`", condition)
        self.assertIn("PRAC-00002", condition)
