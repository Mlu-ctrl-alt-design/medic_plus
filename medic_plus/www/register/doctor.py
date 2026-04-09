import frappe


def get_context(context):
	context.no_cache = 1
	context.no_breadcrumbs = 1
	context.sitemap = 0
	context.metatags = {
		"title": "Doctor Registration — Medic Plus",
		"description": "Register as a doctor on Medic Plus to set up your practice and manage patients.",
	}
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/me"
		raise frappe.Redirect
