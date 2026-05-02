app_name = "medic_plus"
app_title = "Medic Plus"
app_publisher = "Thedaystar"
app_description = "Multi-tenant healthcare platform for doctors and practices"
app_email = "dev@thedaystar.co.za"
app_license = "mit"

required_apps = ["frappe/healthcare"]

# Website assets — included on all public website pages
web_include_js = ["/assets/medic_plus/js/signup_link.js"]

# Fixtures — synced on bench migrate
fixtures = [
	{"dt": "Role", "filters": [["role_name", "in", ["Practice Admin", "Practice Doctor", "Practice Receptionist", "Patient"]]]},
	{"dt": "Custom DocPerm", "filters": [["role", "in", ["Practice Admin", "Practice Doctor", "Practice Receptionist"]]]},
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
			"Healthcare Practitioner-custom_section_associated_practices",
			"Healthcare Practitioner-associated_practices_html",
			# Item — SA medicine fields
			"Item-custom_schedule",
			"Item-custom_nappi_code",
			# Warehouse + Stock Entry — practice scoping for dispensary
			"Warehouse-custom_practice",
			"Stock Entry-custom_practice",
			# SA EMR Phase 1 (Compliance core)
			"Patient Insurance Policy-custom_sa_scheme",
			"Patient Insurance Policy-custom_principal_member_id",
			"Patient Insurance Policy-custom_dependent_code",
			"Patient Insurance Policy-custom_authorisation_reference",
			# Phase 1A — SA-PMI Patient Identity
			"Patient-custom_identifiers",
			"Patient-custom_race",
			"Patient-custom_home_language",
			"Patient-custom_preferred_language",
			"Patient-custom_popia_consent_special",
			"Patient-custom_nhid",
			# Phase 5.7 — Encounter Templates (chief complaint + orders table + antenatal fields)
			"Patient Encounter-custom_chief_complaint",
			"Patient Encounter-custom_encounter_orders",
			"Patient Encounter-custom_section_antenatal",
			"Patient Encounter-custom_gravidity",
			"Patient Encounter-custom_parity",
			"Patient Encounter-custom_gestational_age_weeks",
			"Patient Encounter-custom_column_break_antenatal",
			"Patient Encounter-custom_fundal_height_cm",
			"Patient Encounter-custom_fetal_heart_rate",
			"Patient Encounter-custom_presentation",
			"Patient Encounter-custom_engagement",
			"Patient Encounter-custom_urine_dipstick_result",
			"Patient Encounter-custom_hiv_status",
			"Patient Encounter-custom_next_visit_date",
			# Phase 5.8 — Chronic-disease follow-up template fields
			"Patient Encounter-custom_section_chronic",
			"Patient Encounter-custom_blood_pressure_systolic",
			"Patient Encounter-custom_blood_pressure_diastolic",
			"Patient Encounter-custom_weight_kg",
			"Patient Encounter-custom_bmi",
			"Patient Encounter-custom_column_break_chronic",
			"Patient Encounter-custom_smoking_status",
			"Patient Encounter-custom_alcohol_use",
			"Patient Encounter-custom_medication_adherence",
			# Phase 5.9 — Well-child template fields
			"Patient Encounter-custom_section_wellchild",
			"Patient Encounter-custom_length_height",
			"Patient Encounter-custom_head_circumference",
			"Patient Encounter-custom_column_break_wellchild",
			"Patient Encounter-custom_developmental_milestones_reviewed",
			"Patient Encounter-custom_vision_hearing_reviewed",
			"Patient Encounter-custom_nutrition_assessment",
			# Phase 1C — Structured SOAP encounter
			"Patient Encounter-custom_hopi",
			"Patient Encounter-custom_subjective",
			"Patient Encounter-custom_objective",
			"Patient Encounter-custom_assessment_text",
			"Patient Encounter-custom_assessment_code",
			"Patient Encounter-custom_plan",
			"Patient Encounter-custom_section_examination",
			"Patient Encounter-custom_examination_findings",
			# Phase 4 — Telemedicine + AI
			"Patient-custom_ai_consent",
			"Patient Appointment-custom_video_section",
			"Patient Appointment-custom_consultation_type",
			"Patient Appointment-custom_video_room_id",
			"Patient Appointment-custom_video_join_url",
			"Patient Appointment-custom_patient_join_url",
		]]],
	},
	{"dt": "Print Format",    "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Number Card",     "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Dashboard Chart", "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Workspace",       "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Page",            "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Client Script",   "filters": [["module", "=", "Medic Plus"]]},
	{"dt": "Appointment Type", "filters": [["name", "in", ["Consultation", "Follow-up", "Procedure", "Emergency", "Antenatal", "Chronic Disease Follow-up", "Well-Child Visit"]]]},
	# Phase 5.7 — Encounter Templates (platform-level templates)
	{"dt": "Encounter Template", "filters": [["is_platform_template", "=", 1]]},
	{"dt": "Notification",    "filters": [["name", "in", [
		"Payment Reminder - 7 Days Overdue",
		"Payment Reminder - 30 Days Overdue",
		"Payment Reminder - 60 Days Overdue",
	]]]},
	# SA EMR Phase 1 + 1B — code sets + scheme directory
	{"dt": "Code System",       "filters": [["name", "in", ["ICD-10", "ICD-10-ZA", "NAPPI", "LOINC", "UCUM", "ATC", "SNOMED-CT-ZA-stub"]]]},
	{"dt": "Code Value",        "filters": [["code_system", "in", ["ICD-10", "ICD-10-ZA", "NAPPI", "LOINC", "UCUM", "ATC", "SNOMED-CT-ZA-stub"]]]},
	{"dt": "Medical Aid Scheme"},
	# Phase 5.11 — Backup Drill Log (append-only audit trail, no delete)
	{"dt": "Backup Drill Log"},
]

# Permission Query Conditions (data isolation per practice)
permission_query_conditions = {
	"Practice": "medic_plus.api.permissions.get_practice_permission_query",
	"Practice Member": "medic_plus.api.permissions.get_practice_member_permission_query",
	"Practice Setup Checklist": "medic_plus.api.permissions.get_practice_setup_checklist_permission_query",
	"Patient": "medic_plus.api.permissions.get_patient_permission_query",
	"Patient Appointment": "medic_plus.api.permissions.get_patient_appointment_permission_query",
	"Patient Encounter": "medic_plus.api.permissions.get_patient_encounter_permission_query",
	"Inpatient Record": "medic_plus.api.permissions.get_inpatient_record_permission_query",
	"Patient Medical Record": "medic_plus.api.permissions.get_patient_medical_record_permission_query",
	# SA EMR Phase 1 — clinical-data PQCs that scope via patient.custom_practice
	"Patient Allergy": "medic_plus.api.permissions.get_patient_allergy_permission_query",
	"Patient Chronic Condition": "medic_plus.api.permissions.get_patient_chronic_condition_permission_query",
	"Patient Insurance Policy": "medic_plus.api.permissions.get_patient_insurance_policy_permission_query",
	"Patient Insurance Coverage": "medic_plus.api.permissions.get_patient_insurance_coverage_permission_query",
	# Phase 1A — SA-PMI Patient Identity
	"Patient Identifier": "medic_plus.api.permissions.get_patient_identifier_permission_query",
	# Phase 1C — Structured SOAP encounter + Problem List
	"Patient Problem List": "medic_plus.api.permissions.get_patient_problem_list_permission_query",
	# Phase 5.7 — Encounter Templates
	"Encounter Template": "medic_plus.api.permissions.get_encounter_template_permission_query",
	"Sick Note": "medic_plus.api.permissions.get_sick_note_permission_query",
	"Healthcare Practitioner": "medic_plus.api.permissions.get_healthcare_practitioner_permission_query",
	"Practitioner Schedule": "medic_plus.api.permissions.get_practitioner_schedule_permission_query",
	"Stock Entry": "medic_plus.api.permissions.get_stock_entry_permission_query",
	"Warehouse": "medic_plus.api.permissions.get_warehouse_permission_query",
	# Data masking / consent
	"Data Unmask Request": "medic_plus.api.permissions.get_data_unmask_request_permission_query",
	"Clinical Access Log": "medic_plus.api.permissions.get_clinical_access_log_permission_query",
	# Phase 4 — Telemedicine + AI
	"Practice AI Settings": "medic_plus.api.permissions.get_practice_ai_settings_permission_query",
	"AI Inference Log": "medic_plus.api.permissions.get_ai_inference_log_permission_query",
	"Telemedicine Consent": "medic_plus.api.permissions.get_telemedicine_consent_permission_query",
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
		"validate": "medic_plus.api.doc_events.validate_patient_identifiers",
	},
	"Patient Appointment": {
		"before_insert": "medic_plus.api.doc_events.set_practice_on_insert",
	},
	"Patient Encounter": {
		"before_insert": [
			"medic_plus.api.doc_events.set_practice_on_insert",
			"medic_plus.api.doc_events.apply_encounter_template",
		],
		"before_submit": "medic_plus.api.doc_events.validate_encounter_template_fields",
		"on_submit": "medic_plus.api.doc_events.on_encounter_submit",
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
	# Practice Setup Checklist — steps 1–6
	"Practice": {
		"after_insert": [
			"medic_plus.api.billing.start_trial_for_practice",
			"medic_plus.api.doc_events.sync_practice_doctors",
		],
		"on_update": [
			"medic_plus.api.doc_events.update_checklist_on_practice_save",
			"medic_plus.api.doc_events.sync_practice_doctors",
		],
	},
	"Practice Member": {
		"after_insert": "medic_plus.api.doc_events.update_checklist_on_member_status",
		"on_update": "medic_plus.api.doc_events.update_checklist_on_member_status",
	},
	"Practitioner Schedule": {
		"after_insert": "medic_plus.api.doc_events.update_checklist_on_schedule_created",
	},
	"Sales Invoice": {
		"after_insert": "medic_plus.api.doc_events.update_checklist_on_first_invoice",
	},

}

scheduler_events = {
	"cron": {
		"*/15 * * * *": [
			"medic_plus.api.data_access.expire_stale_requests",
			"medic_plus.api.signup.retry_failed_provisioning",
		],
		# 1st of each month at 08:00 — backup-drill reminder
		"0 8 1 * *": [
			"medic_plus.api.backup_drill.send_drill_reminder",
		],
	},
	"daily": [
		"medic_plus.api.retention.flag_overdue_records",
	],
}

# v16: extend base DocType classes with practice-aware mixins
extend_doctype_class = {
	"Patient Appointment": "medic_plus.api.mixins.PracticeAwareMixin",
}
