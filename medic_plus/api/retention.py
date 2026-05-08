"""Daily scheduler tick that flags patients past the legal retention window.

HPCSA Booklet 9 + National Health Act §17 require patient records to be
kept for a minimum of 6 years from the date of the last entry. Records
of minors must be kept until the patient turns 21 (whichever is later).
This module flags candidates into the Record Archive Queue for human
review — actual archive/destroy is opt-in.
"""

import datetime

import frappe

RETENTION_YEARS = 6
PAEDIATRIC_RETENTION_AGE = 21


def flag_overdue_records() -> int:
	"""Find patients past retention and queue them for review.

	Returns the number of newly-queued rows. Idempotent — patients
	already in the queue are skipped.

	A patient is queueable when:
	  - last activity (currently their Patient row creation) is older
	    than RETENTION_YEARS (6 years), AND
	  - if the patient has a recorded DOB and is younger than
	    PAEDIATRIC_RETENTION_AGE (21), they are NOT queued — minors'
	    records must be kept until the patient turns 21.
	"""
	cutoff = frappe.utils.now_datetime() - datetime.timedelta(days=365 * RETENTION_YEARS)
	overdue_patients = frappe.get_all(
		"Patient",
		filters={"creation": ["<", cutoff]},
		fields=["name", "dob"],
	)
	already_queued = set(frappe.get_all(
		"Record Archive Queue",
		pluck="patient",
		limit=0,
	))
	count = 0
	for row in overdue_patients:
		if _is_minor(row.get("dob")):
			continue
		if row["name"] in already_queued:
			continue
		_queue_for_archive(row["name"])
		count += 1
	return count


def _is_minor(dob) -> bool:
	"""True if the DOB indicates the patient is younger than 21 today."""
	if not dob:
		return False
	if isinstance(dob, str):
		try:
			dob = datetime.date.fromisoformat(dob)
		except ValueError:
			return False
	today = datetime.date.today()
	age = (today.year - dob.year) - ((today.month, today.day) < (dob.month, dob.day))
	return age < PAEDIATRIC_RETENTION_AGE


def _queue_for_archive(patient: str) -> None:
	frappe.get_doc({
		"doctype": "Record Archive Queue",
		"patient": patient,
		"status": "Pending Review",
		"flagged_on": frappe.utils.now_datetime(),
	}).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Phase 1E — POPIA consent record expiry
# ---------------------------------------------------------------------------

# Consent records expire after 3 years of inactivity per POPIA guidance
CONSENT_EXPIRY_YEARS = 3


def flag_expired_consent_records() -> int:
	"""Mark Patient Consent Records as Expired if they exceed the expiry window.

	Called by the daily scheduler.  Only affects Given records — Withdrawn/
	Pending are already terminal or handled by the operator.  Idempotent.
	"""
	if not frappe.db.table_exists("tabPatient Consent Record"):
		return 0

	cutoff = frappe.utils.now_datetime() - datetime.timedelta(
		days=365 * CONSENT_EXPIRY_YEARS
	)
	overdue = frappe.get_all(
		"Patient Consent Record",
		filters={"status": "Given", "consented_on": ["<", cutoff]},
		pluck="name",
		limit=0,
	)
	for name in overdue:
		frappe.db.set_value("Patient Consent Record", name, "status", "Expired")
	if overdue:
		frappe.db.commit()
	return len(overdue)
