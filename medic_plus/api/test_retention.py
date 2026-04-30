"""TDD: medic_plus.api.retention.flag_overdue_records.

Phase 1 acceptance criterion (#18) — daily scheduler tick that flags
patients whose latest clinical-record activity exceeds the legal
retention window (HPCSA Booklet 9 / National Health Act §17 — 6
years from the date of the last entry, except minors where retention
runs to age 21).

Tests are tracer-bulletted: one behaviour at a time, drive the
implementation forward only as much as each new test demands.
"""

import datetime

import frappe
from frappe.tests import IntegrationTestCase


def _suffix() -> str:
	return frappe.generate_hash(length=6)


def _make_patient(*, label: str, dob: str | None = None) -> str:
	first_name = f"Retention Patient {label}"
	existing = frappe.db.get_value("Patient", {"first_name": first_name}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "Patient",
		"first_name": first_name,
		"sex": "Female",
		"dob": dob,
	}).insert(ignore_permissions=True).name


def _backdate_creation(doctype: str, name: str, days_ago: int) -> None:
	"""Force a row's creation timestamp into the past for retention tests.

	Frappe stamps `creation` automatically on insert; we have to drop into
	SQL to push it backwards.
	"""
	cutoff = frappe.utils.now_datetime() - datetime.timedelta(days=days_ago)
	frappe.db.sql(
		f"UPDATE `tab{doctype}` SET creation=%s, modified=%s WHERE name=%s",
		(cutoff, cutoff, name),
	)
	frappe.db.commit()


class TestRetentionTracer(IntegrationTestCase):
	"""Tracer: patient with last activity > 6 years ago is queued for archive."""

	def test_patient_with_7y_old_activity_lands_in_archive_queue(self):
		from medic_plus.api.retention import flag_overdue_records

		s = _suffix()
		patient = _make_patient(label=f"7y-{s}")
		# Backdate the Patient row itself — this acts as 'last activity'
		# until linked-clinical-doc lookup is added (a later test).
		_backdate_creation("Patient", patient, days_ago=365 * 7)

		flag_overdue_records()

		queue_rows = frappe.get_all(
			"Record Archive Queue",
			filters={"patient": patient},
			fields=["name", "status"],
		)
		self.assertEqual(len(queue_rows), 1, f"expected 1 queue row, got {queue_rows}")
		self.assertEqual(queue_rows[0]["status"], "Pending Review")


class TestRetentionExclusion(IntegrationTestCase):
	"""Patients still inside the retention window must NOT be queued."""

	def test_patient_with_5y_old_activity_does_not_land_in_archive_queue(self):
		from medic_plus.api.retention import flag_overdue_records

		s = _suffix()
		patient = _make_patient(label=f"5y-{s}")
		_backdate_creation("Patient", patient, days_ago=365 * 5)

		flag_overdue_records()

		queue_rows = frappe.get_all(
			"Record Archive Queue",
			filters={"patient": patient},
			fields=["name"],
		)
		self.assertEqual(queue_rows, [], "5-year-old patient must not be queued")


class TestPaediatricRetention(IntegrationTestCase):
	"""Records of minors must be retained until the patient turns 21."""

	def test_minor_with_7y_old_activity_still_under_21_is_NOT_queued(self):
		from medic_plus.api.retention import flag_overdue_records

		s = _suffix()
		# DOB ~14 years ago: patient is currently 14, will turn 21 in 7 years.
		# Even though their last activity is 7 years old (which would
		# normally trigger queueing), retention must run to age 21.
		fourteen_years_ago = (datetime.date.today() - datetime.timedelta(days=365 * 14)).isoformat()
		patient = _make_patient(label=f"minor-{s}", dob=fourteen_years_ago)
		_backdate_creation("Patient", patient, days_ago=365 * 7)

		flag_overdue_records()

		queue_rows = frappe.get_all(
			"Record Archive Queue",
			filters={"patient": patient},
			fields=["name"],
		)
		self.assertEqual(queue_rows, [], "minor's record must not be queued before age 21")


class TestRetentionIdempotency(IntegrationTestCase):
	"""Re-running the scheduler tick must not duplicate queue rows."""

	def test_double_run_does_not_duplicate_queue_row(self):
		from medic_plus.api.retention import flag_overdue_records

		s = _suffix()
		patient = _make_patient(label=f"idem-{s}")
		_backdate_creation("Patient", patient, days_ago=365 * 7)

		flag_overdue_records()
		flag_overdue_records()

		queue_rows = frappe.get_all(
			"Record Archive Queue",
			filters={"patient": patient},
			fields=["name"],
		)
		self.assertEqual(len(queue_rows), 1, f"expected 1 queue row, got {queue_rows}")
