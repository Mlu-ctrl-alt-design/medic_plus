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
			# Patient scoping
			"Patient-custom_practice",
			"Patient Appointment-custom_practice",
			"Patient Encounter-custom_practice",
			"Inpatient Record-custom_practice",
			# Healthcare Practitioner — SA compliance + signature + dispensing
			"Healthcare Practitioner-custom_section_practice_details",
			"Healthcare Practitioner-custom_hpcsa_number",
			"Healthcare Practitioner-custom_practice_number",
			"Healthcare Practitioner-custom_is_dispensing_doctor",
			"Healthcare Practitioner-custom_column_break_signature",
			"Healthcare Practitioner-custom_practitioner_signature",
			# Item — SA medicine fields
			"Item-custom_schedule",
			"Item-custom_nappi_code",
			# Warehouse + Stock Entry — practice scoping for dispensary
			"Warehouse-custom_practice",
			"Stock Entry-custom_practice",
		]]],
	},
	{"dt": "Print Format",    "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Number Card",     "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Dashboard Chart", "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Workspace",       "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Client Script",   "filters": [["module", "=", "Medic Plus"]]},
]

# Permission Query Conditions (data isolation per practice)
permission_query_conditions = {
	"Practice": "medic_plus.api.permissions.get_practice_permission_query",
	"Practice Member": "medic_plus.api.permissions.get_practice_member_permission_query",
	"Patient": "medic_plus.api.permissions.get_patient_permission_query",
	"Patient Appointment": "medic_plus.api.permissions.get_patient_appointment_permission_query",
	"Patient Encounter": "medic_plus.api.permissions.get_patient_encounter_permission_query",
	"Inpatient Record": "medic_plus.api.permissions.get_inpatient_record_permission_query",
	"Sick Note": "medic_plus.api.permissions.get_sick_note_permission_query",
	"Healthcare Practitioner": "medic_plus.api.permissions.get_healthcare_practitioner_permission_query",
	"Stock Entry": "medic_plus.api.permissions.get_stock_entry_permission_query",
	"Warehouse": "medic_plus.api.permissions.get_warehouse_permission_query",
	# Data masking / consent
	"Data Unmask Request": "medic_plus.api.permissions.get_data_unmask_request_permission_query",
	"Clinical Access Log": "medic_plus.api.permissions.get_clinical_access_log_permission_query",
}

# Document event hooks
doc_events = {
	# Auto-set practice on all healthcare document creates
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
	# Provisioning hooks
	"Healthcare Practitioner": {
		"on_update": "medic_plus.api.doc_events.provision_dispensary_on_update",
	},
}

# Scheduler — expire stale unmask requests every 15 minutes
scheduler_events = {
	"cron": {
		"*/15 * * * *": [
			"medic_plus.api.data_access.expire_stale_requests",
		],
	},
}

# v16: extend base DocType classes with practice-aware mixins
extend_doctype_class = {
	"Patient Appointment": "medic_plus.api.mixins.PracticeAwareMixin",
}
