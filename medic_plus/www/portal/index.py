import frappe


def get_context(context):
	context.no_cache = 1
	context.no_breadcrumbs = 1
	context.sitemap = 0

	slug = (frappe.form_dict.get("slug") or "").strip()
	context.slug = slug
	context.session_user = frappe.session.user if frappe.session.user != "Guest" else None
	csrf = ""
	session = getattr(frappe.local, "session", None)
	if session and getattr(session, "data", None):
		csrf = session.data.get("csrf_token") or ""
	context.csrf_token = csrf

	# If no slug — render the resolver page; the SPA boot script handles routing.
	if not slug:
		context.practice = None
		context.is_authed = bool(context.session_user)
		context.has_patient = False
		return

	practice = frappe.db.get_value(
		"Practice",
		{"slug": slug, "is_active": 1},
		["name", "practice_name", "logo", "color", "email", "slug"],
		as_dict=True,
	)
	context.practice = practice

	context.is_authed = bool(context.session_user)
	context.has_patient = False
	if practice and context.session_user:
		context.has_patient = bool(frappe.db.exists(
			"Patient",
			{"email": context.session_user, "custom_practice": practice.name},
		))
