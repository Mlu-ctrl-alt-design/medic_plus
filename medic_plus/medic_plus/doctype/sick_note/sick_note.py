import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, today


class SickNote(Document):
	def before_insert(self):
		self._set_practice_from_context()
		self._fetch_practitioner_details()

	def validate(self):
		self._calculate_days_off()
		self._validate_dates()
		self._validate_practice_access()

	def on_submit(self):
		self._create_patient_medical_record()

	# ------------------------------------------------------------------
	# Private
	# ------------------------------------------------------------------

	def _set_practice_from_context(self):
		if not self.practice:
			practice = frappe.db.get_value(
				"Practice Member", {"user": frappe.session.user}, "practice"
			)
			if practice:
				self.practice = practice

	def _fetch_practitioner_details(self):
		"""Copy HPCSA number, practice number, and signature from the linked
		Healthcare Practitioner so they are embedded in the Sick Note at the
		time of issue (snapshot — stays accurate even if the practitioner
		record is later updated)."""
		if not self.practitioner:
			return
		practitioner = frappe.get_value(
			"Healthcare Practitioner",
			self.practitioner,
			[
				"custom_hpcsa_number",
				"custom_practice_number",
				"custom_practitioner_signature",
			],
			as_dict=True,
		)
		if not practitioner:
			return
		if not self.hpcsa_number:
			self.hpcsa_number = practitioner.custom_hpcsa_number
		if not self.practice_number:
			self.practice_number = practitioner.custom_practice_number
		if not self.practitioner_signature:
			self.practitioner_signature = practitioner.custom_practitioner_signature

	def _calculate_days_off(self):
		if self.date_issued and self.fit_for_work_date:
			self.days_off = date_diff(self.fit_for_work_date, self.date_issued)
			if self.days_off < 0:
				frappe.throw(
					frappe._("Fit for Work Date must be after Date Issued."),
					title=frappe._("Invalid Dates"),
				)

	def _validate_dates(self):
		if self.date_issued and self.date_issued > today():
			frappe.throw(
				frappe._("Date Issued cannot be in the future."),
				title=frappe._("Invalid Date"),
			)

	def _validate_practice_access(self):
		if "Healthcare Administrator" in frappe.get_roles():
			return
		member = frappe.db.get_value(
			"Practice Member",
			{"user": frappe.session.user, "practice": self.practice},
			"role",
		)
		if not member:
			frappe.throw(
				frappe._("You do not have access to practice {0}.").format(self.practice),
				title=frappe._("Access Denied"),
			)

	def _create_patient_medical_record(self):
		frappe.get_doc(
			{
				"doctype": "Patient Medical Record",
				"patient": self.patient,
				"document_type": "Sick Note",
				"document": self.name,
				"date": self.date_issued,
			}
		).insert(ignore_permissions=True)
