app_name = "medic_plus"
app_title = "Medic Plus"
app_publisher = "Thedaystar"
app_description = "Multi-tenant healthcare platform for doctors and practices"
app_email = "dev@thedaystar.co.za"
app_license = "mit"

required_apps = ["frappe/healthcare"]

# Fixtures — synced on bench migrate
fixtures = [
	{"dt": "Role", "filters": [["role_name", "in", ["Practice Admin", "Practice Doctor", "Practice Receptionist"]]]},
	{
		"dt": "Custom Field",
		"filters": [["name", "in", [
			"Patient-custom_practice",
			"Patient Appointment-custom_practice",
			"Patient Encounter-custom_practice",
			"Inpatient Record-custom_practice",
		]]],
	},
]

# Permission Query Conditions (data isolation per practice)
permission_query_conditions = {
	"Practice": "medic_plus.api.permissions.get_practice_permission_query",
	"Practice Member": "medic_plus.api.permissions.get_practice_permission_query",
	"Patient": "medic_plus.api.permissions.get_patient_permission_query",
	"Patient Appointment": "medic_plus.api.permissions.get_patient_appointment_permission_query",
	"Patient Encounter": "medic_plus.api.permissions.get_patient_encounter_permission_query",
	"Inpatient Record": "medic_plus.api.permissions.get_inpatient_record_permission_query",
	"Sick Note": "medic_plus.api.permissions.get_sick_note_permission_query",
	"Healthcare Practitioner": "medic_plus.api.permissions.get_healthcare_practitioner_permission_query",
}

# Auto-set practice on all healthcare document creates
doc_events = {
	"Patient": {
		"before_insert": "medic_plus.api.doc_events.set_practice_on_insert",
	},
	"Patient Appointment": {
		"before_insert": "medic_plus.api.doc_events.set_practice_on_insert",
	},
	"Patient Encounter": {
		"before_insert": "medic_plus.api.doc_events.set_practice_on_insert",
	},
	"Inpatient Record": {
		"before_insert": "medic_plus.api.doc_events.set_practice_on_insert",
	},
}

# v16: extend base DocType classes with practice-aware mixins
extend_doctype_class = {
	"Patient Appointment": "medic_plus.api.mixins.PracticeAwareMixin",
}
