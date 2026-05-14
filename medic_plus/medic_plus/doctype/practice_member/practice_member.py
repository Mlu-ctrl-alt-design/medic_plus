import frappe
from frappe import _
from frappe.model.document import Document


class PracticeMember(Document):
	def validate(self):
		if self.role == "Doctor" and not self.practitioner:
			frappe.throw(
				_("Healthcare Practitioner is required when Role is Doctor."),
				title=_("Missing Practitioner"),
			)
		self._prevent_duplicate()

	def after_insert(self):
		if self.user:
			self._assign_frappe_role()

	def on_update(self):
		if self.user and self.has_value_changed("role"):
			self._assign_frappe_role()

	def on_trash(self):
		if self.user:
			self._remove_frappe_role()

	# ------------------------------------------------------------------
	# Frappe role management
	# ------------------------------------------------------------------

	def _get_frappe_role(self) -> str:
		role_map = {
			"Admin": "Practice Admin",
			"Doctor": "Practice Doctor",
			"Receptionist": "Practice Receptionist",
		}
		return role_map.get(self.role, "")

	def _assign_frappe_role(self):
		frappe_role = self._get_frappe_role()
		if not frappe_role or not self.user:
			return
		user = frappe.get_doc("User", self.user)
		existing_roles = [r.role for r in user.roles]
		if frappe_role not in existing_roles:
			user.append("roles", {"role": frappe_role})
			user.save(ignore_permissions=True)

	def _remove_frappe_role(self):
		frappe_role = self._get_frappe_role()
		if not frappe_role or not self.user:
			return
		other_memberships = frappe.db.count(
			"Practice Member",
			{"user": self.user, "role": self.role, "name": ("!=", self.name)},
		)
		if other_memberships == 0:
			user = frappe.get_doc("User", self.user)
			user.roles = [r for r in user.roles if r.role != frappe_role]
			user.save(ignore_permissions=True)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _prevent_duplicate(self):
		if not (self.practice and self.user):
			return
		existing = frappe.db.exists(
			"Practice Member",
			{"practice": self.practice, "user": self.user, "name": ("!=", self.name or "")},
		)
		if existing:
			frappe.throw(
				_("This user is already a member of this practice."),
				title=_("Duplicate Member"),
			)
