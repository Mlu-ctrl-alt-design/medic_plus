"""FHIR R4 REST router — whitelisted Frappe endpoints.

Endpoint pattern (via website_route_rules):
  GET /api/fhir/R4/metadata                       → CapabilityStatement
  GET /api/fhir/R4/<ResourceType>/<id>            → single resource
  GET /api/fhir/R4/<ResourceType>?patient=<id>    → search
  GET /api/fhir/R4/Patient/<id>/$everything       → Bundle

Whitelisted functions are also reachable as:
  /api/method/medic_plus.api.fhir.router.<fn>

Token auth:
  Bearer token in Authorization header (or ?token= query param for tests).
  Resolved via fhir.token.resolve_token().
  Session user (Frappe login) is accepted as fallback for same-site SPA.

Cross-tenant enforcement mirrors PQC logic but is applied in Python
rather than SQL — the resource mapper loads the doc, then we check
whether the doc's practice matches the token's practice.
"""

from __future__ import annotations

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Token issuance
# ---------------------------------------------------------------------------

@frappe.whitelist()
def issue_fhir_token(practice: str, scope: str = "patient/*.read") -> dict:
	"""Issue a SMART-on-FHIR bearer token for the current session user.

	Requires the user to be a Practice Member of the requested practice.
	Returns {access_token, token_type, expires_in, scope}.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)
	_assert_practice_member(user, practice)

	from medic_plus.api.fhir.token import issue_token, TOKEN_TTL_SECONDS
	raw, _doc_name = issue_token(user, practice, scope)
	return {
		"access_token": raw,
		"token_type": "Bearer",
		"expires_in": TOKEN_TTL_SECONDS,
		"scope": scope,
	}


# ---------------------------------------------------------------------------
# CapabilityStatement
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_metadata() -> dict:
	"""Return the FHIR CapabilityStatement (no auth required)."""
	from medic_plus.api.fhir.capability_statement import build
	return build()


# ---------------------------------------------------------------------------
# Per-resource GET
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_patient(id: str, token: str = None) -> dict:
	ctx = _resolve_context(token)
	doc = frappe.get_doc("Patient", id)
	_assert_resource_practice(doc, ctx, "custom_practice")
	from medic_plus.api.fhir.mappers import patient_to_fhir
	return patient_to_fhir(id)


@frappe.whitelist()
def get_encounter(id: str, token: str = None) -> dict:
	ctx = _resolve_context(token)
	doc = frappe.get_doc("Patient Encounter", id)
	_assert_resource_practice(doc, ctx, "custom_practice")
	from medic_plus.api.fhir.mappers import encounter_to_fhir
	return encounter_to_fhir(id)


@frappe.whitelist()
def get_condition(id: str, token: str = None) -> dict:
	"""Condition is derived from encounter diagnosis; id = encounter name."""
	ctx = _resolve_context(token)
	doc = frappe.get_doc("Patient Encounter", id)
	_assert_resource_practice(doc, ctx, "custom_practice")
	from medic_plus.api.fhir.mappers import condition_to_fhir
	result = condition_to_fhir(id)
	if result is None:
		frappe.throw(_("Condition not found"), frappe.DoesNotExistError)
	return result


@frappe.whitelist()
def get_medication_request(id: str, token: str = None) -> dict:
	"""MedicationRequest derived from encounter; id = encounter name."""
	ctx = _resolve_context(token)
	doc = frappe.get_doc("Patient Encounter", id)
	_assert_resource_practice(doc, ctx, "custom_practice")
	from medic_plus.api.fhir.mappers import medication_request_to_fhir
	result = medication_request_to_fhir(id)
	if result is None:
		frappe.throw(_("MedicationRequest not found"), frappe.DoesNotExistError)
	return result


@frappe.whitelist()
def get_allergy_intolerance(id: str, token: str = None) -> dict:
	ctx = _resolve_context(token)
	allergy = frappe.get_doc("Patient Allergy", id)
	patient_practice = frappe.db.get_value("Patient", allergy.patient, "custom_practice")
	if ctx and ctx.get("practice") and patient_practice != ctx["practice"]:
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	from medic_plus.api.fhir.mappers import allergy_to_fhir
	return allergy_to_fhir(id)


@frappe.whitelist()
def get_observations(encounter_id: str, token: str = None) -> dict:
	"""Return a Bundle of Observation resources for the encounter's vitals."""
	ctx = _resolve_context(token)
	doc = frappe.get_doc("Patient Encounter", encounter_id)
	_assert_resource_practice(doc, ctx, "custom_practice")
	from medic_plus.api.fhir.mappers import vitals_to_fhir
	entries = [
		{"resource": obs} for obs in vitals_to_fhir(encounter_id)
	]
	return {
		"resourceType": "Bundle",
		"type": "searchset",
		"total": len(entries),
		"entry": entries,
	}


# ---------------------------------------------------------------------------
# $everything — Patient Bundle
# ---------------------------------------------------------------------------

@frappe.whitelist()
def patient_everything(patient_id: str, token: str = None) -> dict:
	"""Return a Bundle with all resources for a patient (FHIR $everything)."""
	ctx = _resolve_context(token)
	patient_doc = frappe.get_doc("Patient", patient_id)
	_assert_resource_practice(patient_doc, ctx, "custom_practice")

	from medic_plus.api.fhir.mappers import (
		patient_to_fhir,
		encounter_to_fhir,
		condition_to_fhir,
		medication_request_to_fhir,
		allergy_to_fhir,
		vitals_to_fhir,
	)

	entries = [{"resource": patient_to_fhir(patient_id)}]

	encounter_names = frappe.get_all(
		"Patient Encounter",
		filters={"patient": patient_id},
		pluck="name",
		limit=50,
	)
	for enc_name in encounter_names:
		entries.append({"resource": encounter_to_fhir(enc_name)})
		cond = condition_to_fhir(enc_name)
		if cond:
			entries.append({"resource": cond})
		med = medication_request_to_fhir(enc_name)
		if med:
			entries.append({"resource": med})
		for obs in vitals_to_fhir(enc_name):
			entries.append({"resource": obs})

	allergy_names = frappe.get_all(
		"Patient Allergy",
		filters={"patient": patient_id},
		pluck="name",
		limit=50,
	)
	for al in allergy_names:
		entries.append({"resource": allergy_to_fhir(al)})

	return {
		"resourceType": "Bundle",
		"type": "collection",
		"total": len(entries),
		"entry": entries,
	}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_context(raw_token: str | None) -> dict | None:
	"""Resolve token context.  Falls back to session user if no token provided."""
	if raw_token:
		from medic_plus.api.fhir.token import resolve_token
		return resolve_token(raw_token)

	# No bearer token — try session user (same-site SPA usage)
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)

	practice = frappe.db.get_value(
		"Practice Member", {"user": user}, "practice"
	)
	if not practice and "Healthcare Administrator" not in frappe.get_roles(user):
		frappe.throw(_("No practice context — obtain a FHIR bearer token"), frappe.AuthenticationError)

	return {"user": user, "practice": practice, "scope": "patient/*.read"}


def _assert_resource_practice(doc, ctx: dict | None, practice_field: str) -> None:
	"""Deny cross-tenant access.  Platform admins bypass."""
	if ctx is None:
		return
	if "Healthcare Administrator" in frappe.get_roles(ctx.get("user") or frappe.session.user):
		return
	resource_practice = doc.get(practice_field) or ""
	token_practice = ctx.get("practice") or ""
	if token_practice and resource_practice != token_practice:
		frappe.throw(_("Not found"), frappe.DoesNotExistError)


def _assert_practice_member(user: str, practice: str) -> None:
	if "Healthcare Administrator" in frappe.get_roles(user):
		return
	member = frappe.db.get_value(
		"Practice Member", {"user": user, "practice": practice}, "name"
	)
	if not member:
		frappe.throw(
			_(f"User {user} is not a member of practice {practice}"),
			frappe.PermissionError,
		)
