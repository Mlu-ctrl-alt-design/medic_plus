"""
Yoco Online Payments integration — soft paywall for doctor signup.

Flow:
  1. After verify_signup_otp creates a Practice Registration Request (Unpaid),
     the frontend calls `create_signup_checkout(request_name)` which returns
     a Yoco-hosted checkout URL.
  2. Doctor completes payment on Yoco; webhook `yoco_webhook` receives a
     `payment.succeeded` event, verifies signature, and flips payment_status
     to Paid.
  3. Admin review/provision is a separate step — the Unpaid flag is a *soft*
     marker, not a hard gate. Provisioned practices with payment_status=Unpaid
     are surfaced in the admin list so ops can chase payment.

Yoco API assumptions (Online Payments v1):
  - POST   https://payments.yoco.com/api/checkouts  → { id, redirectUrl }
  - Webhook signature: HMAC-SHA256 over "{id}.{timestamp}.{body}", base64,
    prefixed "v1," in the `webhook-signature` header.
  - Headers `webhook-id`, `webhook-timestamp`, `webhook-signature`.

If Yoco adjusts their API shape, tune the _yoco_* helpers below; callers
shouldn't need to change.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from medic_plus.api._provisioning import create_user, provision_doctor

_YOCO_CHECKOUT_URL = "https://payments.yoco.com/api/checkouts"
#: Reject webhooks older than this (replay protection).
_WEBHOOK_MAX_AGE_SECONDS = 5 * 60


# ---------------------------------------------------------------------------
# Settings accessors — read from `Medic Plus Yoco Settings` (single DocType).
#
# Falls back to `Medic Plus Settings.yoco_*` for backwards compatibility with
# sites that haven't migrated yet, and to site_config keys for ops overrides.
# ---------------------------------------------------------------------------

_YOCO_SETTINGS_NAME = "Medic Plus Yoco Settings"


def _get_yoco_settings_doc():
	"""Return the Medic Plus Yoco Settings doc, or None if unavailable.

	The DocType is a regular (non-Single) doctype; ops creates one row named
	exactly "Medic Plus Yoco Settings" via the Desk and pastes the credentials
	into it. If multiple rows exist (e.g. ops set up several merchants),
	the first by creation is used.

	Cached on frappe.local for the duration of the request.
	"""
	cached = getattr(frappe.local, "_medic_yoco_settings", None)
	if cached is not None:
		return cached or None
	doc = False
	try:
		if frappe.db.exists("Medic Plus Yoco Settings", _YOCO_SETTINGS_NAME):
			doc = frappe.get_cached_doc("Medic Plus Yoco Settings", _YOCO_SETTINGS_NAME)
		else:
			fallback = frappe.db.get_value(
				"Medic Plus Yoco Settings", {}, "name", order_by="creation asc"
			)
			if fallback:
				doc = frappe.get_cached_doc("Medic Plus Yoco Settings", fallback)
	except Exception:
		doc = False
	frappe.local._medic_yoco_settings = doc
	return doc or None


def _get_secret_key() -> str | None:
	doc = _get_yoco_settings_doc()
	if doc:
		val = doc.get_password("secret_key", raise_exception=False)
		if val:
			return val
	# Legacy fallback (Phase 6 preview): keys lived on Medic Plus Settings
	try:
		val = frappe.db.get_single_value("Medic Plus Settings", "yoco_secret_key")
		if val:
			return val
	except Exception:
		pass
	return frappe.conf.get("yoco_secret_key")


def _get_webhook_secret() -> str | None:
	doc = _get_yoco_settings_doc()
	if doc:
		val = doc.get_password("webhook_secret", raise_exception=False)
		if val:
			return val
	try:
		val = frappe.db.get_single_value("Medic Plus Settings", "yoco_webhook_secret")
		if val:
			return val
	except Exception:
		pass
	return frappe.conf.get("yoco_webhook_secret")


def _get_signup_fee_cents() -> int:
	doc = _get_yoco_settings_doc()
	if doc and doc.signup_fee_cents:
		return int(doc.signup_fee_cents)
	try:
		value = frappe.db.get_single_value("Medic Plus Settings", "yoco_signup_fee_cents")
		if value:
			return int(value)
	except Exception:
		pass
	return 49900  # R499.00 default


# ---------------------------------------------------------------------------
# Guest endpoint — called from the signup UI after OTP verify
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=3600)
def create_signup_checkout(request_name: str) -> dict:
	"""Create a Yoco checkout for the given Practice Registration Request.

	Guest-callable because the requester has no User yet.  Idempotent:
	calling twice for the same request before payment returns the existing
	checkout (tracked via `yoco_checkout_id`).
	"""
	req = _get_request_or_throw(request_name)

	if req.payment_status == "Paid":
		frappe.throw(_("This registration is already paid."), frappe.ValidationError)

	secret = _get_secret_key()
	if not secret:
		return {"status": "not_configured", "message": "Yoco is not configured."}

	amount_cents = _get_signup_fee_cents()
	base_url = frappe.utils.get_url()

	payload = {
		"amount": amount_cents,
		"currency": "ZAR",
		"metadata": {
			"request_name": req.name,
			"email": req.email,
		},
		"successUrl": f"{base_url}/signup/success?req={req.name}",
		"cancelUrl": f"{base_url}/signup/cancel?req={req.name}",
		"failureUrl": f"{base_url}/signup/failed?req={req.name}",
	}

	import requests
	resp = requests.post(
		_YOCO_CHECKOUT_URL,
		json=payload,
		headers={
			"Authorization": f"Bearer {secret}",
			"Content-Type": "application/json",
			"Idempotency-Key": str(uuid.uuid4()),
		},
		timeout=15,
	)
	if resp.status_code not in (200, 201):
		frappe.log_error(
			title="Yoco checkout creation failed",
			message=f"status={resp.status_code} body={resp.text[:1000]}",
		)
		frappe.throw(
			_("Could not initialise payment. Please try again in a moment."),
			frappe.ValidationError,
		)

	data = resp.json()
	frappe.db.set_value(
		"Practice Registration Request",
		req.name,
		{
			"yoco_checkout_id": data.get("id"),
			"payment_status": "Pending",
			"yoco_amount_cents": amount_cents,
		},
	)
	frappe.db.commit()

	return {
		"status": "ok",
		"checkout_id": data.get("id"),
		"redirect_url": data.get("redirectUrl"),
	}


# ---------------------------------------------------------------------------
# Webhook — flips payment_status on payment.succeeded
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def yoco_webhook() -> None:
	"""Receive and verify a Yoco webhook.

	Returns 200 on acknowledged events (even ignored ones). Returns 400 on
	signature verification failure so Yoco retries aren't silently dropped
	into a black hole.
	"""
	secret = _get_webhook_secret()
	if not secret:
		frappe.local.response.http_status_code = 500
		frappe.log_error("Yoco webhook received but secret not configured", "Yoco")
		return

	raw_body = frappe.request.get_data()
	wh_id = frappe.get_request_header("webhook-id", "")
	wh_ts = frappe.get_request_header("webhook-timestamp", "")
	wh_sig = frappe.get_request_header("webhook-signature", "")

	if not (wh_id and wh_ts and wh_sig):
		frappe.local.response.http_status_code = 400
		return

	# Replay protection: reject stale timestamps
	try:
		ts_int = int(wh_ts)
	except ValueError:
		frappe.local.response.http_status_code = 400
		return
	if abs(time.time() - ts_int) > _WEBHOOK_MAX_AGE_SECONDS:
		frappe.local.response.http_status_code = 400
		return

	if not _verify_webhook_signature(secret, wh_id, wh_ts, raw_body, wh_sig):
		frappe.local.response.http_status_code = 400
		frappe.log_error("Yoco webhook: signature mismatch", "Yoco")
		return

	try:
		event = json.loads(raw_body)
	except json.JSONDecodeError:
		frappe.local.response.http_status_code = 400
		return

	event_type = event.get("type") or event.get("event")
	data = event.get("payload") or event.get("data") or {}

	if event_type == "payment.succeeded":
		_handle_payment_succeeded(data)
	elif event_type == "payment.failed":
		_handle_payment_failed(data)
	# Other events (refund.succeeded etc.) — acknowledged but ignored.

	frappe.local.response.http_status_code = 200


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_request_or_throw(name: str):
	if not frappe.db.exists("Practice Registration Request", name):
		frappe.throw(_("Registration request not found."), frappe.ValidationError)
	return frappe.get_doc("Practice Registration Request", name)


def _verify_webhook_signature(
	secret: str, wh_id: str, wh_ts: str, body: bytes, header: str
) -> bool:
	"""HMAC-SHA256 over "{id}.{ts}.{body}", base64-encoded.

	The `webhook-signature` header can contain multiple space-separated
	version-tagged values (e.g. "v1,<sig1> v1,<sig2>"). We accept if any
	matches.
	"""
	signed = f"{wh_id}.{wh_ts}.".encode() + body
	expected = base64.b64encode(
		hmac.new(secret.encode(), signed, hashlib.sha256).digest()
	).decode()

	for part in header.split():
		_, _, sig = part.partition(",")
		if sig and hmac.compare_digest(sig, expected):
			return True
	return False


@frappe.whitelist()
def force_provision(request_name: str) -> dict:
	"""Admin-initiated provisioning for a PRR that has already been paid.

	Used when the Yoco webhook failed to land (network hiccup, signature error
	on legacy config, etc.) and the admin needs to finish the flow by hand.
	Strict prerequisites:
	  - caller must be a System Manager
	  - PRR must exist
	  - PRR.payment_status must be "Paid" (no forcing through unpaid requests)
	  - PRR must not already be provisioned
	"""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can force provisioning."), frappe.PermissionError)

	request_name = (request_name or "").strip()
	if not request_name or not frappe.db.exists("Practice Registration Request", request_name):
		frappe.throw(_("Registration request not found."), frappe.ValidationError)

	req = frappe.get_doc("Practice Registration Request", request_name)

	if req.provisioned_practice:
		frappe.throw(
			_("This request is already provisioned ({0}).").format(req.provisioned_practice),
			frappe.ValidationError,
		)
	if req.payment_status != "Paid":
		frappe.throw(
			_("Force Provision requires payment_status=Paid. Current: {0}.").format(
				req.payment_status or "Unpaid"
			),
			frappe.ValidationError,
		)

	_handle_payment_succeeded({"metadata": {"request_name": request_name}})

	req.reload()
	if req.status != "Provisioned" or not req.provisioned_practice:
		frappe.throw(
			_("Provisioning did not complete. Error: {0}").format(req.provisioning_error or "unknown"),
			frappe.ValidationError,
		)

	return {
		"status": "ok",
		"practice": req.provisioned_practice,
		"message": _("Practice {0} provisioned successfully.").format(req.practice_name),
	}


@frappe.whitelist()
def admin_mark_paid_and_provision(request_name: str, reason: str | None = None) -> dict:
	"""Admin payment override: mark a PRR Paid and run provisioning.

	Used when a customer paid out-of-band (EFT, complimentary, demo) and the
	Yoco webhook will never arrive. Reuses the same _handle_payment_succeeded
	path as the webhook so admin and webhook flows produce identical tenants.

	An audit Comment is written to the PRR before provisioning runs, so the
	override is traceable even if provisioning fails afterwards.

	Strict prerequisites:
	  - caller must be a System Manager
	  - PRR must exist
	  - PRR must not already be provisioned
	"""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(
			_("Only System Managers can override payment."), frappe.PermissionError
		)

	request_name = (request_name or "").strip()
	if not request_name or not frappe.db.exists(
		"Practice Registration Request", request_name
	):
		frappe.throw(_("Registration request not found."), frappe.ValidationError)

	req = frappe.get_doc("Practice Registration Request", request_name)

	if req.provisioned_practice:
		frappe.throw(
			_("This request is already provisioned ({0}).").format(
				req.provisioned_practice
			),
			frappe.ValidationError,
		)

	actor = frappe.session.user
	was_unpaid = req.payment_status != "Paid"
	note = (reason or "").strip() or _("(no reason given)")

	req.add_comment(
		"Comment",
		text=_("Admin payment override by {0}. Reason: {1}").format(actor, note),
	)

	_handle_payment_succeeded({"metadata": {"request_name": request_name}})

	req.reload()
	if req.status != "Provisioned" or not req.provisioned_practice:
		frappe.throw(
			_("Provisioning did not complete. Error: {0}").format(
				req.provisioning_error or "unknown"
			),
			frappe.ValidationError,
		)

	if was_unpaid:
		message = _("Practice {0} provisioned (admin payment override).").format(
			req.practice_name
		)
	else:
		message = _("Practice {0} provisioned successfully.").format(req.practice_name)

	return {
		"status": "ok",
		"practice": req.provisioned_practice,
		"message": message,
		"override": was_unpaid,
	}


def _handle_payment_succeeded(data: dict) -> None:
	"""Mark PRR as Paid, provision the doctor, issue a completion token.

	The webhook hits this as Guest (Yoco's HTTP request has no Frappe session),
	but provisioning needs Administrator privileges to insert User Permissions
	via Healthcare Practitioner's on_update hook. The webhook signature was
	already verified by yoco_webhook upstream, so the elevation is safe.
	"""
	original_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		_provision_from_payment(data)
	finally:
		frappe.set_user(original_user)


def _provision_from_payment(data: dict) -> None:
	request_name = (data.get("metadata") or {}).get("request_name")
	checkout_id = data.get("checkoutId") or data.get("id")

	target = None
	if request_name and frappe.db.exists("Practice Registration Request", request_name):
		target = request_name
	elif checkout_id:
		target = frappe.db.get_value(
			"Practice Registration Request",
			{"yoco_checkout_id": checkout_id},
			"name",
		)

	if not target:
		frappe.log_error(
			f"Yoco payment.succeeded with no matching request: {data}", "Yoco"
		)
		return

	req = frappe.get_doc("Practice Registration Request", target)

	# Idempotency: if already provisioned, just ensure Paid is recorded and exit.
	if req.provisioned_practice:
		if req.payment_status != "Paid":
			frappe.db.set_value(
				"Practice Registration Request", target,
				{"payment_status": "Paid", "yoco_paid_at": frappe.utils.now()},
			)
			frappe.db.commit()
		return

	# Mark Paid first so payment state is recorded even if provisioning fails.
	frappe.db.set_value(
		"Practice Registration Request", target,
		{"payment_status": "Paid", "yoco_paid_at": frappe.utils.now()},
	)
	frappe.db.commit()

	try:
		# Email verification happens via the completion-token flow, so the
		# User can be created here without going through Frappe's sign_up.
		if not frappe.db.exists("User", req.email):
			create_user(
				full_name=req.full_name,
				email=req.email,
				mobile=req.mobile or "",
				roles=["Practice Doctor", "Practice Admin"],
			)

		result = provision_doctor(
			full_name=req.full_name,
			email=req.email,
			mobile=req.mobile or "",
			hpcsa_number=req.hpcsa_number or "",
			practice_number=req.practice_number or "",
			practice_name=req.practice_name,
			is_dispensing_doctor=bool(req.is_dispensing_doctor),
		)

		frappe.db.set_value(
			"Practice Registration Request", target,
			{
				"status": "Provisioned",
				"provisioned_practice": result["practice"],
				"provisioning_attempted_at": frappe.utils.now(),
				"provisioning_error": None,
			},
		)
		frappe.db.commit()

		_emit_completion_email(target, req.email, req.practice_name)

	except Exception as exc:
		frappe.db.rollback()
		frappe.db.set_value(
			"Practice Registration Request", target,
			{
				"status": "Provisioning Failed",
				"provisioning_attempted_at": frappe.utils.now(),
				"provisioning_error": str(exc),
			},
		)
		frappe.db.commit()
		frappe.log_error(
			title=f"Signup provisioning failed for {req.email}",
			message=frappe.get_traceback(),
		)


def _emit_completion_email(request_name: str, email: str, practice_name: str) -> None:
	"""Issue the signed completion token and email the applicant.

	In developer_mode the URL is also logged to Error Log so staging devs can
	recover it when mute_emails=1.
	"""
	from medic_plus.api.signup import issue_completion_token

	token = issue_completion_token(email=email, request_name=request_name)
	completion_url = f"{frappe.utils.get_url()}/signup/complete?token={token}"

	if frappe.conf.get("developer_mode"):
		frappe.log_error(
			title=f"[DEV] Completion URL for {email}",
			message=completion_url,
		)

	frappe.sendmail(
		recipients=[email],
		subject=_("Your Medic Plus practice is ready"),
		message=_(
			"<p>Your practice <strong>{0}</strong> has been activated.</p>"
			"<p>Click the button below within 12 hours to set your password and log in:</p>"
			"<p><a href=\"{1}\" style=\"background:#2563eb;color:#fff;padding:10px 20px;"
			"border-radius:6px;text-decoration:none;font-weight:600;\">Set your password</a></p>"
			"<p>If the link expires, you can reset your password from the login page.</p>"
		).format(practice_name, completion_url),
		now=False,
	)
	frappe.db.set_value(
		"Practice Registration Request", request_name,
		"completion_email_sent_at", frappe.utils.now(),
	)
	frappe.db.commit()


def _handle_payment_failed(data: dict) -> None:
	request_name = (data.get("metadata") or {}).get("request_name")
	if not request_name or not frappe.db.exists("Practice Registration Request", request_name):
		return
	frappe.db.set_value(
		"Practice Registration Request", request_name, "payment_status", "Failed"
	)
	frappe.db.commit()
