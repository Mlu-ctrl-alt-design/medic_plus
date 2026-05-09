"""FHIR CapabilityStatement builder for the Medic Plus FHIR R4 server.

Returns a dict that validates against fhir.resources.CapabilityStatement.
Listed resources: Patient, Encounter, Condition, MedicationRequest,
AllergyIntolerance, Observation.
"""

from __future__ import annotations


def _fhir_base_url() -> str:
	import frappe
	return f"{frappe.utils.get_url()}/api/fhir/R4"

_RESOURCES = [
	{
		"type": "Patient",
		"interaction": [{"code": "read"}, {"code": "search-type"}],
		"searchParam": [{"name": "_id", "type": "token"}],
	},
	{
		"type": "Encounter",
		"interaction": [{"code": "read"}, {"code": "search-type"}],
		"searchParam": [
			{"name": "patient", "type": "reference"},
			{"name": "_id", "type": "token"},
		],
	},
	{
		"type": "Condition",
		"interaction": [{"code": "read"}, {"code": "search-type"}],
		"searchParam": [{"name": "patient", "type": "reference"}],
	},
	{
		"type": "MedicationRequest",
		"interaction": [{"code": "read"}, {"code": "search-type"}],
		"searchParam": [{"name": "patient", "type": "reference"}],
	},
	{
		"type": "AllergyIntolerance",
		"interaction": [{"code": "read"}, {"code": "search-type"}],
		"searchParam": [{"name": "patient", "type": "reference"}],
	},
	{
		"type": "Observation",
		"interaction": [{"code": "read"}, {"code": "search-type"}],
		"searchParam": [
			{"name": "patient", "type": "reference"},
			{"name": "category", "type": "token"},
		],
	},
]


def build() -> dict:
	import frappe
	return {
		"resourceType": "CapabilityStatement",
		"id": "medic-plus-fhir-server",
		"status": "active",
		"date": frappe.utils.today(),
		"publisher": "Medic Plus (Thedaystar)",
		"kind": "instance",
		"fhirVersion": "4.0.1",
		"format": ["json"],
		"description": "Medic Plus read-only FHIR R4 server — Phase 1E. "
		               "Six resource types; SMART v2 scoped bearer tokens; "
		               "practice-tenant isolation.",
		"software": {
			"name": "medic_plus",
			"version": "0.1.28",
		},
		"implementation": {
			"description": "Medic Plus FHIR endpoint",
			"url": _fhir_base_url(),
		},
		"rest": [
			{
				"mode": "server",
				"security": {
					"cors": True,
					"service": [
						{
							"coding": [
								{
									"system": "http://terminology.hl7.org/CodeSystem/restful-security-service",
									"code": "SMART-on-FHIR",
									"display": "SMART-on-FHIR",
								}
							]
						}
					],
					"description": "SMART v2 scoped bearer tokens issued via "
					               "/api/method/medic_plus.api.fhir.router.issue_fhir_token",
				},
				"resource": _RESOURCES,
				"operation": [
					{
						"name": "everything",
						"definition": "http://hl7.org/fhir/OperationDefinition/Patient-everything",
					}
				],
			}
		],
	}
