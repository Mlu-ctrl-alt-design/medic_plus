"""FHIR R4 URL dispatcher — handles /api/fhir/R4/* routes.

Frappe website_route_rules maps /api/fhir/R4/<path:path> here.
The ``path`` variable is available in frappe.request.path.

Supported patterns:
  GET /api/fhir/R4/metadata
  GET /api/fhir/R4/Patient/<id>
  GET /api/fhir/R4/Patient/<id>/$everything
  GET /api/fhir/R4/Encounter/<id>
  GET /api/fhir/R4/Condition/<id>
  GET /api/fhir/R4/MedicationRequest/<id>
  GET /api/fhir/R4/AllergyIntolerance/<id>
  GET /api/fhir/R4/Observation?encounter=<id>

All responses are JSON.  Content-Type is set to application/fhir+json.
"""

import json
import frappe

no_cache = 1


def get_context(context):
	"""Frappe calls this before rendering.  We hijack it to return raw JSON."""
	try:
		result = _dispatch()
	except frappe.DoesNotExistError:
		_json_response({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found", "diagnostics": "Resource not found"}]}, status=404)
		raise
	except frappe.AuthenticationError as exc:
		_json_response({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "security", "diagnostics": str(exc)}]}, status=401)
		raise
	except frappe.PermissionError as exc:
		_json_response({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": str(exc)}]}, status=403)
		raise
	except Exception as exc:
		_json_response({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": str(exc)}]}, status=500)
		raise

	_json_response(result)
	# Return empty context — response already sent via frappe.response
	return {}


def _dispatch():
	request_path = frappe.request.path or ""
	# Strip the /api/fhir/R4 prefix
	path = request_path.removeprefix("/api/fhir/R4").lstrip("/")
	token = frappe.request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or None

	from medic_plus.api.fhir import router

	if not path or path == "metadata":
		return router.get_metadata()

	parts = path.split("/")
	resource_type = parts[0] if parts else ""
	resource_id = parts[1] if len(parts) > 1 else ""
	operation = parts[2] if len(parts) > 2 else ""

	_DISPATCH = {
		"Patient": router.get_patient,
		"Encounter": router.get_encounter,
		"Condition": router.get_condition,
		"MedicationRequest": router.get_medication_request,
		"AllergyIntolerance": router.get_allergy_intolerance,
	}

	if resource_type == "Patient" and operation == "$everything":
		return router.patient_everything(patient_id=resource_id, token=token)

	if resource_type == "Observation":
		encounter_id = frappe.request.args.get("encounter", "")
		return router.get_observations(encounter_id=encounter_id, token=token)

	if resource_type in _DISPATCH and resource_id:
		return _DISPATCH[resource_type](id=resource_id, token=token)

	frappe.throw(f"FHIR resource type '{resource_type}' not supported", frappe.DoesNotExistError)


def _json_response(data: dict, status: int = 200):
	frappe.response.update({
		"http_status_code": status,
		"content_type": "application/fhir+json",
	})
	frappe.response["message"] = data
