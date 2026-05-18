import frappe
from frappe import _


def _require_practice_member():
	"""Return the current user's practice or throw if they have none."""
	practice = frappe.db.get_value(
		"Practice Member", {"user": frappe.session.user}, "practice"
	)
	if not practice:
		frappe.throw(_("No practice found for your account."), frappe.PermissionError)
	return practice


@frappe.whitelist()
def get_issues():
	"""List all Issues raised by this practice, newest first."""
	practice = _require_practice_member()
	issues = frappe.get_all(
		"Issue",
		filters={"custom_practice": practice},
		fields=["name", "subject", "status", "priority", "opening_date", "raised_by", "creation"],
		order_by="creation desc",
	)
	return issues


@frappe.whitelist()
def get_issue_detail(issue_name: str):
	"""Return full issue + its communication thread."""
	practice = _require_practice_member()
	issue = frappe.get_doc("Issue", issue_name)
	if issue.custom_practice != practice:
		frappe.throw(_("Access denied."), frappe.PermissionError)

	thread = frappe.get_all(
		"Communication",
		filters={"reference_doctype": "Issue", "reference_name": issue_name},
		fields=["sender_full_name", "sender", "content", "sent_or_received", "creation"],
		order_by="creation asc",
	)
	return {"issue": issue.as_dict(), "thread": thread}


@frappe.whitelist()
def create_issue(subject: str, description: str, priority: str = None):
	"""Open a new support issue for the current user's practice."""
	if not subject or not description:
		frappe.throw(_("Subject and description are required."))

	practice = _require_practice_member()
	issue = frappe.get_doc(
		{
			"doctype": "Issue",
			"subject": subject,
			"description": description,
			"raised_by": frappe.session.user,
			"custom_practice": practice,
			"status": "Open",
		}
	)
	if priority:
		issue.priority = priority
	issue.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": issue.name, "status": issue.status}


@frappe.whitelist()
def update_issue_status(issue_name: str, status: str):
	"""Close or reopen an issue (only the owning practice may do this)."""
	allowed = {"Closed", "Open"}
	if status not in allowed:
		frappe.throw(_("Status must be one of: {0}").format(", ".join(allowed)))

	practice = _require_practice_member()
	issue = frappe.get_doc("Issue", issue_name)
	if issue.custom_practice != practice:
		frappe.throw(_("Access denied."), frappe.PermissionError)

	issue.status = status
	issue.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": issue.name, "status": issue.status}
