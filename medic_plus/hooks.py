app_name = "medic_plus"
app_title = "Medic Plus"
app_publisher = "Thedaystar"
app_description = "Multi-tenant healthcare platform for doctors and practices"
app_email = "dev@thedaystar.co.za"
app_license = "mit"

required_apps = ["frappe/healthcare"]

# Website assets — included on all public website pages
web_include_js = ["/assets/medic_plus/js/register_links.js"]

# Fixtures — synced on bench migrate
fixtures = [
	{"dt": "Role", "filters": [["role_name", "in", ["Practice Admin", "Practice Doctor", "Practice Receptionist", "Patient"]]]},
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
	{"dt": "Workspace",       "filters": [["name", "=", "Medic Plus Platform"]]},
]

# Permission Query Conditions (data isolation per practice)
permission_query_conditions = {
	"Practice": "medic_plus.api.permissions.get_practice_permission_query",
	"Practice Member": "medic_plus.api.permissions.get_practice_permission_query",
	"Practice Setup Checklist": "medic_plus.api.permissions.get_practice_setup_checklist_permission_query",
	"Patient": "medic_plus.api.permissions.get_patient_permission_query",
	"Patient Appointment": "medic_plus.api.permissions.get_patient_appointment_permission_query",
	"Patient Encounter": "medic_plus.api.permissions.get_patient_encounter_permission_query",
	"Inpatient Record": "medic_plus.api.permissions.get_inpatient_record_permission_query",
	"Sick Note": "medic_plus.api.permissions.get_sick_note_permission_query",
	"Healthcare Practitioner": "medic_plus.api.permissions.get_healthcare_practitioner_permission_query",
	"Stock Entry": "medic_plus.api.permissions.get_stock_entry_permission_query",
	"Warehouse": "medic_plus.api.permissions.get_warehouse_permission_query",
	# Financial doctypes — scoped via practice's ERPNext Company
	"Sales Invoice": "medic_plus.api.permissions.get_sales_invoice_permission_query",
	"POS Profile": "medic_plus.api.permissions.get_pos_profile_permission_query",
	"Payment Entry": "medic_plus.api.permissions.get_payment_entry_permission_query",
	"Purchase Invoice": "medic_plus.api.permissions.get_purchase_invoice_permission_query",
	"Journal Entry": "medic_plus.api.permissions.get_journal_entry_permission_query",
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
		"on_update": [
			"medic_plus.api.doc_events.provision_dispensary_on_update",
			"medic_plus.api.doc_events.update_checklist_on_signature",
		],
	},
	# Practice Setup Checklist updates
	"Practice": {
		"on_update": "medic_plus.api.doc_events.update_checklist_on_practice_save",
	},
	"Practice Member": {
		"after_insert": "medic_plus.api.doc_events.update_checklist_on_member_status",
		"on_update": "medic_plus.api.doc_events.update_checklist_on_member_status",
	},
	# Self-registration: provision doctor/patient after email verification
	"User": {
		"on_update": "medic_plus.api.registration.on_user_verified",
	},
}

# v16: extend base DocType classes with practice-aware mixins
extend_doctype_class = {
	"Patient Appointment": "medic_plus.api.mixins.PracticeAwareMixin",
}
