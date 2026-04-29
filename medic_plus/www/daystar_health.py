import frappe

from medic_plus.api.practice_resolver import get_active_practice

no_cache = 1


def get_context(context):
	"""Bootstrap the Daystar Health SPA with session + CSRF state.

	The SPA decides its first-render route from `session_user` and `has_practice`
	and uses `csrf_token` for non-GET API calls. Resolving here avoids an
	additional client-side round trip to determine login state on first paint.
	"""
	context.no_cache = 1
	context.session_user = frappe.session.user

	try:
		get_active_practice()
		context.has_practice = True
	except frappe.PermissionError:
		context.has_practice = False

	context.csrf_token = frappe.sessions.get_csrf_token()
	return context
