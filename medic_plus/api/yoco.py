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

_YOCO_CHECKOUT_URL = "https://payments.yoco.com/api/checkouts"
#: Reject webhooks older than this (replay protection).
_WEBHOOK_MAX_AGE_SECONDS = 5 * 60


# ---------------------------------------------------------------------------
# Settings accessors
# ---------------------------------------------------------------------------

def _get_secret_key() -> str | None:
	try:
		return frappe.db.get_single_value("Medic Plus Settings", "yoco_secret_key")
	except Exception:
		return frappe.conf.get("yoco_secret_key")


def _get_webhook_secret() -> str | None:
	try:
		return frappe.db.get_single_value("Medic Plus Settings", "yoco_webhook_secret")
	except Exception:
		return frappe.conf.get("yoco_webhook_secret")


def _get_signup_fee_cents() -> int:
	try:
		value = frappe.db.get_single_value("Medic Plus Settings", "yoco_signup_fee_cents")
	except Exception:
		value = None
	return int(value) if value else 49900  # R499.00 default


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


def _handle_payment_succeeded(data: dict) -> None:
	request_name = (data.get("metadata") or {}).get("request_name")
	checkout_id = data.get("checkoutId") or data.get("id")

	# Prefer metadata.request_name; fall back to matching by checkout ID.
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

	frappe.db.set_value(
		"Practice Registration Request",
		target,
		{
			"payment_status": "Paid",
			"yoco_paid_at": frappe.utils.now(),
		},
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
