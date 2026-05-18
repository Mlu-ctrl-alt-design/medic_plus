"""Patient Portal API — practice-scoped, OTP-authenticated patient-facing endpoints.

See docs/superpowers/specs/2026-05-18-patient-portal-design.md
"""
import random
import frappe
from frappe.utils import getdate, get_datetime, now_datetime
from datetime import timedelta


# ---------------------------------------------------------------------------
# OTP infrastructure (parallel to medic_plus.api.booking; intentional duplicate
# to keep portal and guest booking flows fully independent)
# ---------------------------------------------------------------------------

OTP_TTL_SECONDS = 600  # 10 minutes
OTP_MAX_SEND_PER_WINDOW = 5
OTP_SEND_WINDOW_SECONDS = 600  # 10 minutes
OTP_MAX_VERIFY_ATTEMPTS = 5


def _otp_cache_key(slug: str, email: str) -> str:
	return f"portal_otp|{slug}|{email.lower().strip()}"


def _otp_attempt_key(slug: str, email: str) -> str:
	return f"portal_otp_attempt|{slug}|{email.lower().strip()}"


def _otp_verify_attempt_key(slug: str, email: str) -> str:
	return f"portal_otp_verify_attempt|{slug}|{email.lower().strip()}"


def _resolve_practice(slug: str) -> dict | None:
	return frappe.db.get_value(
		"Practice",
		{"slug": slug, "is_active": 1},
		["name", "practice_name", "logo", "color", "email", "slug"],
		as_dict=True,
	)


def _send_portal_otp_email(email: str, otp: str, practice: dict):
	subject = frappe._("Your sign-in code — {0}").format(practice["practice_name"])
	logo_tag = (
		f"<img src='{practice['logo']}' style='height:48px;margin-bottom:24px;display:block;' alt='{practice['practice_name']}'>"
		if practice.get("logo") else ""
	)
	message = f"""
	<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;border:1px solid #e5e7eb;border-radius:8px;">
		{logo_tag}
		<h2 style="margin:0 0 8px;font-size:1.2rem;color:#111;">{practice['practice_name']} — Patient Portal</h2>
		<p style="color:#555;margin:0 0 24px;">Use the code below to sign in. It expires in <strong>10 minutes</strong>.</p>
		<div style="background:#f3f4f6;border-radius:8px;padding:20px;text-align:center;letter-spacing:0.3em;font-size:2rem;font-weight:700;color:#111;">{otp}</div>
		<p style="color:#999;font-size:0.8rem;margin:24px 0 0;">If you did not request this code, you can safely ignore this email.</p>
	</div>
	"""
	frappe.sendmail(recipients=[email], subject=subject, message=message, now=True)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def request_portal_otp(slug: str, email: str) -> dict:
	"""Send a 6-digit OTP to `email` if a Patient record exists at `slug`.

	Always returns {ok: true} regardless of match — prevents email enumeration.
	Rate-limited to 5 sends per email/slug per 10 minutes.
	"""
	email = (email or "").lower().strip()
	if not email or "@" not in email:
		frappe.throw(frappe._("Please enter a valid email address."))

	practice = _resolve_practice(slug)
	if not practice:
		# Don't reveal whether a slug is valid; respond with the same shape.
		return {"ok": True}

	attempt_key = _otp_attempt_key(slug, email)
	attempts = frappe.cache.get_value(attempt_key) or 0
	if attempts >= OTP_MAX_SEND_PER_WINDOW:
		frappe.throw(
			frappe._("Too many sign-in attempts. Please wait 10 minutes and try again."),
			title=frappe._("Rate Limited"),
		)

	# Check if Patient exists at this practice with this email. If not, no-op
	# but still increment rate-limit + return success (anti-enumeration).
	patient_exists = frappe.db.exists("Patient", {"email": email, "custom_practice": practice["name"]})

	frappe.cache.set_value(attempt_key, attempts + 1, expires_in_sec=OTP_SEND_WINDOW_SECONDS)

	if patient_exists:
		otp = str(random.randint(100000, 999999))
		frappe.cache.set_value(_otp_cache_key(slug, email), otp, expires_in_sec=OTP_TTL_SECONDS)
		frappe.cache.delete_value(_otp_verify_attempt_key(slug, email))  # reset verify attempts on each send
		_send_portal_otp_email(email, otp, practice)

	return {"ok": True}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_portal_otp(slug: str, email: str, code: str) -> dict:
	"""Verify OTP, auto-provision a Frappe User if needed, log in."""
	email = (email or "").lower().strip()
	code = (code or "").strip()

	practice = _resolve_practice(slug)
	if not practice:
		frappe.throw(frappe._("Invalid sign-in link."), frappe.DoesNotExistError)

	verify_key = _otp_verify_attempt_key(slug, email)
	verify_attempts = frappe.cache.get_value(verify_key) or 0
	if verify_attempts >= OTP_MAX_VERIFY_ATTEMPTS:
		frappe.throw(
			frappe._("Too many incorrect attempts. Request a new code."),
			title=frappe._("Locked"),
		)

	otp_key = _otp_cache_key(slug, email)
	stored = frappe.cache.get_value(otp_key)
	if not stored:
		frappe.throw(frappe._("Code expired. Request a new one."), title=frappe._("Expired"))

	if code != stored:
		frappe.cache.set_value(verify_key, verify_attempts + 1, expires_in_sec=OTP_TTL_SECONDS)
		frappe.throw(frappe._("Incorrect code. Please try again."), title=frappe._("Invalid Code"))

	# Success — consume OTP and counters
	frappe.cache.delete_value(otp_key)
	frappe.cache.delete_value(verify_key)
	frappe.cache.delete_value(_otp_attempt_key(slug, email))

	# Ensure Patient still exists at this practice (defense vs. mid-flight revocation)
	if not frappe.db.exists("Patient", {"email": email, "custom_practice": practice["name"]}):
		frappe.throw(frappe._("No patient record found."), frappe.DoesNotExistError)

	# Auto-provision User if missing
	user = frappe.db.get_value("User", {"email": email}, "name")
	if not user:
		user_doc = frappe.get_doc({
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"enabled": 1,
			"user_type": "Website User",
			"send_welcome_email": 0,
		})
		user_doc.flags.ignore_permissions = True
		user_doc.insert(ignore_permissions=True)
		user = user_doc.name

	# Ensure `Patient` role
	user_doc = frappe.get_doc("User", user)
	if not any(r.role == "Patient" for r in user_doc.roles):
		user_doc.append("roles", {"role": "Patient"})
		user_doc.save(ignore_permissions=True)

	# Log in (login_manager only exists in HTTP request context; fall back for tests)
	try:
		frappe.local.login_manager.login_as(user)
	except AttributeError:
		frappe.set_user(user)
	frappe.db.commit()

	csrf_token = None
	session = getattr(frappe.local, "session", None)
	if session and getattr(session, "data", None):
		csrf_token = session.data.get("csrf_token")
	return {
		"ok": True,
		"slug": slug,
		"csrf_token": csrf_token,
	}


# ---------------------------------------------------------------------------
# Ownership + allowlist helpers
# ---------------------------------------------------------------------------

PATIENT_EDITABLE_FIELDS = {
	"first_name", "middle_name", "last_name", "dob", "sex",
	"mobile", "phone", "email", "blood_group",
	"marital_status", "occupation",
	"address_line1", "address_line2", "city", "state", "zip_code", "country",
	"allergies", "medication",
	"custom_preferred_language", "custom_ai_consent",
}


def _require_authed():
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("Please sign in."), frappe.PermissionError)


def _resolve_my_patient(slug: str) -> dict:
	"""Resolve the session user's Patient record at the given practice.

	Throws PermissionError if no match — never reveals practice/patient existence.
	"""
	_require_authed()
	practice = _resolve_practice(slug)
	if not practice:
		frappe.throw(frappe._("No patient record."), frappe.PermissionError)
	patient = frappe.db.get_value(
		"Patient",
		{"email": frappe.session.user, "custom_practice": practice["name"]},
		["name", "first_name", "middle_name", "last_name", "dob", "sex",
		 "mobile", "phone", "email", "blood_group", "marital_status", "occupation",
		 "address_line1", "address_line2", "city", "state", "zip_code", "country",
		 "allergies", "medication", "custom_preferred_language", "custom_ai_consent",
		 "custom_practice", "customer", "custom_nhid"],
		as_dict=True,
	)
	if not patient:
		frappe.throw(frappe._("No patient record."), frappe.PermissionError)
	return patient


@frappe.whitelist(methods=["GET", "POST"])
def get_me(slug: str) -> dict:
	"""Return the session user's Patient record (editable fields + masked NHID)."""
	patient = _resolve_my_patient(slug)
	# Mask NHID (SA national health ID equivalent) — only last 4 visible
	nhid = patient.get("custom_nhid")
	if nhid:
		patient["custom_nhid_masked"] = "•" * max(len(nhid) - 4, 0) + nhid[-4:]
	patient.pop("custom_nhid", None)
	return patient


@frappe.whitelist(methods=["POST"])
def update_me(slug: str, payload: dict) -> dict:
	"""PATCH the session user's Patient record using only fields on the allowlist."""
	patient = _resolve_my_patient(slug)

	if not isinstance(payload, dict):
		try:
			payload = frappe.parse_json(payload)
		except Exception:
			frappe.throw(frappe._("Invalid payload."))

	rejected = [k for k in payload.keys() if k not in PATIENT_EDITABLE_FIELDS]
	if rejected:
		frappe.throw(
			frappe._("Cannot edit fields: {0}").format(", ".join(rejected)),
			title=frappe._("Forbidden Fields"),
		)

	pdoc = frappe.get_doc("Patient", patient["name"])
	for k, v in payload.items():
		setattr(pdoc, k, v)
	# Ownership already validated above; the Patient role intentionally does not
	# have write perms on Patient (would expose cross-tenant editing via Desk).
	pdoc.save(ignore_permissions=True)
	frappe.db.commit()

	return get_me(slug)


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["GET", "POST"])
def list_my_appointments(slug: str) -> dict:
	patient = _resolve_my_patient(slug)
	upcoming = frappe.get_all(
		"Patient Appointment",
		filters={"patient": patient["name"], "appointment_date": [">=", frappe.utils.today()],
				 "status": ["not in", ["Cancelled"]]},
		fields=["name", "practitioner", "practitioner_name", "appointment_date",
				"appointment_time", "duration", "status", "notes"],
		order_by="appointment_date asc, appointment_time asc",
		limit=50,
	)
	past = frappe.get_all(
		"Patient Appointment",
		filters={"patient": patient["name"], "appointment_date": ["<", frappe.utils.today()]},
		fields=["name", "practitioner", "practitioner_name", "appointment_date",
				"appointment_time", "duration", "status"],
		order_by="appointment_date desc, appointment_time desc",
		limit=20,
	)
	return {"upcoming": upcoming, "past": past}


@frappe.whitelist(methods=["POST"])
def cancel_my_appointment(slug: str, name: str) -> dict:
	patient = _resolve_my_patient(slug)
	appt = frappe.db.get_value(
		"Patient Appointment",
		{"name": name, "patient": patient["name"]},
		["appointment_date", "appointment_time", "status"],
		as_dict=True,
	)
	if not appt:
		frappe.throw(frappe._("Appointment not found."), frappe.DoesNotExistError)
	if appt["status"] == "Cancelled":
		frappe.throw(frappe._("Already cancelled."))

	# Combine date + time into datetime; status is 24h before that.
	appt_dt = get_datetime(f"{appt['appointment_date']} {appt['appointment_time']}")
	if appt_dt - now_datetime() < timedelta(hours=24):
		frappe.throw(
			frappe._("Cancellations must be at least 24 hours before the appointment. Please call the practice."),
			title=frappe._("Too Late to Cancel"),
		)

	frappe.db.set_value("Patient Appointment", name, "status", "Cancelled")
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def book_for_authed_patient(slug: str, practitioner: str, appointment_date: str,
							  appointment_time: str, reason: str = "") -> dict:
	"""Authed booking — calls shared _book_slot helper from medic_plus.api.booking."""
	from medic_plus.api import booking as booking_mod

	patient = _resolve_my_patient(slug)
	practice = _resolve_practice(slug)

	# Validate practitioner is a member of the practice
	if not frappe.db.exists(
		"Practice Member",
		{"practice": practice["name"], "practitioner": practitioner, "role": "Doctor"},
	):
		frappe.throw(frappe._("Practitioner not found at this practice."), frappe.DoesNotExistError)

	appointment = booking_mod._book_slot(
		patient_name=patient["name"],
		practice=practice,
		practitioner=practitioner,
		appointment_date=appointment_date,
		appointment_time=appointment_time,
		reason=reason,
	)
	frappe.db.commit()
	return {"ok": True, "appointment_name": appointment.name}


@frappe.whitelist(methods=["GET", "POST"])
def resolve_my_practices() -> list:
	"""Return practices where session user has a Patient record. For /portal resolver."""
	_require_authed()
	rows = frappe.db.sql("""
		SELECT pr.slug, pr.practice_name, pr.logo, pr.color
		FROM `tabPatient` p
		JOIN `tabPractice` pr ON pr.name = p.custom_practice
		WHERE p.email = %(email)s AND pr.is_active = 1
		ORDER BY pr.practice_name ASC
	""", {"email": frappe.session.user}, as_dict=True)
	return rows or []


@frappe.whitelist(methods=["GET", "POST"])
def get_boot(slug: str) -> dict:
	"""Boot context for the SPA: practice info + auth state."""
	practice = _resolve_practice(slug)
	if not practice:
		frappe.throw(frappe._("Practice not found."), frappe.DoesNotExistError)
	is_authed = frappe.session.user != "Guest"
	has_patient = False
	patient_name = None
	if is_authed:
		patient_name = frappe.db.get_value(
			"Patient", {"email": frappe.session.user, "custom_practice": practice["name"]}, "name"
		)
		has_patient = bool(patient_name)
	return {
		"practice": practice,
		"is_authed": is_authed,
		"has_patient": has_patient,
		"patient_name": patient_name,
		"session_user": frappe.session.user if is_authed else None,
	}
