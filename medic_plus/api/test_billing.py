"""
Unit tests for medic_plus.api.billing — plan enforcement & entitlement logic.

All external calls (frappe.db, frappe.get_roles, frappe.throw) are mocked.
No documents are created in the database.
"""

import unittest
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

def _import_billing():
    """Import billing module freshly to allow clean mock patching."""
    from medic_plus.api import billing
    return billing


# ── tests ─────────────────────────────────────────────────────────────────────


class TestMedicPlanCatalogue(unittest.TestCase):
    """Validate the MEDIC_PLANS constant structure."""

    def setUp(self):
        self.b = _import_billing()
        self.plans = self.b.MEDIC_PLANS

    def test_three_plans_defined(self):
        self.assertEqual(set(self.plans.keys()), {"Free", "Basic", "Pro"})

    def test_all_plans_have_required_keys(self):
        required = {"label", "price_monthly", "features", "limits"}
        for key, plan in self.plans.items():
            missing = required - set(plan.keys())
            self.assertFalse(missing, f"Plan '{key}' is missing keys: {missing}")

    def test_free_plan_is_cheapest(self):
        self.assertEqual(self.plans["Free"]["price_monthly"], 0)

    def test_pro_plan_is_most_expensive(self):
        prices = [p["price_monthly"] for p in self.plans.values()]
        self.assertEqual(self.plans["Pro"]["price_monthly"], max(prices))

    def test_inpatient_module_only_on_pro(self):
        self.assertFalse(self.plans["Free"]["features"]["inpatient_module"])
        self.assertFalse(self.plans["Basic"]["features"]["inpatient_module"])
        self.assertTrue(self.plans["Pro"]["features"]["inpatient_module"])

    def test_free_plan_has_patient_limit(self):
        limit = self.plans["Free"]["limits"]["Patient"]
        self.assertGreater(limit, 0, "Free plan must have a finite Patient limit")

    def test_pro_plan_has_unlimited_patients(self):
        self.assertEqual(self.plans["Pro"]["limits"]["Patient"], 0, "0 = unlimited")

    def test_all_plans_have_dispensing(self):
        """All tiers include basic dispensing."""
        for key, plan in self.plans.items():
            self.assertTrue(plan["features"]["dispensing"], f"Plan '{key}' missing dispensing")

    def test_plan_order_list_complete(self):
        self.assertEqual(self.b._PLAN_ORDER, ["Free", "Basic", "Pro"])


class TestGetPracticePlan(unittest.TestCase):
    """Tests for get_practice_plan()."""

    def setUp(self):
        self.b = _import_billing()

    def test_returns_free_when_no_practice(self):
        with patch.object(self.b, "_get_user_practice", return_value=None):
            result = self.b.get_practice_plan()
        self.assertEqual(result, "Free")

    def test_returns_plan_from_db(self):
        with patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"), \
             patch("frappe.db.get_value", return_value="Pro"):
            result = self.b.get_practice_plan()
        self.assertEqual(result, "Pro")

    def test_unknown_plan_key_falls_back_to_free(self):
        with patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"), \
             patch("frappe.db.get_value", return_value="Enterprise"):
            result = self.b.get_practice_plan()
        self.assertEqual(result, "Free")

    def test_empty_plan_falls_back_to_free(self):
        with patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"), \
             patch("frappe.db.get_value", return_value=None):
            result = self.b.get_practice_plan()
        self.assertEqual(result, "Free")

    def test_explicit_practice_arg_used(self):
        with patch("frappe.db.get_value", return_value="Basic") as mock_db:
            result = self.b.get_practice_plan("PRAC-00099")
        self.assertEqual(result, "Basic")
        mock_db.assert_called_once_with("Practice", "PRAC-00099", "subscription_plan")


class TestHasFeature(unittest.TestCase):
    """Tests for has_feature()."""

    def setUp(self):
        self.b = _import_billing()

    def _has_feature(self, feature_key, plan_key, is_admin=False):
        with patch.object(self.b, "_is_platform_admin", return_value=is_admin), \
             patch.object(self.b, "get_practice_plan", return_value=plan_key):
            return self.b.has_feature(feature_key)

    def test_admin_always_has_all_features(self):
        self.assertTrue(self._has_feature("inpatient_module", "Free", is_admin=True))

    def test_free_lacks_inpatient(self):
        self.assertFalse(self._has_feature("inpatient_module", "Free"))

    def test_basic_lacks_inpatient(self):
        self.assertFalse(self._has_feature("inpatient_module", "Basic"))

    def test_pro_has_inpatient(self):
        self.assertTrue(self._has_feature("inpatient_module", "Pro"))

    def test_all_plans_have_appointments(self):
        for plan in ("Free", "Basic", "Pro"):
            with self.subTest(plan=plan):
                self.assertTrue(self._has_feature("appointments", plan))

    def test_unknown_feature_returns_false(self):
        self.assertFalse(self._has_feature("time_machine", "Pro"))

    def test_free_lacks_sms_reminders(self):
        self.assertFalse(self._has_feature("sms_reminders", "Free"))

    def test_pro_has_sms_reminders(self):
        self.assertTrue(self._has_feature("sms_reminders", "Pro"))


class TestIsWithinLimit(unittest.TestCase):
    """Tests for is_within_limit()."""

    def setUp(self):
        self.b = _import_billing()

    def _within(self, identifier, plan_key, current_count, practice="PRAC-00001", is_admin=False):
        with patch.object(self.b, "_is_platform_admin", return_value=is_admin), \
             patch.object(self.b, "_get_user_practice", return_value=practice), \
             patch.object(self.b, "get_practice_plan", return_value=plan_key), \
             patch.object(self.b, "_count_usage", return_value=current_count):
            return self.b.is_within_limit(identifier, practice)

    def test_admin_always_within_limit(self):
        self.assertTrue(self._within("Patient", "Free", 9999, is_admin=True))

    def test_free_plan_within_patient_limit(self):
        free_limit = self.b.MEDIC_PLANS["Free"]["limits"]["Patient"]
        self.assertTrue(self._within("Patient", "Free", free_limit - 1))

    def test_free_plan_at_patient_limit_blocked(self):
        free_limit = self.b.MEDIC_PLANS["Free"]["limits"]["Patient"]
        self.assertFalse(self._within("Patient", "Free", free_limit))

    def test_free_plan_over_patient_limit_blocked(self):
        free_limit = self.b.MEDIC_PLANS["Free"]["limits"]["Patient"]
        self.assertFalse(self._within("Patient", "Free", free_limit + 5))

    def test_pro_plan_unlimited_always_within(self):
        # Pro Patient limit = 0 (unlimited)
        self.assertTrue(self._within("Patient", "Pro", 99_999))

    def test_no_practice_returns_false(self):
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "_get_user_practice", return_value=None):
            result = self.b.is_within_limit("Patient")
        self.assertFalse(result)

    def test_unknown_identifier_treated_as_unlimited(self):
        # Unknown identifier → limit defaults to 0 (unlimited)
        self.assertTrue(self._within("UnknownResource", "Free", 9999))


class TestRequireFeatureDecorator(unittest.TestCase):
    """Tests for the @require_feature decorator."""

    def setUp(self):
        self.b = _import_billing()

    def _decorate(self, feature_key, plan_key, is_admin=False):
        """Create a decorated dummy function and return it."""
        @self.b.require_feature(feature_key)
        def dummy():
            return "ok"

        return dummy, plan_key, is_admin

    def test_allowed_plan_calls_through(self):
        fn, plan_key, is_admin = self._decorate("inpatient_module", "Pro")
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Pro"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            result = fn()
        self.assertEqual(result, "ok")

    def test_blocked_plan_raises_permission_error(self):
        fn, _, _ = self._decorate("inpatient_module", "Free")
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Free"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            with self.assertRaises(frappe.PermissionError):
                fn()

    def test_admin_bypasses_gate(self):
        fn, _, _ = self._decorate("inpatient_module", "Free")
        with patch.object(self.b, "_is_platform_admin", return_value=True):
            result = fn()
        self.assertEqual(result, "ok")

    def test_basic_blocked_for_inpatient(self):
        fn, _, _ = self._decorate("inpatient_module", "Basic")
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Basic"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            with self.assertRaises(frappe.PermissionError):
                fn()

    def test_error_message_names_the_feature(self):
        fn, _, _ = self._decorate("inpatient_module", "Free")
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Free"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            with self.assertRaises(frappe.PermissionError) as ctx:
                fn()
        self.assertIn("inpatient", str(ctx.exception).lower())

    def test_error_message_mentions_upgrade(self):
        fn, _, _ = self._decorate("inpatient_module", "Free")
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Free"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            with self.assertRaises(frappe.PermissionError) as ctx:
                fn()
        self.assertIn("Pro", str(ctx.exception))  # tells user which plan to upgrade to


class TestRequireLimitDecorator(unittest.TestCase):
    """Tests for the @require_limit decorator."""

    def setUp(self):
        self.b = _import_billing()

    def test_within_limit_calls_through(self):
        @self.b.require_limit("Patient")
        def add_patient():
            return "created"

        with patch.object(self.b, "is_within_limit", return_value=True):
            result = add_patient()
        self.assertEqual(result, "created")

    def test_at_limit_raises_validation_error(self):
        @self.b.require_limit("Patient")
        def add_patient():
            return "created"

        with patch.object(self.b, "is_within_limit", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Free"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            with self.assertRaises(frappe.ValidationError):
                add_patient()

    def test_limit_error_mentions_upgrade(self):
        @self.b.require_limit("Patient")
        def add_patient():
            return "created"

        with patch.object(self.b, "is_within_limit", return_value=False), \
             patch.object(self.b, "get_practice_plan", return_value="Free"), \
             patch.object(self.b, "_get_user_practice", return_value="PRAC-00001"):
            with self.assertRaises(frappe.ValidationError) as ctx:
                add_patient()
        self.assertIn("upgrade", str(ctx.exception).lower())


class TestStartTrialForPractice(unittest.TestCase):
    """Tests for the start_trial_for_practice doc_event hook."""

    def setUp(self):
        self.b = _import_billing()

    def test_sets_free_plan_and_trialing_status(self):
        doc = MagicMock()
        doc.name = "PRAC-00001"

        with patch("frappe.db.set_value") as mock_set:
            self.b.start_trial_for_practice(doc)

        mock_set.assert_called_once()
        args = mock_set.call_args
        values = args[0][2]  # third positional argument is the dict
        self.assertEqual(values["subscription_plan"], "Free")
        self.assertEqual(values["subscription_status"], "Trialing")

    def test_sets_trial_ends_on_14_days_out(self):
        from frappe.utils import add_days, today, getdate

        doc = MagicMock()
        doc.name = "PRAC-00001"

        with patch("frappe.db.set_value") as mock_set:
            self.b.start_trial_for_practice(doc)

        values = mock_set.call_args[0][2]
        trial_end = getdate(values["trial_ends_on"])
        expected = getdate(add_days(today(), 14))
        self.assertEqual(trial_end, expected)

    def test_uses_doc_name_as_practice_identifier(self):
        doc = MagicMock()
        doc.name = "PRAC-TEST-99"

        with patch("frappe.db.set_value") as mock_set:
            self.b.start_trial_for_practice(doc)

        args = mock_set.call_args[0]
        self.assertEqual(args[0], "Practice")
        self.assertEqual(args[1], "PRAC-TEST-99")

    def test_method_arg_is_optional(self):
        """Frappe may pass method='after_insert' as second arg; must not crash."""
        doc = MagicMock()
        doc.name = "PRAC-00002"

        with patch("frappe.db.set_value"):
            self.b.start_trial_for_practice(doc, method="after_insert")


class TestGetBillingSummary(unittest.TestCase):
    """Tests for the get_billing_summary() API method."""

    def setUp(self):
        self.b = _import_billing()

    def _call_summary(self, plan_key="Free", status="Trialing", trial_ends=None,
                      patient_count=5, user_count=2, is_admin=False):
        practice = None if is_admin else "PRAC-00001"
        with patch.object(self.b, "_is_platform_admin", return_value=is_admin), \
             patch.object(self.b, "_get_user_practice", return_value=practice), \
             patch.object(self.b, "get_practice_plan", return_value=plan_key), \
             patch.object(self.b, "get_practice_status", return_value=status), \
             patch("frappe.db.get_value", return_value=trial_ends), \
             patch.object(self.b, "_count_usage", side_effect=lambda id, p: patient_count if id == "Patient" else user_count):
            return self.b.get_billing_summary()

    def test_returns_all_required_keys(self):
        result = self._call_summary()
        required = {"plan_key", "plan_label", "price_label", "status", "features", "usage", "available_plans"}
        missing = required - set(result.keys())
        self.assertFalse(missing, f"Missing keys: {missing}")

    def test_plan_key_matches_plan(self):
        result = self._call_summary(plan_key="Basic")
        self.assertEqual(result["plan_key"], "Basic")

    def test_usage_structure_for_free_plan(self):
        result = self._call_summary(plan_key="Free", patient_count=10)
        self.assertIn("Patient", result["usage"])
        patient_usage = result["usage"]["Patient"]
        self.assertEqual(patient_usage["current"], 10)
        self.assertGreater(patient_usage["limit"], 0)

    def test_at_limit_flag_set(self):
        free_limit = self.b.MEDIC_PLANS["Free"]["limits"]["Patient"]
        result = self._call_summary(plan_key="Free", patient_count=free_limit)
        self.assertTrue(result["usage"]["Patient"]["at_limit"])

    def test_available_plans_for_free(self):
        result = self._call_summary(plan_key="Free")
        keys = {p["key"] for p in result["available_plans"]}
        self.assertIn("Basic", keys)
        self.assertIn("Pro", keys)
        self.assertNotIn("Free", keys)

    def test_available_plans_for_pro_is_empty(self):
        result = self._call_summary(plan_key="Pro")
        self.assertEqual(result["available_plans"], [])

    def test_no_practice_and_not_admin_raises(self):
        with patch.object(self.b, "_is_platform_admin", return_value=False), \
             patch.object(self.b, "_get_user_practice", return_value=None):
            with self.assertRaises(frappe.PermissionError):
                self.b.get_billing_summary()


class TestCountUsage(unittest.TestCase):
    """Tests for the _count_usage internal helper."""

    def setUp(self):
        self.b = _import_billing()

    def test_patient_identifier_queries_patient_doctype(self):
        with patch("frappe.db.count", return_value=42) as mock_count:
            result = self.b._count_usage("Patient", "PRAC-00001")
        self.assertEqual(result, 42)
        mock_count.assert_called_once_with("Patient", {"custom_practice": "PRAC-00001"})

    def test_users_identifier_queries_practice_member(self):
        with patch("frappe.db.count", return_value=3) as mock_count:
            result = self.b._count_usage("users", "PRAC-00001")
        self.assertEqual(result, 3)
        mock_count.assert_called_once_with("Practice Member", {"practice": "PRAC-00001"})

    def test_unknown_identifier_returns_zero(self):
        result = self.b._count_usage("something_unknown", "PRAC-00001")
        self.assertEqual(result, 0)


class TestGetAvailablePlans(unittest.TestCase):
    """Tests for the _get_available_plans private helper."""

    def setUp(self):
        self.b = _import_billing()

    def test_free_returns_basic_and_pro(self):
        plans = self.b._get_available_plans("Free")
        keys = [p["key"] for p in plans]
        self.assertEqual(keys, ["Basic", "Pro"])

    def test_basic_returns_only_pro(self):
        plans = self.b._get_available_plans("Basic")
        keys = [p["key"] for p in plans]
        self.assertEqual(keys, ["Pro"])

    def test_pro_returns_empty(self):
        plans = self.b._get_available_plans("Pro")
        self.assertEqual(plans, [])

    def test_each_plan_has_price_and_highlight(self):
        for plan in self.b._get_available_plans("Free"):
            self.assertIn("price_monthly", plan)
            self.assertIn("highlight", plan)
            self.assertIsInstance(plan["highlight"], list)


if __name__ == "__main__":
    unittest.main()
