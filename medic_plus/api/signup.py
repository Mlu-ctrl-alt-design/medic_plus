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
		{"email": email, "status": ["in", ["Pending", "Approved"]]},
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
		{"email": email, "status": ["in", ["Pending", "Approved"]]},
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

	from medic_plus.api.onboarding import _notify_admins_of_new_request
	_notify_admins_of_new_request(doc)

	return {
		"status": "submitted",
		"request": doc.name,
		"message": _("Signup submitted. You'll receive login details once approved."),
	}
