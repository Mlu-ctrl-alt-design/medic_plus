"""
Practice Setup Checklist controller.

One checklist record per Practice. Created automatically when a Practice
is provisioned. Steps are updated in real-time via doc_events hooks on
the relevant doctypes.

Step evaluation logic lives here so it can be called from:
  - after_insert hooks on triggering doctypes
  - a future scheduled job for reconciliation
"""

import frappe
from frappe.model.document import Document


STEP_FIELDS = [
	"step_practice_profile",
	"step_signature",
	"step_staff_invited",
	"step_patients_invited",
	"step_appointments",
	"step_billing",
	"step_clinical_templates",
	"step_medical_aid",
]


class PracticeSetupChecklist(Document):
	def before_save(self):
		self._recompute_progress()

	def _recompute_progress(self):
		completed = sum(1 for f in STEP_FIELDS if self.get(f))
		total = len(STEP_FIELDS)
		self.completion_pct = round((completed / total) * 100)
		# current_step = index (1-based) of first unchecked step, or total+1 if all done
		self.current_step = next(
			(i + 1 for i, f in enumerate(STEP_FIELDS) if not self.get(f)),
			total + 1,
		)


# ---------------------------------------------------------------------------
# Public helpers — called from doc_events hooks
# ---------------------------------------------------------------------------

def _get_checklist(practice: str) -> "PracticeSetupChecklist | None":
	name = frappe.db.get_value("Practice Setup Checklist", {"practice": practice}, "name")
	if not name:
		return None
	return frappe.get_doc("Practice Setup Checklist", name)


def _tick(practice: str, field: str) -> None:
	"""Set a checklist step to 1 and save. No-op if already set."""
	checklist = _get_checklist(practice)
	if not checklist or checklist.get(field):
		return
	checklist.set(field, 1)
	checklist.save(ignore_permissions=True)


def on_practice_profile_complete(practice: str) -> None:
	"""Step 1 — called after Practice name/contact details are saved."""
	_tick(practice, "step_practice_profile")


def on_signature_saved(practice: str) -> None:
	"""Step 2 — called when a practitioner saves a signature for this practice."""
	_tick(practice, "step_signature")


def on_staff_accepted(practice: str) -> None:
	"""Step 3 — called when any staff Practice Member reaches status=Accepted."""
	_tick(practice, "step_staff_invited")


def on_patient_invited(practice: str) -> None:
	"""Step 4 — called when any patient Practice Member reaches status=Sent."""
	_tick(practice, "step_patients_invited")


def on_schedule_created(practice: str) -> None:
	"""Step 5 — called when a Practitioner Schedule is created for this practice."""
	_tick(practice, "step_appointments")


def on_billing_configured(practice: str) -> None:
	"""Step 6 — called when the first Item Price is created under this practice's company."""
	_tick(practice, "step_billing")


def on_clinical_template_saved(practice: str) -> None:
	"""Step 7 — called when a Clinical Note Template is created for this practice."""
	_tick(practice, "step_clinical_templates")


def on_medical_aid_connected(practice: str) -> None:
	"""Step 8 — called when a switching house credential is saved for this practice."""
	_tick(practice, "step_medical_aid")
