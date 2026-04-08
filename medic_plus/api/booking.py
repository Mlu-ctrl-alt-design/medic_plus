import frappe
from frappe.utils import getdate, nowdate, get_time


@frappe.whitelist(allow_guest=True)
def get_practice_info(practice_slug: str) -> dict:
	"""Return public practice info for the booking page."""
	practice = frappe.db.get_value(
		"Practice",
		{"slug": practice_slug, "is_active": 1},
		["name", "practice_name", "logo", "color", "phone", "email", "address"],
		as_dict=True,
	)
	if not practice:
		frappe.throw(frappe._("Practice not found."), frappe.DoesNotExistError)
	return practice


@frappe.whitelist(allow_guest=True)
def get_practice_practitioners(practice_slug: str) -> list:
	"""Return active doctors for a practice."""
	practice = frappe.db.get_value("Practice", {"slug": practice_slug, "is_active": 1}, "name")
	if not practice:
		frappe.throw(frappe._("Practice not found."), frappe.DoesNotExistError)

	members = frappe.get_all(
		"Practice Member",
		filters={"practice": practice, "role": "Doctor"},
		fields=["practitioner"],
	)
	practitioner_names = [m.practitioner for m in members if m.practitioner]
	if not practitioner_names:
		return []

	practitioners = frappe.get_all(
		"Healthcare Practitioner",
		filters={"name": ("in", practitioner_names), "status": "Active"},
		fields=["name", "practitioner_name", "department", "image"],
	)
	return practitioners


@frappe.whitelist(allow_guest=True)
def get_availability(practice_slug: str, practitioner: str, date: str) -> list:
	"""Return available time slots for a practitioner on a given date."""
	practice = frappe.db.get_value("Practice", {"slug": practice_slug, "is_active": 1}, "name")
	if not practice:
		frappe.throw(frappe._("Practice not found."), frappe.DoesNotExistError)

	# Verify practitioner belongs to this practice
	is_member = frappe.db.exists(
		"Practice Member",
		{"practice": practice, "practitioner": practitioner, "role": "Doctor"},
	)
	if not is_member:
		frappe.throw(frappe._("Practitioner not found in this practice."), frappe.DoesNotExistError)

	# Fetch existing appointments for that day
	booked_times = frappe.get_all(
		"Patient Appointment",
		filters={
			"practitioner": practitioner,
			"appointment_date": date,
			"status": ("not in", ["Cancelled"]),
		},
		pluck="appointment_time",
	)

	# Get practitioner schedule
	schedule_name = frappe.db.get_value(
		"Healthcare Practitioner", practitioner, "practitioner_schedules"
	)
	if not schedule_name:
		return []

	day_of_week = getdate(date).strftime("%A")
	time_slots = frappe.get_all(
		"Practitioner Schedule",
		filters={"name": schedule_name},
		fields=["*"],
	)

	# Build available slots (simplified - 30 min intervals 08:00–17:00)
	available = []
	from datetime import datetime, timedelta

	start = datetime.strptime("08:00:00", "%H:%M:%S")
	end = datetime.strptime("17:00:00", "%H:%M:%S")
	slot = start
	while slot < end:
		slot_str = slot.strftime("%H:%M:%S")
		if slot_str not in [str(t) for t in booked_times]:
			available.append(slot_str)
		slot += timedelta(minutes=30)

	return available


@frappe.whitelist(allow_guest=True)
def create_appointment(
	practice_slug: str,
	practitioner: str,
	appointment_date: str,
	appointment_time: str,
	patient_first_name: str,
	patient_last_name: str,
	patient_email: str,
	patient_phone: str,
	appointment_type: str = None,
) -> dict:
	"""Create a patient appointment from the public booking page."""
	practice = frappe.db.get_value(
		"Practice",
		{"slug": practice_slug, "is_active": 1},
		["name", "practice_name"],
		as_dict=True,
	)
	if not practice:
		frappe.throw(frappe._("Practice not found."), frappe.DoesNotExistError)

	# Find or create patient by email
	patient_name = frappe.db.get_value("Patient", {"email": patient_email}, "name")
	if not patient_name:
		patient = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": patient_first_name,
				"last_name": patient_last_name,
				"email": patient_email,
				"mobile": patient_phone,
				"custom_practice": practice.name,
				"status": "Active",
			}
		)
		patient.insert(ignore_permissions=True)
		patient_name = patient.name
	else:
		# Link patient to practice if not already
		existing_practice = frappe.db.get_value("Patient", patient_name, "custom_practice")
		if not existing_practice:
			frappe.db.set_value("Patient", patient_name, "custom_practice", practice.name)

	# Create appointment
	appointment = frappe.get_doc(
		{
			"doctype": "Patient Appointment",
			"patient": patient_name,
			"practitioner": practitioner,
			"appointment_date": appointment_date,
			"appointment_time": appointment_time,
			"appointment_type": appointment_type,
			"custom_practice": practice.name,
			"status": "Open",
		}
	)
	appointment.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"appointment": appointment.name,
		"patient": patient_name,
		"message": frappe._("Your appointment has been booked. Reference: {0}").format(
			appointment.name
		),
	}
