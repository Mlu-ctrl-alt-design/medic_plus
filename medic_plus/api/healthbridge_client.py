"""Healthbridge HTTP switch client.

Thin transport layer: constructs the claim payload, POSTs it to the configured
endpoint, and parses the response.  The caller (claims.py) owns retries and
state transitions.

The ``_post`` function is a module-level callable so tests can monkeypatch it
without needing ``requests-mock`` at import time:

    from medic_plus.api import healthbridge_client as hb
    hb._post = lambda url, **kw: MockResponse(200, {...})
"""

from __future__ import annotations

import json
import frappe
import requests

# Default endpoint — override per practice via Switch Configuration.endpoint_url
_DEFAULT_ENDPOINT = "https://api.healthbridge.co.za/switch/v1/claims"

# Timeout passed to every requests.post call (seconds)
_DEFAULT_TIMEOUT = 30


def _post(url: str, *, headers: dict, payload: dict, timeout: int) -> requests.Response:
	"""Thin wrapper around requests.post.  Replaced by tests to avoid live HTTP."""
	return requests.post(url, headers=headers, json=payload, timeout=timeout)


def submit_to_switch(claim_name: str) -> dict:
	"""POST the claim to Healthbridge and return the parsed response dict.

	Response dict shape:
	  {
	    "success": bool,
	    "switch_reference": str | None,
	    "response_code": str,
	    "response_message": str,
	    "line_statuses": [{"code": str, "status": str, "rejection_reason": str}],
	    "raw": str,
	  }

	Raises ``frappe.ValidationError`` for configuration errors (missing
	Switch Configuration, missing provider_code).  HTTP-level failures set
	``success=False`` and surface the message in ``response_message``.
	"""
	claim = frappe.get_doc("Insurance Claim", claim_name)
	switch_cfg = _get_switch_config(claim.practice)

	payload = _build_payload(claim, switch_cfg)
	endpoint = (switch_cfg.endpoint_url or "").strip() or _DEFAULT_ENDPOINT
	headers = _build_headers(switch_cfg)
	timeout = int(switch_cfg.timeout_seconds or _DEFAULT_TIMEOUT)

	try:
		resp = _post(endpoint, headers=headers, payload=payload, timeout=timeout)
	except requests.RequestException as exc:
		return {
			"success": False,
			"switch_reference": None,
			"response_code": "NETWORK_ERROR",
			"response_message": str(exc),
			"line_statuses": [],
			"raw": "",
		}

	return _parse_response(resp)


def _get_switch_config(practice: str):
	name = frappe.db.get_value("Switch Configuration", {"practice": practice}, "name")
	if not name:
		frappe.throw(
			f"No Switch Configuration found for practice {practice}. "
			"Please configure Healthbridge credentials before submitting claims.",
			frappe.ValidationError,
		)
	return frappe.get_doc("Switch Configuration", name)


def _build_headers(cfg) -> dict:
	import base64
	creds = base64.b64encode(
		f"{cfg.username or ''}:{cfg.get_password('password') or ''}".encode()
	).decode()
	return {
		"Authorization": f"Basic {creds}",
		"Content-Type": "application/json",
		"X-Sender-PR": cfg.sender_id or "",
		"X-Provider-Code": cfg.provider_code or "",
	}


def _build_payload(claim, cfg) -> dict:
	return {
		"provider_code": cfg.provider_code or "",
		"claim_reference": claim.name,
		"patient": {
			"member_id": claim.member_id or "",
			"dependent_code": claim.dependent_code or "",
			"authorisation_reference": claim.authorisation_reference or "",
			"scheme": claim.scheme_name or "",
		},
		"lines": [
			{
				"line_type": ln.line_type,
				"code": ln.code,
				"description": ln.description or "",
				"quantity": ln.quantity or 1,
				"unit_fee": float(ln.unit_fee or 0),
			}
			for ln in (claim.claim_lines or [])
		],
	}


def _parse_response(resp: requests.Response) -> dict:
	raw = resp.text
	try:
		body = resp.json()
	except ValueError:
		body = {}

	if resp.status_code == 200:
		line_statuses = [
			{
				"code": ls.get("code", ""),
				"status": ls.get("status", "Accepted"),
				"rejection_reason": ls.get("rejection_reason", ""),
			}
			for ls in body.get("line_statuses", [])
		]
		all_accepted = all(ls["status"] == "Accepted" for ls in line_statuses) if line_statuses else True
		any_rejected = any(ls["status"] == "Rejected" for ls in line_statuses)
		if all_accepted:
			overall = "Accepted"
		elif any_rejected and not all_accepted:
			overall = "Partial"
		else:
			overall = "Accepted"

		return {
			"success": True,
			"switch_reference": body.get("switch_reference") or body.get("reference"),
			"response_code": str(resp.status_code),
			"response_message": body.get("message", "OK"),
			"line_statuses": line_statuses,
			"overall_status": overall,
			"raw": raw,
		}

	return {
		"success": False,
		"switch_reference": None,
		"response_code": str(resp.status_code),
		"response_message": body.get("message") or resp.reason or f"HTTP {resp.status_code}",
		"line_statuses": [],
		"overall_status": "Error",
		"raw": raw,
	}
