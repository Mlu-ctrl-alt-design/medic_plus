import frappe
from frappe.model.document import Document


class PracticeTimeBlock(Document):
	def validate(self):
		if self.end_date and self.end_date < self.block_date:
			frappe.throw(frappe._("End Date cannot be before Date."))
		if not self.is_all_day:
			if self.from_time and self.to_time and self.to_time <= self.from_time:
				frappe.throw(frappe._("To time must be after From time."))
