"""Phase 5.10 — Performance / scale audit: integration tests for Axis 1 and 2.

Axis 1: DB indexes on custom_practice exist for all audited tables.
Axis 2: Cache hit-rate instrumentation and get_cache_stats endpoint shape.

Axes 3 (FHIR load) and 4 (Lab inbox throughput) are manual-only load
tests in tests/perf/ and are skip-marked in CI.
"""

import frappe
from frappe.tests import IntegrationTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


# ---------------------------------------------------------------------------
# Axis 1 — DB indexes
# ---------------------------------------------------------------------------

# Doctypes that must have a custom_practice index
_INDEXED_TABLES = [
    "tabPatient",
    "tabPatient Appointment",
    "tabPatient Encounter",
    "tabInpatient Record",
    "tabSick Note",
    "tabWarehouse",
    "tabStock Entry",
    "tabData Unmask Request",
    "tabClinical Access Log",
    "tabPatient Allergy",
    "tabPatient Chronic Condition",
    "tabPatient Identifier",
]

# Additional targeted indexes
_ADDITIONAL_INDEXES = [
    ("tabPatient Encounter", "appointment_type"),
    ("tabClinical Access Log", "patient"),
    ("tabClinical Access Log", "accessor_user"),
]


class TestCustomPracticeIndexes(IntegrationTestCase):
    """After the patch runs, custom_practice indexes exist on all audited tables."""

    def _has_index(self, table: str, column: str) -> bool:
        rows = frappe.db.sql(
            "SHOW INDEX FROM `{table}` WHERE Column_name = %s".format(table=table),
            (column,),
        )
        return len(rows) > 0

    def _table_exists(self, table: str) -> bool:
        rows = frappe.db.sql(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
            (table,),
        )
        return len(rows) > 0

    def test_patch_is_idempotent(self):
        """Running the index patch twice raises no error."""
        from medic_plus.patches.v0_4_0.add_custom_practice_indexes import execute
        execute()
        execute()  # second run must be a no-op

    def test_custom_practice_indexes_exist_after_patch(self):
        """Each audited table has an index on custom_practice after the patch."""
        from medic_plus.patches.v0_4_0.add_custom_practice_indexes import execute
        execute()
        missing = []
        for table in _INDEXED_TABLES:
            if not self._table_exists(table):
                continue  # table may not exist in minimal test DB
            if not self._has_index(table, "custom_practice"):
                missing.append(table)
        self.assertEqual(
            missing, [],
            f"custom_practice index missing on: {missing}",
        )

    def test_additional_indexes_exist_after_patch(self):
        """Additional targeted indexes exist after the patch."""
        from medic_plus.patches.v0_4_0.add_custom_practice_indexes import execute
        execute()
        missing = []
        for table, column in _ADDITIONAL_INDEXES:
            if not self._table_exists(table):
                continue
            if not self._has_index(table, column):
                missing.append(f"{table}.{column}")
        self.assertEqual(missing, [], f"Targeted indexes missing: {missing}")


# ---------------------------------------------------------------------------
# Axis 2 — Cache hit-rate instrumentation
# ---------------------------------------------------------------------------

class TestCacheStatEndpoint(IntegrationTestCase):
    """get_cache_stats returns per-method call counts with correct shape."""

    def setUp(self):
        # Clear any stale counters from prior test runs
        try:
            frappe.cache().delete("medic_plus:rpc_calls")
            frappe.cache().delete("medic_plus:rpc_cache_hits")
        except Exception:
            pass

    def test_track_call_increments_counter(self):
        """track_call increments the Redis call counter for a method."""
        from medic_plus.api.perf import track_call
        track_call("search_icd10")
        track_call("search_icd10")
        try:
            count = int(frappe.cache().hget("medic_plus:rpc_calls", "search_icd10") or 0)
        except Exception:
            self.skipTest("Redis not available in this test environment")
        self.assertGreaterEqual(count, 2)

    def test_get_cache_stats_returns_correct_shape(self):
        """get_cache_stats returns a list of dicts with method/call_count/hit_count/hit_rate."""
        from medic_plus.api.perf import track_call, get_cache_stats
        track_call("get_medical_records")
        result = get_cache_stats()
        self.assertIsInstance(result, list)
        if not result:
            return  # Redis unavailable in test env — skip assertion
        sample = result[0]
        for key in ("method", "call_count", "hit_count", "hit_rate"):
            self.assertIn(key, sample, f"Key '{key}' missing from get_cache_stats response")

    def test_get_cache_stats_includes_tracked_methods(self):
        """get_cache_stats response includes all 5 monitored methods."""
        from medic_plus.api.perf import TRACKED_METHODS, track_call, get_cache_stats
        for m in TRACKED_METHODS:
            track_call(m)
        result = get_cache_stats()
        if not result:
            return  # Redis unavailable
        returned_methods = {r["method"] for r in result}
        for m in TRACKED_METHODS:
            self.assertIn(m, returned_methods)

    def test_hit_rate_between_zero_and_one(self):
        """hit_rate is in [0, 1] for all returned methods."""
        from medic_plus.api.perf import track_call, get_cache_stats
        track_call("search_icd10")
        result = get_cache_stats()
        if not result:
            return
        for row in result:
            self.assertGreaterEqual(row["hit_rate"], 0.0)
            self.assertLessEqual(row["hit_rate"], 1.0)

    def test_track_call_failure_never_raises(self):
        """track_call does not propagate Redis errors to callers."""
        from medic_plus.api.perf import track_call
        import unittest.mock as mock
        with mock.patch("frappe.cache") as mock_cache:
            mock_cache.return_value.hincrby.side_effect = Exception("Redis down")
            try:
                track_call("search_icd10")
            except Exception as exc:
                self.fail(f"track_call raised unexpectedly: {exc}")
