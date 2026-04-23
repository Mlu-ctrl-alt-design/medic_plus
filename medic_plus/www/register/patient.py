import frappe
from frappe.utils import today


def get_context(context):
	context.no_cache = 1
	context.no_breadcrumbs = 1
	context.sitemap = 0
	context.today = today()
	context.metatags = {
		"title": "Patient Registration — Medic Plus",
		"description": "Create a patient account on Medic Plus to book appointments and manage your health records.",
	}
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/me"
		raise frappe.Redirect

	try:
		context.practices = frappe.get_all(
			"Practice",
			filters={"is_active": 1},
			fields=["name", "practice_name"],
			order_by="practice_name asc",
		)
	except Exception:
		context.practices = []
