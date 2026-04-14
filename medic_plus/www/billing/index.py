import frappe


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = f"/login?redirect-to=/billing"
        raise frappe.Redirect

    # Only Practice Admins and Healthcare Administrators can view billing
    roles = frappe.get_roles(frappe.session.user)
    if not any(r in roles for r in ("Practice Admin", "Healthcare Administrator", "Administrator")):
        frappe.throw("You do not have permission to view billing.", frappe.PermissionError)

    context.no_cache = 1
    context.show_sidebar = False
    context.title = "Subscription & Billing"
