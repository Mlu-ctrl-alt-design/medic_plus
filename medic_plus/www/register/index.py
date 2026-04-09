import frappe


def get_context(context):
	context.no_cache = 1
	context.no_breadcrumbs = 1
	context.sitemap = 0
	context.metatags = {
		"title": "Register — Medic Plus",
		"description": "Create your Medic Plus account as a doctor or patient.",
	}
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/me"
		raise frappe.Redirect
