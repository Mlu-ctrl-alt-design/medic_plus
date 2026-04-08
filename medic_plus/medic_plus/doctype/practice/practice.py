import frappe
from frappe.model.document import Document
import re


class Practice(Document):
	def before_insert(self):
		if not self.slug:
			self.slug = self._generate_slug(self.practice_name)

	def validate(self):
		if not self.slug:
			self.slug = self._generate_slug(self.practice_name)
		self._validate_slug()

	def _generate_slug(self, name: str) -> str:
		slug = name.lower().strip()
		slug = re.sub(r"[^a-z0-9\s-]", "", slug)
		slug = re.sub(r"\s+", "-", slug)
		slug = re.sub(r"-+", "-", slug).strip("-")
		# ensure uniqueness
		base = slug
		counter = 1
		while frappe.db.exists("Practice", {"slug": slug, "name": ("!=", self.name or "")}):
			slug = f"{base}-{counter}"
			counter += 1
		return slug

	def _validate_slug(self):
		if not re.match(r"^[a-z0-9-]+$", self.slug):
			frappe.throw(
				frappe._("Slug can only contain lowercase letters, numbers, and hyphens."),
				title=frappe._("Invalid Slug"),
			)
