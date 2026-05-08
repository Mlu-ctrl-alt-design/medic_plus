"""Insurance Claims API — whitelisted endpoints for claim management."""

from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist()
def submit_claim(claim_name: str) -> dict:
	"""Submit a Draft Insurance Claim to the Healthbridge switch.

	Transitions the claim through Draft → Submitted → Accepted/Partial/Error.
	Returns a dict with the final status and per-line results.
	"""
	claim = frappe.get_doc("Insurance Claim", claim_name)
	_assert_practice_access(claim)

	if claim.status != "Draft":
		frappe.throw(_(f"Claim {claim_name} is in status '{claim.status}' — only Draft claims can be submitted."))

	# Mark as Submitted before the network call so a server crash leaves an
	# auditable trace rather than silently re-sending.
	claim.status = "Submitted"
	claim.submitted_at = frappe.utils.now_datetime()
	claim.save(ignore_permissions=True)

	from medic_plus.api.healthbridge_client import submit_to_switch
	try:
		result = submit_to_switch(claim_name)
	except Exception as exc:
		claim.status = "Error"
		claim.response_message = str(exc)
		claim.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(str(exc))

	_apply_result(claim, result)
	claim.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": claim.status,
		"switch_reference": claim.switch_reference,
		"response_code": claim.response_code,
		"response_message": claim.response_message,
		"line_statuses": [
			{
				"code": ln.code,
				"line_type": ln.line_type,
				"status": ln.status,
				"rejection_reason": ln.rejection_reason or "",
			}
			for ln in (claim.claim_lines or [])
		],
	}


@frappe.whitelist()
def get_claim_for_encounter(encounter_name: str) -> dict | None:
	"""Return the Insurance Claim for a given encounter (if any)."""
	name = frappe.db.get_value("Insurance Claim", {"encounter": encounter_name}, "name")
	if not name:
		return None
	claim = frappe.get_doc("Insurance Claim", name)
	_assert_practice_access(claim)
	return claim.as_dict()


def _assert_practice_access(claim) -> None:
	"""Raise PermissionError if the session user does not belong to claim.practice."""
	if "Healthcare Administrator" in frappe.get_roles():
		return
	user_practice = frappe.db.get_value(
		"Practice Member", {"user": frappe.session.user}, "practice"
	)
	if user_practice != claim.practice:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _apply_result(claim, result: dict) -> None:
	claim.switch_reference = result.get("switch_reference") or ""
	claim.response_code = result.get("response_code") or ""
	claim.response_message = result.get("response_message") or ""
	claim.raw_response = result.get("raw") or ""

	if result.get("success"):
		claim.status = result.get("overall_status", "Accepted")
		# Apply per-line statuses from switch response
		line_map = {ls["code"]: ls for ls in (result.get("line_statuses") or [])}
		for ln in (claim.claim_lines or []):
			ls = line_map.get(ln.code)
			if ls:
				ln.status = ls.get("status", "Accepted")
				ln.rejection_reason = ls.get("rejection_reason", "")
			elif not line_map:
				# Switch returned no per-line data → accept all
				ln.status = "Accepted"
	else:
		claim.status = "Error"


def auto_build_claim_for_encounter(encounter_name: str) -> str | None:
	"""Build and persist a Draft Insurance Claim from a submitted encounter.

	Called from doc_events.build_claim_on_submit.  Returns the new claim name
	or None if the encounter has no claimable lines.
	"""
	from medic_plus.api.claim_builder import build_claim

	if frappe.db.exists("Insurance Claim", {"encounter": encounter_name}):
		return None  # idempotent — claim already exists

	try:
		claim = build_claim(encounter_name)
	except Exception as exc:
		frappe.log_error(
			f"Claim auto-build failed for {encounter_name}: {exc}",
			"Claims Auto-Build",
		)
		return None

	if claim is None:
		return None

	try:
		claim.insert(ignore_permissions=True)
		frappe.db.commit()
		return claim.name
	except Exception as exc:
		frappe.log_error(
			f"Claim insert failed for {encounter_name}: {exc}",
			"Claims Auto-Build",
		)
		frappe.db.rollback()
		return None
