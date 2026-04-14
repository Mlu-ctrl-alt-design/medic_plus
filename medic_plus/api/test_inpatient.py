"""
Unit tests for medic_plus.api.inpatient — summary stats, inpatient list, and feature gating.

All external calls (frappe.db, billing decorators) are mocked.
No documents are created in the database.
"""

import unittest
from datetime import datetime, date
from unittest.mock import MagicMock, patch, call

import frappe


# ── frappe local-state bootstrap ─────────────────────────────────────────────

def setUpModule():
    """Bind frappe LocalProxy objects so mock patching works correctly."""
    frappe.local.session = frappe._dict(user="test@example.test")
    frappe.local.conf = frappe._dict(developer_mode=0)
    frappe.local.flags = frappe._dict()
    frappe.local.lang = "en"
    frappe.local.message_log = []
    frappe.local.error_log = []
    frappe.local.debug_log = []
    frappe.local.response = frappe._dict()

    cache_mock = MagicMock()
    cache_mock.hget.return_value = {}
    frappe.cache = cache_mock


# ── helpers ──────────────────────────────────────────────────────────────────

def _import_inpatient():
    from medic_plus.api import inpatient
    return inpatient


def _import_billing():
    from medic_plus.api import billing
    return billing


def _make_inpatient_record(**kwargs):
    """Return a frappe._dict simulating a fetched Inpatient Record row."""
    base = frappe._dict(
        name="IPD-00001",
        patient="PAT-00001",
        patient_name="John Doe",
        gender="Male",
        status="Admitted",
        admitted_datetime=datetime(2026, 4, 10, 9, 0, 0),
        expected_discharge=date(2026, 4, 16),
        primary_practitioner="DR-00001",
        medical_department="General Medicine",
        custom_practice="PRAC-00001",
    )
    base.update(kwargs)
    return base


# ── tests ─────────────────────────────────────────────────────────────────────


class TestGetPracticeFilter(unittest.TestCase):
    """Tests for _get_practice_filter()."""

    def setUp(self):
        self.m = _import_inpatient()
        self.b = _import_billing()

    def test_admin_returns_empty_filter(self):
        with patch.object(self.b, "_is_platform_admin", return_value=True):
            result = self.m._get_practice_filter()
        self.assertEqual(result, {})

    def test_practice_user_returns_practice_filter(self):
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            result = self.m._get_practice_filter()
        self.assertEqual(result, {"custom_practice": "PRAC-00001"})

    def test_no_practice_raises_permission_error(self):
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "_get_user_practice", return_value=None):
            with self.assertRaises(frappe.PermissionError):
                self.m._get_practice_filter()


class TestComputeAvgLos(unittest.TestCase):
    """Tests for _compute_avg_los()."""

    def setUp(self):
        self.m = _import_inpatient()

    def test_no_admitted_patients_returns_zero(self):
        with patch("frappe.db.get_all", return_value=[]):
            result = self.m._compute_avg_los({"custom_practice": "PRAC-00001"})
        self.assertEqual(result, 0)

    def test_single_patient_admitted_today(self):
        from frappe.utils import today
        today_dt = datetime.strptime(today(), "%Y-%m-%d")
        record = frappe._dict(admitted_datetime=today_dt)
        with patch("frappe.db.get_all", return_value=[record]):
            result = self.m._compute_avg_los({})
        self.assertEqual(result, 0.0)

    def test_average_calculated_correctly(self):
        from frappe.utils import add_days, today
        today_str = today()
        records = [
            frappe._dict(admitted_datetime=datetime.strptime(add_days(today_str, -2), "%Y-%m-%d")),
            frappe._dict(admitted_datetime=datetime.strptime(add_days(today_str, -4), "%Y-%m-%d")),
        ]
        with patch("frappe.db.get_all", return_value=records):
            result = self.m._compute_avg_los({})
        # Average of 2 days and 4 days = 3.0
        self.assertEqual(result, 3.0)

    def test_rounds_to_one_decimal(self):
        from frappe.utils import add_days, today
        today_str = today()
        records = [
            frappe._dict(admitted_datetime=datetime.strptime(add_days(today_str, -1), "%Y-%m-%d")),
            frappe._dict(admitted_datetime=datetime.strptime(add_days(today_str, -2), "%Y-%m-%d")),
            frappe._dict(admitted_datetime=datetime.strptime(add_days(today_str, -2), "%Y-%m-%d")),
        ]
        with patch("frappe.db.get_all", return_value=records):
            result = self.m._compute_avg_los({})
        # Average = (1+2+2)/3 = 1.666... → rounds to 1.7
        self.assertEqual(result, 1.7)

    def test_records_with_null_admitted_datetime_skipped(self):
        records = [
            frappe._dict(admitted_datetime=None),
            frappe._dict(admitted_datetime=None),
        ]
        with patch("frappe.db.get_all", return_value=records):
            result = self.m._compute_avg_los({})
        self.assertEqual(result, 0)


class TestGetInpatientSummary(unittest.TestCase):
    """Tests for get_inpatient_summary() return structure."""

    def setUp(self):
        self.m = _import_inpatient()
        self.b = _import_billing()

    def _call(self, is_admin=True, patient_count=3, admission_count=1,
              discharge_count=0, avg_los=2.5):
        with patch.object(self.b, "_is_platform_admin", return_value=is_admin), \
             patch.object(self.b, "_get_user_practice",
                          return_value=None if is_admin else "PRAC-00001"), \
             patch("frappe.db.count", side_effect=[patient_count, admission_count, discharge_count]), \
             patch.object(self.m, "_compute_avg_los", return_value=avg_los):
            return self.m.get_inpatient_summary()

    def test_returns_all_required_keys(self):
        result = self._call()
        for key in ("current_inpatients", "todays_admissions", "expected_discharges", "avg_los_days"):
            self.assertIn(key, result)

    def test_current_inpatients_count(self):
        result = self._call(patient_count=7)
        self.assertEqual(result["current_inpatients"], 7)

    def test_todays_admissions_count(self):
        result = self._call(admission_count=2)
        self.assertEqual(result["todays_admissions"], 2)

    def test_expected_discharges_count(self):
        result = self._call(discharge_count=3)
        self.assertEqual(result["expected_discharges"], 3)

    def test_avg_los_days_value(self):
        result = self._call(avg_los=4.2)
        self.assertEqual(result["avg_los_days"], 4.2)

    def test_feature_gate_blocks_free_plan_user(self):
        """require_feature('inpatient_module') blocks a Free-plan practice doctor."""
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Free"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            with self.assertRaises(frappe.PermissionError):
                self.m.get_inpatient_summary()

    def test_feature_gate_allows_pro_plan_user(self):
        """Pro plan user passes the inpatient_module feature gate."""
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Pro"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"), \
             patch("frappe.db.count", return_value=0), \
             patch.object(self.m, "_compute_avg_los", return_value=0):
            result = self.m.get_inpatient_summary()
        self.assertIn("current_inpatients", result)


class TestGetCurrentInpatients(unittest.TestCase):
    """Tests for get_current_inpatients() return structure and enrichment."""

    def setUp(self):
        self.m = _import_inpatient()
        self.b = _import_billing()

    def _call(self, records=None, occ=None, is_admin=True):
        records = records or []
        with patch.object(self.b, "_is_platform_admin", return_value=is_admin), \
             patch.object(self.b, "get_practice_plan", return_value="Pro"), \
             patch.object(self.b, "_get_user_practice",
                          return_value=None if is_admin else "PRAC-00001"), \
             patch("frappe.db.get_all", return_value=records), \
             patch("frappe.db.get_value", return_value=occ):
            return self.m.get_current_inpatients()

    def test_empty_returns_empty_list(self):
        result = self._call(records=[])
        self.assertEqual(result, [])

    def test_los_days_computed(self):
        from frappe.utils import add_days, today
        admit_dt = datetime.strptime(add_days(today(), -3), "%Y-%m-%d")
        record = _make_inpatient_record(admitted_datetime=admit_dt)
        result = self._call(records=[record])
        self.assertEqual(result[0]["los_days"], 3)

    def test_los_days_zero_when_admitted_today(self):
        from frappe.utils import today
        admit_dt = datetime.strptime(today(), "%Y-%m-%d")
        record = _make_inpatient_record(admitted_datetime=admit_dt)
        result = self._call(records=[record])
        self.assertEqual(result[0]["los_days"], 0)

    def test_los_days_zero_when_no_admitted_datetime(self):
        record = _make_inpatient_record(admitted_datetime=None)
        result = self._call(records=[record])
        self.assertEqual(result[0]["los_days"], 0)

    def test_current_ward_populated_from_occupancy(self):
        record = _make_inpatient_record()
        occ = frappe._dict(service_unit="Ward A", check_in=datetime(2026, 4, 10, 9, 0))
        with patch.object(self.b, "_is_platform_admin", return_value=True), \
             patch.object(self.b, "get_practice_plan", return_value="Pro"), \
             patch("frappe.db.get_all", return_value=[record]), \
             patch("frappe.db.get_value", return_value=occ):
            result = self.m.get_current_inpatients()
        self.assertEqual(result[0]["current_ward"], "Ward A")

    def test_current_ward_none_when_no_occupancy(self):
        record = _make_inpatient_record()
        result = self._call(records=[record], occ=None)
        self.assertIsNone(result[0]["current_ward"])

    def test_feature_gate_blocks_free_plan(self):
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Free"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            with self.assertRaises(frappe.PermissionError):
                self.m.get_current_inpatients()

    def test_practice_filter_applied_for_non_admin(self):
        """Non-admin calls include custom_practice in the DB filter."""
        record = _make_inpatient_record()
        occ = frappe._dict(service_unit="Ward B", check_in=None)
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Pro"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"), \
             patch("frappe.db.get_all", return_value=[record]) as mock_get_all, \
             patch("frappe.db.get_value", return_value=occ):
            self.m.get_current_inpatients()

        call_kwargs = mock_get_all.call_args
        filters_used = call_kwargs[1].get("filters") or call_kwargs[0][1]
        self.assertIn("custom_practice", filters_used)
        self.assertEqual(filters_used["custom_practice"], "PRAC-00001")

    def test_multiple_records_all_get_los(self):
        from frappe.utils import add_days, today
        today_str = today()
        records = [
            _make_inpatient_record(
                name=f"IPD-0000{i}",
                admitted_datetime=datetime.strptime(add_days(today_str, -i), "%Y-%m-%d"),
            )
            for i in range(1, 4)
        ]
        with patch.object(self.b, "_is_platform_admin", return_value=True), \
             patch.object(self.b, "get_practice_plan", return_value="Pro"), \
             patch("frappe.db.get_all", return_value=records), \
             patch("frappe.db.get_value", return_value=None):
            result = self.m.get_current_inpatients()

        self.assertEqual(len(result), 3)
        for i, row in enumerate(result, start=1):
            self.assertEqual(row["los_days"], i)


class TestInpatientFeatureGateIntegration(unittest.TestCase):
    """Cross-module: verify billing.require_feature gates inpatient endpoints."""

    def setUp(self):
        self.b = _import_billing()

    def test_plan_catalogue_inpatient_gating_consistent(self):
        """Every plan that gates inpatient must have inpatient_module=False."""
        gated_plans = ("Free", "Basic")
        for plan_key in gated_plans:
            with self.subTest(plan=plan_key):
                self.assertFalse(
                    self.b.MEDIC_PLANS[plan_key]["features"]["inpatient_module"],
                    f"Plan '{plan_key}' should NOT include inpatient_module",
                )

    def test_first_plan_with_inpatient_is_pro(self):
        result = self.b._first_plan_with_feature("inpatient_module")
        self.assertEqual(result, "Pro")

    def test_first_plan_with_appointments_is_free(self):
        """Appointments feature available even on Free plan."""
        result = self.b._first_plan_with_feature("appointments")
        self.assertEqual(result, "Free")

    def test_unavailable_feature_returns_none(self):
        result = self.b._first_plan_with_feature("teleportation")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
