import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url
from medic_plus.medic_plus.doctype.practice_setup_checklist.practice_setup_checklist import (
	on_staff_accepted,
	on_patient_invited,
)


class PracticeMember(Document):
	def validate(self):
		if self.role == "Doctor" and not self.practitioner:
			frappe.throw(
				_("Healthcare Practitioner is required when Role is Doctor."),
				title=_("Missing Practitioner"),
			)
		self._prevent_duplicate()

	def after_insert(self):
		if self.status == "Pending":
			self._run_invitation_flow()
		elif self.user:
			self._assign_frappe_role()

	def on_update(self):
		if self.user and self.has_value_changed("role"):
			self._assign_frappe_role()

	def on_trash(self):
		if self.user:
			self._remove_frappe_role()

	# ------------------------------------------------------------------
	# Invitation flow
	# ------------------------------------------------------------------

	def _run_invitation_flow(self):
		"""Dispatch to staff or patient invitation based on role."""
		if self.role == "Patient":
			self._invite_patient()
		else:
			self._invite_staff()

	def _invite_staff(self):
		"""Create a Frappe User for the staff member and send the invitation email."""
		first_name, last_name = self._split_name()

		# Create User if one doesn't already exist for this email
		if frappe.db.exists("User", self.email):
			user_doc = frappe.get_doc("User", self.email)
		else:
			user_doc = frappe.get_doc({
				"doctype": "User",
				"email": self.email,
				"first_name": first_name,
				"last_name": last_name,
				"send_welcome_email": 0,
				"mobile_no": self.mobile_number or "",
			})
			user_doc.insert(ignore_permissions=True)

		frappe_role = self._get_frappe_role()
		if frappe_role:
			existing_roles = [r.role for r in user_doc.roles]
			if frappe_role not in existing_roles:
				user_doc.append("roles", {"role": frappe_role})
				user_doc.save(ignore_permissions=True)

		# Generate a password-reset key so staff can set their own password on first login
		user_doc.reset_password()

		frappe.db.set_value("Practice Member", self.name, {
			"user": user_doc.name,
			"status": "Sent",
			"invitation_sent_on": now_datetime(),
		})

		self._send_staff_invitation_email(user_doc)
		on_staff_accepted(self.practice)

	def _invite_patient(self):
		"""Create a Patient record (no User account in Phase 2) and send confirmation email."""
		practice_doc = frappe.get_doc("Practice", self.practice)

		first_name, last_name = self._split_name()

		# Create Patient record scoped to this practice.
		# sex defaults to "Other" — doctors can correct it on the Patient form.
		patient_doc = frappe.get_doc({
			"doctype": "Patient",
			"first_name": first_name,
			"last_name": last_name,
			"patient_name": self.full_name,
			"email": self.email,
			"mobile": self.mobile_number or "",
			"sex": "Other",
			"custom_practice": self.practice,
		})
		patient_doc.insert(ignore_permissions=True)

		frappe.db.set_value("Practice Member", self.name, {
			"patient_record": patient_doc.name,
			"status": "Sent",
			"invitation_sent_on": now_datetime(),
		})

		self._send_patient_invitation_email(practice_doc)
		on_patient_invited(self.practice)

	# ------------------------------------------------------------------
	# Email senders
	# ------------------------------------------------------------------

	def _send_staff_invitation_email(self, user_doc):
		practice_doc = frappe.get_doc("Practice", self.practice)
		practitioner_name = self._get_practitioner_name()

		frappe.sendmail(
			recipients=[self.email],
			subject=_("You've been invited to join {0} on PracticeManager").format(
				practice_doc.practice_name
			),
			message=_(
				"""<p>Hi {full_name},</p>
<p>Dr {practitioner_name} has invited you to join <strong>{practice_name}</strong>
as a <strong>{role}</strong>.</p>
<p>You can log in using your work email address:</p>
<ul>
  <li><strong>Email:</strong> {email}</li>
  <li><strong>Login URL:</strong> <a href="{url}/login">{url}/login</a></li>
</ul>
<p>You will be prompted to set your password on first login.</p>
<p>— The PracticeManager Team</p>"""
			).format(
				full_name=self.full_name,
				practitioner_name=practitioner_name,
				practice_name=practice_doc.practice_name,
				role=self.role,
				email=self.email,
				url=get_url(),
			),
		)

	def _send_patient_invitation_email(self, practice_doc):
		practitioner_name = self._get_practitioner_name()

		frappe.sendmail(
			recipients=[self.email],
			subject=_("You are now a registered patient at {0}").format(
				practice_doc.practice_name
			),
			message=_(
				"""<p>Hi {full_name},</p>
<p>You have been registered as a patient at <strong>{practice_name}</strong>
under the care of <strong>Dr {practitioner_name}</strong>.</p>
<p>Your medical records are now managed digitally through PracticeManager.
Your doctor will be in touch regarding your next appointment.</p>
<p>If you did not expect this email, please contact {practice_name} directly.</p>
<p>— The PracticeManager Team</p>"""
			).format(
				full_name=self.full_name,
				practitioner_name=practitioner_name,
				practice_name=practice_doc.practice_name,
			),
		)

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
		# Duplicate check by email within same practice
		existing = frappe.db.exists(
			"Practice Member",
			{"practice": self.practice, "email": self.email, "name": ("!=", self.name or "")},
		)
		if existing:
			frappe.throw(
				_("A member with email {0} already exists in this practice.").format(self.email),
				title=_("Duplicate Member"),
			)

	def _split_name(self) -> tuple[str, str]:
		parts = (self.full_name or "").strip().split(" ", 1)
		first = parts[0]
		last = parts[1] if len(parts) > 1 else ""
		return first, last

	def _get_practitioner_name(self) -> str:
		"""Return the name of the Doctor/Admin who owns this practice."""
		doctor_member = frappe.db.get_value(
			"Practice Member",
			{"practice": self.practice, "role": "Doctor"},
			["full_name", "practitioner"],
			as_dict=True,
		)
		if doctor_member and doctor_member.practitioner:
			return frappe.db.get_value(
				"Healthcare Practitioner", doctor_member.practitioner, "practitioner_name"
			) or doctor_member.full_name
		return doctor_member.full_name if doctor_member else "Your Doctor"
