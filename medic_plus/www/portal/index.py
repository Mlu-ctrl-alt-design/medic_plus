import frappe
from frappe.utils import today


def get_context(context):
	context.no_cache = 1
	context.no_breadcrumbs = 1
	context.sitemap = 0

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/portal"
		raise frappe.Redirect

	patient = frappe.db.get_value(
		"Patient",
		{"email": frappe.session.user},
		["name", "patient_name", "custom_practice"],
		as_dict=True,
	)

	context.patient = patient

	if not patient:
		context.upcoming = []
		context.past = []
		context.sick_notes = []
		context.practice_name = None
		return

	context.upcoming = frappe.get_all(
		"Patient Appointment",
		filters={
			"patient": patient.name,
			"appointment_date": [">=", today()],
			"status": ["not in", ["Cancelled"]],
		},
		fields=["name", "practitioner_name", "appointment_date", "appointment_time", "status"],
		order_by="appointment_date asc",
		limit=20,
	)

	context.past = frappe.get_all(
		"Patient Appointment",
		filters={
			"patient": patient.name,
			"appointment_date": ["<", today()],
		},
		fields=["name", "practitioner_name", "appointment_date", "appointment_time", "status"],
		order_by="appointment_date desc",
		limit=20,
	)

	context.sick_notes = frappe.get_all(
		"Sick Note",
		filters={"patient": patient.name, "docstatus": 1},
		fields=["name", "date_issued", "practitioner", "diagnosis", "days_off", "fit_for_work_date"],
		order_by="date_issued desc",
		limit=50,
	)

	context.practice_name = (
		frappe.db.get_value("Practice", patient.custom_practice, "practice_name")
		if patient.custom_practice else None
	)
