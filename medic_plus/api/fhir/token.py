"""FHIR / SMART-on-FHIR OAuth2 token issuance and validation.

Implements a minimal SMART v2 bearer-token model:
  - Tokens are 256-bit random secrets stored only as SHA-256 hashes.
  - Scope is a space-delimited list of SMART v2 resource scopes.
  - Practice context is baked into the token; cross-tenant calls are denied.
  - Token TTL defaults to 1 hour.

Usage (from a whitelisted endpoint or test):
  raw_token, token_doc_name = issue_token(user, practice, scope)
  resolve_token(raw_token) → {user, practice, scope, token_name}
"""

from __future__ import annotations

import hashlib
import secrets
import datetime

import frappe

TOKEN_TTL_SECONDS = 3600


def issue_token(user: str, practice: str, scope: str = "patient/*.read") -> tuple[str, str]:
	"""Create a FHIR Access Token and return (raw_token, doc_name).

	The raw_token must be returned to the caller once and never stored.
	"""
	raw = secrets.token_hex(32)
	token_hash = _hash(raw)
	expires_at = frappe.utils.now_datetime() + datetime.timedelta(seconds=TOKEN_TTL_SECONDS)

	doc = frappe.get_doc({
		"doctype": "FHIR Access Token",
		"issued_to": user,
		"practice": practice,
		"token_hash": token_hash,
		"scope": scope,
		"expires_at": expires_at,
		"is_active": 1,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return raw, doc.name


def resolve_token(raw_token: str) -> dict:
	"""Validate a bearer token and return its context dict.

	Raises frappe.AuthenticationError on invalid/expired/inactive tokens.
	"""
	token_hash = _hash(raw_token)
	name = frappe.db.get_value(
		"FHIR Access Token",
		{"token_hash": token_hash, "is_active": 1},
		"name",
	)
	if not name:
		frappe.throw("Invalid or revoked FHIR token", frappe.AuthenticationError)

	doc = frappe.get_doc("FHIR Access Token", name)
	now = frappe.utils.now_datetime()
	if doc.expires_at and doc.expires_at < now:
		frappe.db.set_value("FHIR Access Token", name, "is_active", 0)
		frappe.db.commit()
		frappe.throw("FHIR token expired", frappe.AuthenticationError)

	return {
		"user": doc.issued_to,
		"practice": doc.practice,
		"scope": doc.scope or "",
		"token_name": doc.name,
	}


def revoke_token(raw_token: str) -> bool:
	token_hash = _hash(raw_token)
	name = frappe.db.get_value("FHIR Access Token", {"token_hash": token_hash}, "name")
	if name:
		frappe.db.set_value("FHIR Access Token", name, "is_active", 0)
		frappe.db.commit()
		return True
	return False


def _hash(raw: str) -> str:
	return hashlib.sha256(raw.encode()).hexdigest()
