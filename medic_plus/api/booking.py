import random
import frappe
from frappe.utils import getdate, nowdate


# ---------------------------------------------------------------------------
# OTP helpers
# ---------------------------------------------------------------------------

def _otp_cache_key(practice_slug: str, email: str) -> str:
	return f"medic_plus_otp|{practice_slug}|{email.lower().strip()}"


def _attempt_cache_key(practice_slug: str, email: str) -> str:
	return f"medic_plus_otp_attempts|{practice_slug}|{email.lower().strip()}"


def _get_practice_or_throw(practice_slug: str) -> dict:
	practice = frappe.db.get_value(
		"Practice",
		{"slug": practice_slug, "is_active": 1},
		["name", "practice_name", "logo", "color", "email"],
		as_dict=True,
	)
	if not practice:
		frappe.throw(frappe._("Practice not found."), frappe.DoesNotExistError)
	return practice


def _practice_display_name(practice: dict) -> str:
	"""Patient-facing name for a practice.

	Prefers the matching ERPNext Company name so emails reflect the legal
	entity; falls back to the practice's own name when no Company matches.
	"""
	company_name = frappe.db.get_value(
		"Company", {"company_name": practice.practice_name}, "company_name"
	)
	return company_name or practice.practice_name


# ---------------------------------------------------------------------------
# OTP: request
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def request_booking_otp(practice_slug: str, email: str) -> dict:
	"""Generate a 6-digit OTP, store server-side in Redis, and email it to the patient."""
	practice = _get_practice_or_throw(practice_slug)
	email = email.lower().strip()

	# Rate limit: max 3 requests per 10 min per email/practice
	attempt_key = _attempt_cache_key(practice_slug, email)
	attempts = frappe.cache.get_value(attempt_key) or 0
	if attempts >= 3:
		frappe.throw(
			frappe._("Too many OTP requests. Please wait 10 minutes before trying again."),
			title=frappe._("Rate Limited"),
		)

	otp = str(random.randint(100000, 999999))
	cache_key = _otp_cache_key(practice_slug, email)

	# Store OTP server-side — 10 minute TTL
	frappe.cache.set_value(cache_key, otp, expires_in_sec=600)
	frappe.cache.set_value(attempt_key, attempts + 1, expires_in_sec=600)

	# Send email
	_send_otp_email(email=email, otp=otp, practice=practice)

	return {"sent": True, "message": frappe._("OTP sent to {0}").format(email)}


def _send_otp_email(email: str, otp: str, practice: dict):
	display_name = _practice_display_name(practice)
	subject = frappe._("Your booking verification code — {0}").format(display_name)
	message = f"""
	<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;border:1px solid #e5e7eb;border-radius:8px;">
		{"<img src='" + practice.logo + "' style='height:48px;margin-bottom:24px;display:block;' alt='" + display_name + "'>" if practice.logo else ""}
		<h2 style="margin:0 0 8px;font-size:1.2rem;color:#111;">{display_name}</h2>
		<p style="color:#555;margin:0 0 24px;">Use the code below to confirm your appointment booking. It expires in <strong>10 minutes</strong>.</p>
		<div style="background:#f3f4f6;border-radius:8px;padding:20px;text-align:center;letter-spacing:0.3em;font-size:2rem;font-weight:700;color:#111;">
			{otp}
		</div>
		<p style="color:#999;font-size:0.8rem;margin:24px 0 0;">If you did not request this code, you can safely ignore this email.</p>
	</div>
	"""
	frappe.sendmail(
		recipients=[email],
		subject=subject,
		message=message,
		now=True,
	)


# ---------------------------------------------------------------------------
# OTP: verify + create appointment atomically
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def verify_and_book(
	practice_slug: str,
	otp: str,
	practitioner: str,
	appointment_date: str,
	appointment_time: str,
	patient_first_name: str,
	patient_last_name: str,
	patient_email: str,
	patient_phone: str,
	patient_gender: str = "Prefer not to say",
	appointment_type: str = None,
) -> dict:
	"""Verify OTP then create the appointment in a single call."""
	practice = _get_practice_or_throw(practice_slug)
	email = patient_email.lower().strip()

	cache_key = _otp_cache_key(practice_slug, email)
	stored_otp = frappe.cache.get_value(cache_key)

	if not stored_otp:
		frappe.throw(
			frappe._("OTP has expired. Please request a new one."),
			title=frappe._("OTP Expired"),
		)

	if otp.strip() != stored_otp:
		frappe.throw(
			frappe._("Invalid OTP. Please check your email and try again."),
			title=frappe._("Invalid OTP"),
		)

	# OTP verified — consume it immediately so it can't be reused
	frappe.cache.delete_key(cache_key)
	frappe.cache.delete_key(_attempt_cache_key(practice_slug, email))

	# Find or create patient
	patient_name = frappe.db.get_value("Patient", {"email": email}, "name")
	if not patient_name:
		patient = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": patient_first_name,
				"last_name": patient_last_name,
				"sex": patient_gender,
				"email": email,
				"mobile": patient_phone,
				"custom_practice": practice.name,
				"status": "Active",
				# Do not invite the patient as a Frappe user — booking portal
				# patients are anonymous guests, not Desk users.
				"invite_user": 0,
			}
		)
		patient.insert(ignore_permissions=True)
		patient_name = patient.name
	else:
		existing_practice = frappe.db.get_value("Patient", patient_name, "custom_practice")
		if not existing_practice:
			frappe.db.set_value("Patient", patient_name, "custom_practice", practice.name)

	# Resolve appointment type — fall back to "Consultation" if none passed
	resolved_type = appointment_type or frappe.db.get_value(
		"Appointment Type", {"name": "Consultation"}, "name"
	) or frappe.db.get_value("Appointment Type", {}, "name")

	# Create appointment — duration must be > 0, appointment_for and
	# appointment_type are mandatory in Healthcare.
	appointment = frappe.get_doc(
		{
			"doctype": "Patient Appointment",
			"patient": patient_name,
			"practitioner": practitioner,
			"appointment_for": "Practitioner",
			"appointment_date": appointment_date,
			"appointment_time": appointment_time,
			"duration": 30,
			"appointment_type": resolved_type,
			"custom_practice": practice.name,
			"status": "Open",
		}
	)
	appointment.insert(ignore_permissions=True)

	# Send confirmation email
	_send_confirmation_email(
		email=email,
		patient_name=f"{patient_first_name} {patient_last_name}",
		appointment=appointment,
		practice=practice,
	)

	frappe.db.commit()

	return {
		"appointment": appointment.name,
		"patient": patient_name,
		"message": frappe._("Appointment confirmed! Reference: {0}. A confirmation has been sent to {1}.").format(
			appointment.name, email
		),
	}


def _send_confirmation_email(email: str, patient_name: str, appointment, practice: dict):
	display_name = _practice_display_name(practice)
	subject = frappe._("Appointment Confirmed — {0}").format(display_name)
	message = f"""
	<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;border:1px solid #e5e7eb;border-radius:8px;">
		{"<img src='" + practice.logo + "' style='height:48px;margin-bottom:24px;display:block;' alt='" + display_name + "'>" if practice.logo else ""}
		<h2 style="margin:0 0 8px;font-size:1.2rem;color:#111;">Appointment Confirmed</h2>
		<p style="color:#555;margin:0 0 24px;">Hi {patient_name}, your appointment has been booked successfully.</p>
		<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
			<tr><td style="padding:8px 0;color:#888;width:40%;">Practice</td><td style="color:#111;font-weight:500;">{display_name}</td></tr>
			<tr><td style="padding:8px 0;color:#888;">Date</td><td style="color:#111;font-weight:500;">{appointment.appointment_date}</td></tr>
			<tr><td style="padding:8px 0;color:#888;">Time</td><td style="color:#111;font-weight:500;">{str(appointment.appointment_time)[:5]}</td></tr>
			<tr><td style="padding:8px 0;color:#888;">Reference</td><td style="color:#111;font-weight:500;">{appointment.name}</td></tr>
		</table>
		<p style="color:#999;font-size:0.8rem;margin:24px 0 0;">Please arrive 10 minutes before your appointment time.</p>
	</div>
	"""
	frappe.sendmail(recipients=[email], subject=subject, message=message, now=False)


# ---------------------------------------------------------------------------
# Practice info & availability (unchanged)
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_practice_info(practice_slug: str) -> dict:
	"""Return public practice info for the booking page."""
	return _get_practice_or_throw(practice_slug)


@frappe.whitelist(allow_guest=True)
def get_practice_practitioners(practice_slug: str) -> list:
	"""Return active doctors for a practice."""
	practice = _get_practice_or_throw(practice_slug)
	members = frappe.get_all(
		"Practice Member",
		filters={"practice": practice.name, "role": "Doctor"},
		pluck="practitioner",
		ignore_permissions=True,
	)
	practitioner_names = [m for m in members if m]
	if not practitioner_names:
		return []
	return frappe.get_all(
		"Healthcare Practitioner",
		filters={"name": ("in", practitioner_names), "status": "Active"},
		fields=["name", "practitioner_name", "department", "image"],
		ignore_permissions=True,
	)


@frappe.whitelist(allow_guest=True)
def get_availability(practice_slug: str, practitioner: str, date: str) -> list:
	"""Return available time slots for a practitioner on a given date."""
	practice = _get_practice_or_throw(practice_slug)

	is_member = frappe.db.exists(
		"Practice Member",
		{"practice": practice.name, "practitioner": practitioner, "role": "Doctor"},
	)
	if not is_member:
		frappe.throw(frappe._("Practitioner not found in this practice."), frappe.DoesNotExistError)

	# Guest users cannot see Patient Appointment records through the normal
	# permission query condition, so we must bypass permissions to get an
	# accurate view of booked slots. We only read appointment_time (no PII).
	booked_times = frappe.get_all(
		"Patient Appointment",
		filters={
			"practitioner": practitioner,
			"appointment_date": date,
			"status": ("not in", ["Cancelled"]),
		},
		pluck="appointment_time",
		ignore_permissions=True,
	)

	from datetime import datetime, timedelta

	# Normalise booked times to "HH:MM:SS" strings. Frappe returns
	# appointment_time as datetime.timedelta, whose str() drops the leading
	# zero on hours < 10 ("8:00:00" not "08:00:00"), so naive comparison
	# against slot strings like "08:00:00" never matches.
	def _fmt_time(t):
		if isinstance(t, timedelta):
			total = int(t.total_seconds())
			return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"
		return str(t)[:8]

	booked_set = {_fmt_time(t) for t in booked_times}

	available = []
	start = datetime.strptime("08:00:00", "%H:%M:%S")
	end = datetime.strptime("17:00:00", "%H:%M:%S")
	slot = start
	while slot < end:
		slot_str = slot.strftime("%H:%M:%S")
		if slot_str not in booked_set:
			available.append(slot_str)
		slot += timedelta(minutes=30)

	return available
