"""Phase 1B (#25) — Terminology stack: bench-importable Code Systems.

Tracer bullet: `import_icd10(csv_path)` ingests a CSV of (code, display)
rows into `Code Value` under `code_system = "ICD-10-ZA"`. Idempotent —
re-running the same CSV does not create duplicates.

The bench command (`bench import-icd10 …`) is a thin click wrapper over
this function. We test the function directly because subprocess testing
of bench commands is slow and brittle.

Mirrors test patterns in test_sa_emr_phase1.py — uses IntegrationTestCase
to dodge ERPNext's compat preloader.
"""

import csv
import os
import tempfile

import frappe
from frappe.tests import IntegrationTestCase


def _write_csv(rows: list[tuple[str, str]]) -> str:
	fd, path = tempfile.mkstemp(suffix=".csv", prefix="icd10_seed_")
	with os.fdopen(fd, "w", newline="") as fh:
		w = csv.writer(fh)
		w.writerow(["code", "display"])
		for code, display in rows:
			w.writerow([code, display])
	return path


def _seed_rows(n: int, *, prefix: str) -> list[tuple[str, str]]:
	# Test-scoped synthetic codes — the prefix isolates test runs from
	# each other and from the real ICD-10-ZA seed (real codes start with
	# A–Z + digits, so a prefix like "TST1." cannot collide).
	rows = []
	for i in range(n):
		code = f"{prefix}{i:03d}"
		rows.append((code, f"Test diagnosis {code}"))
	return rows


class TestIcd10ImportTracer(IntegrationTestCase):
	"""End-to-end: 50-row CSV → 50 Code Value rows under ICD-10-ZA, idempotent."""

	def setUp(self):
		# The Code System must exist before importing values.
		if not frappe.db.exists("Code System", "ICD-10-ZA"):
			frappe.get_doc({
				"doctype": "Code System",
				"code_system": "ICD-10-ZA",
				"uri": "http://hl7.org/fhir/sid/icd-10-za",
				"is_fhir_defined": 1,
			}).insert(ignore_permissions=True)
		# Cleanup synthetic test rows from prior runs so each test starts clean.
		for stale in frappe.get_all(
			"Code Value",
			filters={"code_system": "ICD-10-ZA", "code_value": ["like", "TST_.%"]},
			pluck="name",
		):
			frappe.delete_doc("Code Value", stale, ignore_permissions=True, force=True)

	def test_first_import_creates_50_rows(self):
		from medic_plus.api.terminology_import import import_icd10
		csv_path = _write_csv(_seed_rows(50, prefix="TST1."))
		try:
			result = import_icd10(csv_path)
		finally:
			os.unlink(csv_path)
		self.assertEqual(result["created"], 50)
		self.assertEqual(result["updated"], 0)

	def test_reimport_is_idempotent(self):
		from medic_plus.api.terminology_import import import_icd10
		rows = _seed_rows(50, prefix="TST2.")
		csv_path = _write_csv(rows)
		try:
			first = import_icd10(csv_path)
			second = import_icd10(csv_path)
		finally:
			os.unlink(csv_path)
		self.assertEqual(first["created"], 50)
		self.assertEqual(first["updated"], 0)
		# Second pass: zero created, all 50 updated (display refreshed in-place).
		self.assertEqual(second["created"], 0)
		self.assertEqual(second["updated"], 50)

	def test_reimport_updates_changed_display(self):
		from medic_plus.api.terminology_import import import_icd10
		# First import with one display value, second with a different one.
		first_path = _write_csv([("TST3.001", "Old text")])
		second_path = _write_csv([("TST3.001", "New text")])
		try:
			import_icd10(first_path)
			import_icd10(second_path)
		finally:
			os.unlink(first_path)
			os.unlink(second_path)
		display = frappe.db.get_value(
			"Code Value", "TST3.001-ICD-10-ZA", "display"
		)
		self.assertEqual(display, "New text")


class TestMultiSystemImporters(IntegrationTestCase):
	"""Each terminology system has its own idempotent import_<system>(csv).

	The same code value (e.g. "I10") in two different systems must NOT
	collide — Code Value's autoname is `{code}-{system}` so disambiguation
	is built in, but we pin the behaviour so a future controller change
	cannot silently merge them.
	"""

	def setUp(self):
		# Cleanup synthetic rows from prior runs across all systems.
		for system in ("ICD-10-ZA", "NAPPI"):
			for stale in frappe.get_all(
				"Code Value",
				filters={"code_system": system, "code_value": ["like", "TSTX_.%"]},
				pluck="name",
			):
				frappe.delete_doc("Code Value", stale, ignore_permissions=True, force=True)

	def test_import_nappi_creates_rows(self):
		from medic_plus.api.terminology_import import import_nappi
		rows = [("TSTX1.001", "Test medication 1"), ("TSTX1.002", "Test medication 2")]
		csv_path = _write_csv(rows)
		try:
			result = import_nappi(csv_path)
		finally:
			os.unlink(csv_path)
		self.assertEqual(result["system"], "NAPPI")
		self.assertEqual(result["created"], 2)

	def test_same_code_in_two_systems_does_not_collide(self):
		from medic_plus.api.terminology_import import import_icd10, import_nappi
		# Same literal code "TSTX2.999" goes to both systems. They must
		# coexist as two distinct Code Value rows.
		shared_code_csv = _write_csv([("TSTX2.999", "shared code")])
		try:
			import_icd10(shared_code_csv)
			import_nappi(shared_code_csv)
		finally:
			os.unlink(shared_code_csv)
		self.assertTrue(frappe.db.exists("Code Value", "TSTX2.999-ICD-10-ZA"))
		self.assertTrue(frappe.db.exists("Code Value", "TSTX2.999-NAPPI"))


class TestPerSystemSearchEndpoints(IntegrationTestCase):
	"""Each whitelisted search endpoint scopes to one Code System.

	The SPA pickers (ICD-10, NAPPI, LOINC) call distinct endpoints so a
	user searching for "100" in the LOINC picker never sees an ICD-10
	hit. We test the public endpoint shape via a direct call (the
	whitelist decorator is irrelevant in-process).
	"""

	def setUp(self):
		# Cleanup synthetic test rows
		for stale in frappe.get_all(
			"Code Value",
			filters={"code_value": ["like", "ZTST%"]},
			pluck="name",
		):
			frappe.delete_doc("Code Value", stale, ignore_permissions=True, force=True)
		# Seed one row in each of the four systems with the SAME code prefix
		# so a wrong-system query would surface them.
		for system in ("ICD-10-ZA", "NAPPI", "LOINC", "ATC"):
			frappe.get_doc({
				"doctype": "Code Value",
				"code_system": system,
				"code_value": f"ZTST{system}",
				"display": f"sample for {system}",
			}).insert(ignore_permissions=True)

	def test_search_nappi_returns_only_nappi_rows(self):
		from medic_plus.api.daystar_health import search_nappi
		rows = search_nappi(query="ZTST", limit=10)
		systems = {
			frappe.db.get_value("Code Value", r["name"], "code_system")
			for r in rows
		}
		self.assertTrue(rows, "expected ZTST seed rows")
		self.assertEqual(systems, {"NAPPI"})

	def test_search_loinc_returns_only_loinc_rows(self):
		from medic_plus.api.daystar_health import search_loinc
		rows = search_loinc(query="ZTST", limit=10)
		systems = {
			frappe.db.get_value("Code Value", r["name"], "code_system")
			for r in rows
		}
		self.assertEqual(systems, {"LOINC"})

	def test_search_icd10_now_targets_icd10_za(self):
		# Regression: search_icd10 used to filter on the deprecated "ICD-10"
		# system. Phase 1B repoints it at ICD-10-ZA — the SA-canonical
		# system the SPA picker now drives.
		from medic_plus.api.daystar_health import search_icd10
		rows = search_icd10(query="ZTST", limit=10)
		systems = {
			frappe.db.get_value("Code Value", r["name"], "code_system")
			for r in rows
		}
		self.assertEqual(systems, {"ICD-10-ZA"})
