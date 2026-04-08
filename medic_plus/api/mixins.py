import frappe


class PracticeAwareMixin:
	"""v16 mixin — adds practice validation to Patient Appointment."""

	def validate(self):
		super().validate()
		self._validate_practitioner_in_practice()

	def _validate_practitioner_in_practice(self):
		if not self.custom_practice or not self.practitioner:
			return
		is_member = frappe.db.exists(
			"Practice Member",
			{"practice": self.custom_practice, "practitioner": self.practitioner},
		)
		if not is_member and "Healthcare Administrator" not in frappe.get_roles():
			frappe.throw(
				frappe._("Practitioner {0} does not belong to this practice.").format(
					self.practitioner
				),
				title=frappe._("Invalid Practitioner"),
			)
