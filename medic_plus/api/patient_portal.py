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
