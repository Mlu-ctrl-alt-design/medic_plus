import frappe


def get_context(context):
	context.no_cache = 1
	context.no_breadcrumbs = 1
	context.sitemap = 0
	context.request_name = frappe.form_dict.get("req", "")
