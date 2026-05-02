import frappe
from frappe.model.document import Document


class DrugMaster(Document):
	def before_save(self):
		if self.nappi_code_value:
			cv = frappe.db.get_value(
				"Code Value", self.nappi_code_value, ["code_value", "display"], as_dict=True
			)
			if cv:
				self.nappi_code = cv.code_value
				if not self.drug_name:
					self.drug_name = cv.display
		if self.atc_code_value:
			self.atc_code = (
				frappe.db.get_value("Code Value", self.atc_code_value, "code_value") or ""
			)
