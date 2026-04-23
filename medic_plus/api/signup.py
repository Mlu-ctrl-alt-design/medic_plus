"""
Doctor self-signup with email OTP verification.

Two-step flow:

  1. request_signup_otp  — validate input, generate 6-digit email OTP,
                            cache hashed OTP + pending registration payload
                            keyed by email, send OTP by email.
  2. verify_signup_otp   — validate OTP, promote cached payload into a
                            Practice Registration Request (Pending), clear
                            cache entry, trigger admin notification.

State lives in Redis cache (not a DocType) because:
  - the payload is pre-user, pre-registration — nothing to link to yet
  - short-lived (10-min expiry) matches Redis TTL semantics
  - one-shot (OTP burns on verify), so no history retention needed

Rate limits mirror registration.py: 5 requests / hour / IP.
"""

import hashlib
import hmac
import random
import string

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from medic_plus.api.validators import (
	validate_hpcsa_number,
	validate_practice_number,
	validate_sa_mobile,
)

OTP_EXPIRY_MINUTES = 10
_CACHE_PREFIX = "medic_plus:signup_otp:"


def _cache_key(email: str) -> str:
	return _CACHE_PREFIX + hashlib.sha256(email.encode()).hexdigest()


def _generate_otp() -> str:
	return "".join(random.choices(string.digits, k=6))


def _hash_otp(otp: str) -> str:
	return hashlib.sha256(otp.encode()).hexdigest()


def _send_signup_otp_email(recipient: str, otp: str) -> None:
	frappe.sendmail(
		recipients=[recipient],
		subject=_("Verify your Medic Plus signup"),
		message=_(
			"Your verification code is: <strong>{0}</strong><br><br>"
			"This code expires in {1} minutes. Do not share it."
		).format(otp, OTP_EXPIRY_MINUTES),
	)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=3600)
def request_signup_otp(
	practice_name: str,
	full_name: str,
	email: str,
	mobile: str,
	hpcsa_number: str,
	practice_number: str,
	is_dispensing_doctor: bool = False,
) -> dict:
	"""Validate inputs, cache a pending signup payload, email a 6-digit OTP."""
	email = (email or "").strip().lower()
	practice_name = (practice_name or "").strip()
	full_name = (full_name or "").strip()

	if not email or "@" not in email:
		frappe.throw(_("A valid email is required."), frappe.ValidationError)
	if not full_name:
		frappe.throw(_("Full name is required."), frappe.ValidationError)
	if not practice_name:
		frappe.throw(_("Practice name is required."), frappe.ValidationError)

	mobile = validate_sa_mobile(mobile)
	hpcsa_number = validate_hpcsa_number(hpcsa_number)
	practice_number = validate_practice_number(practice_number)

	if frappe.db.exists("User", email):
		frappe.throw(_("An account with this email already exists."), frappe.ValidationError)

	duplicate = frappe.db.exists(
		"Practice Registration Request",
		{"email": email, "status": ["in", ["Pending", "Provisioned"]]},
	)
	if duplicate:
		frappe.throw(
			_("A registration request for {0} is already pending or approved.").format(email),
			frappe.ValidationError,
		)

	otp = _generate_otp()
	payload = {
		"otp_hash": _hash_otp(otp),
		"practice_name": practice_name,
		"full_name": full_name,
		"email": email,
		"mobile": mobile,
		"hpcsa_number": hpcsa_number,
		"practice_number": practice_number,
		"is_dispensing_doctor": frappe.utils.cint(is_dispensing_doctor),
	}
	frappe.cache().set_value(
		_cache_key(email),
		payload,
		expires_in_sec=OTP_EXPIRY_MINUTES * 60,
	)

	_send_signup_otp_email(email, otp)

	response: dict = {
		"status": "otp_sent",
		"message": _("We've sent a 6-digit code to {0}. It expires in {1} minutes.").format(
			email, OTP_EXPIRY_MINUTES
		),
		"expires_in_seconds": OTP_EXPIRY_MINUTES * 60,
	}
	if frappe.conf.get("developer_mode"):
		response["_dev_otp"] = otp
	return response


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=600)
def verify_signup_otp(email: str, otp: str) -> dict:
	"""Validate OTP; on success create Practice Registration Request (Pending)."""
	email = (email or "").strip().lower()
	otp = (otp or "").strip()

	if not email or not otp:
		frappe.throw(_("Email and code are required."), frappe.ValidationError)

	payload = frappe.cache().get_value(_cache_key(email))
	if not payload:
		frappe.throw(
			_("Your verification code has expired. Please restart signup."),
			frappe.ValidationError,
		)

	if not hmac.compare_digest(payload["otp_hash"], _hash_otp(otp)):
		frappe.throw(_("Incorrect verification code."), frappe.ValidationError)

	frappe.cache().delete_value(_cache_key(email))

	# Race-check: another request may have landed between request_signup_otp
	# and now. Re-validate uniqueness before insert.
	if frappe.db.exists("User", email):
		frappe.throw(_("An account with this email already exists."), frappe.ValidationError)
	if frappe.db.exists(
		"Practice Registration Request",
		{"email": email, "status": ["in", ["Pending", "Provisioned"]]},
	):
		frappe.throw(
			_("A registration request for {0} is already pending or approved.").format(email),
			frappe.ValidationError,
		)

	doc = frappe.get_doc({
		"doctype": "Practice Registration Request",
		"practice_name": payload["practice_name"],
		"full_name": payload["full_name"],
		"email": payload["email"],
		"mobile": payload["mobile"],
		"hpcsa_number": payload["hpcsa_number"],
		"practice_number": payload["practice_number"],
		"is_dispensing_doctor": payload["is_dispensing_doctor"],
		"status": "Pending",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	notify_admins_of_new_request(doc)

	return {
		"status": "submitted",
		"request": doc.name,
		"message": _("Signup submitted. You'll receive login details once approved."),
	}


def notify_admins_of_new_request(doc) -> None:
	"""Email Healthcare Administrators about a new registration request."""
	admin_users = frappe.get_all(
		"Has Role",
		filters={"role": "Healthcare Administrator", "parenttype": "User"},
		pluck="parent",
	)
	recipients = [u for u in admin_users if frappe.db.get_value("User", u, "enabled")]
	if not recipients:
		return

	frappe.sendmail(
		recipients=recipients,
		subject=f"[Medic Plus] New Registration: {doc.practice_name}",
		message=f"""
		<p>A new practice registration request has been submitted and is awaiting your review.</p>
		<table style="border-collapse:collapse;font-size:14px;">
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">Practice</td><td><strong>{doc.practice_name}</strong></td></tr>
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">Doctor</td><td>{doc.full_name}</td></tr>
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">Email</td><td>{doc.email}</td></tr>
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">HPCSA</td><td>{doc.hpcsa_number}</td></tr>
		  <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">Dispensing</td><td>{"Yes" if doc.is_dispensing_doctor else "No"}</td></tr>
		</table>
		<p style="margin-top:16px;">
		  <a href="/app/practice-registration-request/{doc.name}"
		     style="background:#2563eb;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none;">
		    Review Request
		  </a>
		</p>
		""",
		now=False,
	)


# ---------------------------------------------------------------------------
# Completion token — signed one-time URL issued after provisioning
# ---------------------------------------------------------------------------

COMPLETION_TOKEN_TTL_SECONDS = 12 * 3600
_COMPLETION_PREFIX = "medic_plus:signup_complete:"


def _completion_key(token: str) -> str:
	return _COMPLETION_PREFIX + hashlib.sha256(token.encode()).hexdigest()


def issue_completion_token(email: str, request_name: str) -> str:
	"""Generate a signed one-time URL token. Called post-provisioning.

	Returns the plaintext token. Only the SHA-256 hash is stored in Redis.
	"""
	token = frappe.generate_hash(length=48)
	frappe.cache().set_value(
		_completion_key(token),
		{
			"email": email,
			"request_name": request_name,
			"issued_at": frappe.utils.now(),
		},
		expires_in_sec=COMPLETION_TOKEN_TTL_SECONDS,
	)
	return token


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=30, seconds=600)
def verify_signup_completion_token(token: str) -> dict:
	"""Check whether a completion token is still valid and return the email."""
	token = (token or "").strip()
	if not token:
		frappe.throw(_("Completion token is required."), frappe.ValidationError)
	payload = frappe.cache().get_value(_completion_key(token))
	if not payload:
		frappe.throw(
			_("This completion link has expired or has already been used."),
			frappe.ValidationError,
		)
	return {
		"email": payload["email"],
		"request_name": payload["request_name"],
		"expires_in": COMPLETION_TOKEN_TTL_SECONDS,
	}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=600)
def set_password_and_login(token: str, password: str) -> dict:
	"""Consume the completion token, set the password, log the user in.

	One-shot: on success the Redis entry is deleted so re-use returns 'expired'.
	"""
	from frappe.utils.password import update_password

	token = (token or "").strip()
	password = (password or "").strip()
	if not token or not password:
		frappe.throw(_("Token and password are required."), frappe.ValidationError)
	if len(password) < 10:
		frappe.throw(_("Password must be at least 10 characters."), frappe.ValidationError)

	payload = frappe.cache().get_value(_completion_key(token))
	if not payload:
		frappe.throw(
			_("This completion link has expired or has already been used."),
			frappe.ValidationError,
		)

	email = payload["email"]
	if not frappe.db.exists("User", email):
		frappe.throw(_("Matching account was not found."), frappe.ValidationError)

	update_password(user=email, pwd=password)
	frappe.cache().delete_value(_completion_key(token))

	frappe.local.login_manager.login_as(email)
	return {"redirect": "/app/practice"}


# ---------------------------------------------------------------------------
# Dev-only: simulate a Yoco webhook success for UI tests
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def _test_mark_paid(request_name: str) -> dict:
	"""Simulate a Yoco payment.succeeded webhook. Gated on developer_mode.

	Returns 404-shaped response on production sites so the endpoint is
	effectively absent when not needed.
	"""
	if not frappe.conf.get("developer_mode"):
		frappe.local.response.http_status_code = 404
		return {"error": "not found"}

	from medic_plus.api.yoco import _handle_payment_succeeded
	_handle_payment_succeeded({"metadata": {"request_name": request_name}})
	return {"ok": True}


# ---------------------------------------------------------------------------
# Scheduler — retry stuck Paid-but-not-Provisioned PRRs
# ---------------------------------------------------------------------------

def retry_failed_provisioning() -> None:
	"""Find PRRs stuck after a webhook failure and retry provisioning.

	Targets rows where payment landed but provisioning never completed,
	older than 5 minutes (so we don't race an in-flight webhook).
	"""
	from datetime import timedelta
	from medic_plus.api.yoco import _handle_payment_succeeded

	cutoff = frappe.utils.now_datetime() - timedelta(minutes=5)
	stuck = frappe.get_all(
		"Practice Registration Request",
		filters={
			"payment_status": "Paid",
			"status": ["in", ["Pending", "Provisioning Failed"]],
			"provisioned_practice": ["is", "not set"],
			"modified": ["<", cutoff],
		},
		pluck="name",
	)
	for name in stuck:
		try:
			_handle_payment_succeeded({"metadata": {"request_name": name}})
		except Exception:
			frappe.log_error(
				title=f"retry_failed_provisioning failed for {name}",
				message=frappe.get_traceback(),
			)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=600)
def signup_status(request_name: str) -> dict:
	"""Poll endpoint for /signup/success page.

	Returns the PRR's current payment_status and status, plus a `ready` bool
	indicating whether the frontend should redirect to /signup/complete.
	The completion token itself is delivered via email (see
	issue_completion_token), not through this endpoint.
	"""
	request_name = (request_name or "").strip()
	# Guest-callable endpoint: do NOT distinguish unknown from known request
	# names — returning a generic empty shape prevents enumeration of the
	# predictable `PRR-.#####` namespace under rate limits.
	empty = {"payment_status": None, "status": None, "ready": False}
	if not request_name or not frappe.db.exists("Practice Registration Request", request_name):
		return empty

	row = frappe.db.get_value(
		"Practice Registration Request",
		request_name,
		["payment_status", "status", "provisioned_practice", "completion_email_sent_at"],
		as_dict=True,
	)
	ready = bool(
		row.status == "Provisioned"
		and row.provisioned_practice
		and row.completion_email_sent_at  # webhook emitted the email already
	)
	return {
		"payment_status": row.payment_status,
		"status": row.status,
		"ready": ready,
	}
