"""Whitelisted endpoints for the Daystar Health SPA at /daystar-health.

Each endpoint is a thin orchestrator:
  - resolve the active Practice via practice_resolver (raises PermissionError
    when the caller has no Practice Member row);
  - run the doctype-scoped queries;
  - hand them to the appropriate aggregator for shaping;
  - return a JSON-serialisable payload.

Heavy logic lives in the deep modules (dashboard_aggregator,
patient_summary, …) so it can be tested in isolation.
"""

import json
from datetime import date, timedelta

import frappe
from frappe.utils import getdate

from medic_plus.api.dashboard_aggregator import build_dashboard
from medic_plus.api.patient_summary import build_patient_summary
from medic_plus.api.practice_resolver import get_active_practice


@frappe.whitelist()
def get_dashboard() -> dict:
    """Return the dashboard payload for the logged-in user's active Practice."""
    practice = get_active_practice()
    return build_dashboard(practice=practice, user=frappe.session.user)


_USER_PROFILE_FIELDS = (
    "name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "user_image",
)

_PRACTITIONER_PROFILE_FIELDS = (
    "name",
    "department",
    "custom_hpcsa_number",
    "custom_practice_number",
)


@frappe.whitelist()
def get_my_practitioner_profile() -> dict:
    """Return the read-only profile for the logged-in practitioner.

    Joins ``User`` core fields with the ``Healthcare Practitioner`` linked
    via the user's ``Practice Member`` row. Raises ``PermissionError`` for
    callers without a Practice — the SPA surfaces that as the no-practice
    error card, same as every other endpoint.
    """
    practice = get_active_practice()
    user_email = frappe.session.user
    user_row = frappe.db.get_value(
        "User", user_email, list(_USER_PROFILE_FIELDS), as_dict=True
    ) or {}
    practitioner_name = frappe.db.get_value(
        "Practice Member",
        {"user": user_email, "practice": practice},
        "practitioner",
    )
    practitioner_row = {}
    if practitioner_name:
        practitioner_row = frappe.db.get_value(
            "Healthcare Practitioner",
            practitioner_name,
            list(_PRACTITIONER_PROFILE_FIELDS),
            as_dict=True,
        ) or {}
    # 2FA per-user state is inferred from frappe.utils.user.user_has_2fa
    # (the User doctype has no direct boolean for it). Returned as a flat
    # field so the SPA can render an enabled/disabled badge without another
    # round trip.
    try:
        from frappe.utils.user import user_has_2fa
        twofa_enabled = bool(user_has_2fa(user_email))
    except Exception:
        twofa_enabled = False

    return {
        "user": dict(user_row),
        "practitioner": dict(practitioner_row),
        "practice": practice,
        "two_factor_authentication": twofa_enabled,
    }


_APPOINTMENT_FIELDS = (
    "name",
    "appointment_date",
    "appointment_time",
    "patient",
    "patient_name",
    "practitioner",
    "practitioner_name",
    "appointment_type",
    "status",
)

_DEFAULT_STATUSES = ["Scheduled", "Open", "Checked In"]


def _format_appointments(rows: list, enc_by_appt: dict | None = None) -> list:
    """Shape raw Patient Appointment dicts into SPA-ready dicts.

    Pure transformation — no DB calls, no session access. Tested in isolation.
    enc_by_appt maps appointment name → encounter name for appointments that
    already have a linked Patient Encounter.
    """
    enc_by_appt = enc_by_appt or {}
    return [
        {
            "name": r.get("name"),
            "appointment_date": str(r.get("appointment_date") or ""),
            "appointment_time": str(r.get("appointment_time") or ""),
            "patient": r.get("patient"),
            "patient_name": r.get("patient_name"),
            "practitioner": r.get("practitioner"),
            "practitioner_name": r.get("practitioner_name"),
            "appointment_type": r.get("appointment_type"),
            "status": r.get("status"),
            "encounter": enc_by_appt.get(r.get("name")),
        }
        for r in rows
    ]


@frappe.whitelist()
def get_appointments(filters=None) -> list:
    """Return Patient Appointments for the logged-in user's active Practice.

    Default window: today → +7 days. Default statuses: Scheduled and Open.
    Accepts an optional ``filters`` dict (or JSON string) with keys:
      ``date_from``, ``date_to``, ``status`` (str or list), ``practitioner``.
    Returns at most 200 rows ordered by appointment_date / appointment_time asc.
    """
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}
    filters = filters or {}

    practice = get_active_practice()
    today = date.today()
    date_from = filters.get("date_from") or str(today)
    date_to = filters.get("date_to") or str(today + timedelta(days=7))

    status_filter = filters.get("status") or _DEFAULT_STATUSES
    if isinstance(status_filter, str):
        status_filter = [status_filter]

    doctype_filters = {
        "custom_practice": practice,
        "appointment_date": ["between", [date_from, date_to]],
        "status": ["in", status_filter],
    }
    practitioner = filters.get("practitioner")
    if practitioner:
        doctype_filters["practitioner"] = practitioner

    rows = frappe.get_all(
        "Patient Appointment",
        filters=doctype_filters,
        fields=list(_APPOINTMENT_FIELDS),
        order_by="appointment_date asc, appointment_time asc",
        limit=200,
    )
    enc_by_appt: dict = {}
    if rows:
        encs = frappe.get_all(
            "Patient Encounter",
            filters={"appointment": ["in", [r["name"] for r in rows]]},
            fields=["name", "appointment"],
            limit=len(rows) * 2,
        )
        enc_by_appt = {e["appointment"]: e["name"] for e in encs}
    return _format_appointments(rows, enc_by_appt)


_MEDICAL_RECORD_FIELDS = (
    "name",
    "patient",
    "communication_date",
    "reference_doctype",
    "reference_name",
    "subject",
    "user",
    "attach",
)
_MEDICAL_RECORD_PAGE_DEFAULT = 50
_MEDICAL_RECORD_PAGE_MAX = 200
_MEDICAL_RECORD_SUBJECT_MAX = 240


def _format_medical_records(rows: list, patient_name_by_id: dict) -> list:
    """Shape raw Patient Medical Record dicts into SPA-ready rows.

    Truncates ``subject`` to keep the table compact and surfaces a boolean
    ``has_attach`` rather than the raw file URL (private files cannot be
    rendered cross-user; the source doc carries the canonical attachment).
    """
    out = []
    for r in rows:
        subject = (r.get("subject") or "").strip()
        if len(subject) > _MEDICAL_RECORD_SUBJECT_MAX:
            subject = subject[: _MEDICAL_RECORD_SUBJECT_MAX - 1] + "…"
        out.append({
            "name": r.get("name"),
            "patient": r.get("patient"),
            "patient_name": patient_name_by_id.get(r.get("patient")),
            "communication_date": str(r.get("communication_date") or ""),
            "reference_doctype": r.get("reference_doctype"),
            "reference_name": r.get("reference_name"),
            "subject": subject,
            "user": r.get("user"),
            "has_attach": bool(r.get("attach")),
        })
    return out


@frappe.whitelist()
def get_medical_records(filters=None, limit_start=0, limit_page_length=None) -> dict:
    """Return Patient Medical Record rows for the active Practice.

    Returns a dict shaped ``{rows, total, limit_start, limit_page_length}`` so
    the SPA can render pagination. Patient Medical Record has no
    ``custom_practice`` field — scope is enforced by joining on Patient. The
    PQC ``get_patient_medical_record_permission_query`` is the defence
    in depth; this query restates the same constraint at the API level.

    Filters dict (or JSON string) keys:
      ``patient`` (single Patient name)
      ``reference_doctype`` (str or list — Patient Encounter / Lab Test / …)
      ``date_from`` / ``date_to`` (YYYY-MM-DD; default last 30 days)
    """
    from medic_plus.api.perf import track_call
    track_call("get_medical_records")
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}
    filters = filters or {}

    try:
        limit_start = int(limit_start or 0)
    except (TypeError, ValueError):
        limit_start = 0
    try:
        limit_page_length = int(limit_page_length or _MEDICAL_RECORD_PAGE_DEFAULT)
    except (TypeError, ValueError):
        limit_page_length = _MEDICAL_RECORD_PAGE_DEFAULT
    limit_page_length = max(1, min(limit_page_length, _MEDICAL_RECORD_PAGE_MAX))

    practice = get_active_practice()
    today = date.today()
    date_from = filters.get("date_from") or str(today - timedelta(days=30))
    date_to = filters.get("date_to") or str(today)

    practice_patients = frappe.get_all(
        "Patient",
        filters={"custom_practice": practice},
        pluck="name",
        limit=0,
    )
    if not practice_patients:
        return {"rows": [], "total": 0, "limit_start": limit_start, "limit_page_length": limit_page_length}

    pmr_filters = {
        "patient": ["in", practice_patients],
        "communication_date": ["between", [date_from, date_to]],
    }
    requested_patient = filters.get("patient")
    if requested_patient:
        if requested_patient not in practice_patients:
            # Caller asked for a Patient outside the active practice — no rows.
            return {"rows": [], "total": 0, "limit_start": limit_start, "limit_page_length": limit_page_length}
        pmr_filters["patient"] = requested_patient

    ref_doctype = filters.get("reference_doctype")
    if ref_doctype:
        if isinstance(ref_doctype, str):
            ref_doctype = [ref_doctype]
        pmr_filters["reference_doctype"] = ["in", ref_doctype]

    total = frappe.db.count("Patient Medical Record", filters=pmr_filters)
    rows = frappe.get_all(
        "Patient Medical Record",
        filters=pmr_filters,
        fields=list(_MEDICAL_RECORD_FIELDS),
        order_by="communication_date desc, creation desc",
        limit_start=limit_start,
        limit_page_length=limit_page_length,
    )
    patient_ids = list({r["patient"] for r in rows if r.get("patient")})
    patient_name_by_id = {}
    if patient_ids:
        for p in frappe.get_all(
            "Patient",
            filters={"name": ["in", patient_ids]},
            fields=["name", "patient_name"],
        ):
            patient_name_by_id[p["name"]] = p.get("patient_name")

    return {
        "rows": _format_medical_records(rows, patient_name_by_id),
        "total": total,
        "limit_start": limit_start,
        "limit_page_length": limit_page_length,
    }


# ── SA EMR Phase 1: Allergies + Chronic Conditions + Medical Aid ─────

def _assert_patient_in_active_practice(patient: str) -> str:
    """Cross-tenant guard. Returns the active practice if the call is allowed.

    Same shape as get_patient_detail's guard — caller's active Practice must
    own the requested Patient. Raises PermissionError otherwise so the
    response cannot be used to probe Practice membership.
    """
    practice = get_active_practice()
    patient_practice = frappe.db.get_value("Patient", patient, "custom_practice")
    if patient_practice != practice:
        raise frappe.PermissionError("Patient does not belong to your practice.")
    return practice


@frappe.whitelist()
def get_patient_allergies(patient: str) -> list:
    """Return Patient Allergy rows for the requested patient (active-practice only)."""
    _assert_patient_in_active_practice(patient)
    rows = frappe.get_all(
        "Patient Allergy",
        filters={"patient": patient},
        fields=[
            "name", "status", "category", "substance", "severity", "criticality",
            "reaction", "onset_date", "verified_by", "verified_on", "notes",
        ],
        order_by="status asc, severity desc, modified desc",
        limit=200,
    )
    return [
        {**r, "onset_date": str(r["onset_date"] or ""), "verified_on": str(r["verified_on"] or "")}
        for r in rows
    ]


@frappe.whitelist()
def get_patient_chronic_conditions(patient: str) -> list:
    """Return Patient Chronic Condition rows for the requested patient."""
    _assert_patient_in_active_practice(patient)
    rows = frappe.get_all(
        "Patient Chronic Condition",
        filters={"patient": patient},
        fields=[
            "name", "chronic_status", "diagnosis", "icd10_code", "started_on",
            "resolved_on", "severity", "managing_practitioner", "notes",
        ],
        order_by="chronic_status asc, started_on desc",
        limit=200,
    )
    return [
        {**r, "started_on": str(r["started_on"] or ""), "resolved_on": str(r["resolved_on"] or "")}
        for r in rows
    ]


def _search_code_values(*, system: str, query: str, limit) -> list:
	"""Internal: prefix/substring search inside a single Code System."""
	try:
		limit = int(limit)
	except (TypeError, ValueError):
		limit = 25
	limit = max(1, min(limit, 100))

	q = (query or "").strip()
	if q:
		from frappe.query_builder import DocType
		from frappe.query_builder.functions import Lower
		cv = DocType("Code Value")
		rows = (
			frappe.qb.from_(cv)
			.select(cv.name, cv.code_value, cv.display)
			.where(cv.code_system == system)
			.where(
				Lower(cv.code_value).like(f"{q.lower()}%")
				| Lower(cv.display).like(f"%{q.lower()}%")
			)
			.orderby(cv.code_value)
			.limit(limit)
			.run(as_dict=True)
		)
	else:
		rows = frappe.get_all(
			"Code Value",
			filters={"code_system": system},
			fields=["name", "code_value", "display"],
			order_by="code_value asc",
			limit=limit,
		)
	return [
		{"name": r["name"], "code": r["code_value"], "display": r["display"] or ""}
		for r in rows
	]


@frappe.whitelist()
def get_active_practice_details() -> dict:
	"""Return the active practice's fields for the daystar-health Practice screen.

	Mirrors what's visible on the Desk Practice form, minus sensitive
	subscription identifiers (yoco_*, raw payment refs). Auth is enforced
	by session; practice scope is the caller's Practice Member row.
	"""
	user = frappe.session.user
	practice_name = frappe.db.get_value("Practice Member", {"user": user}, "practice")
	if not practice_name:
		frappe.throw(_("No practice associated with your account."), frappe.PermissionError)

	doc = frappe.get_doc("Practice", practice_name)
	visible = (
		"name", "practice_name", "slug", "is_active",
		"subscription_plan", "subscription_status",
		"trial_ends_on", "current_period_end",
		"phone", "email", "address",
		"logo", "color", "owner_practitioner",
		"company",
	)
	out = {k: doc.get(k) for k in visible}

	# Owner practitioner display name (if set).
	if out.get("owner_practitioner"):
		out["owner_practitioner_name"] = frappe.db.get_value(
			"Healthcare Practitioner", out["owner_practitioner"], "practitioner_name"
		)

	# Doctor list — practice doctors via Practice Member rows.
	doctors = frappe.get_all(
		"Practice Member",
		filters={"practice": practice_name, "role": ("in", ("Doctor", "Admin"))},
		fields=["name", "user", "role", "practitioner"],
		order_by="role asc, creation asc",
		ignore_permissions=True,
	)
	for d in doctors:
		if d.get("practitioner"):
			d["practitioner_name"] = frappe.db.get_value(
				"Healthcare Practitioner", d["practitioner"], "practitioner_name"
			)
	out["doctors"] = doctors
	return out


@frappe.whitelist()
def create_visit(payload: dict | str = None) -> dict:
	"""Create a Patient Appointment + linked Patient Encounter in one shot.

	The SPA's New Visit drawer is the doctor's single starting point for
	an encounter — but a clinical encounter without a corresponding
	Appointment doesn't show up on the schedule, which is wrong for a
	practice management workflow. This wraps both inserts in one
	transaction, linked via Patient Encounter.appointment.

	`payload` carries: patient, practitioner, encounter_date,
	encounter_time, appointment_type, chief_complaint, custom_* SOAP
	fields, custom_examination_findings (list), custom_encounter_orders
	(list). Returns {"appointment": <name>, "encounter": <name>}.

	custom_practice is stamped explicitly on both (the before_insert hook
	does this too, but we want to fail loudly here if the user has no
	practice rather than silently inserting with no tenant scope).
	"""
	if isinstance(payload, str):
		try:
			payload = json.loads(payload)
		except Exception:
			payload = {}
	payload = payload or {}

	practice = get_active_practice()  # raises PermissionError if no Practice Member row
	# Stamp the practice's ERPNext Company explicitly on both docs. Without
	# this Frappe falls back to User Defaults → Global default_company,
	# which the practice doctor has no read perm for → "Insufficient
	# Permission for Company" at insert time.
	company = frappe.db.get_value("Practice", practice, "company")
	if not company:
		frappe.throw(
			_("Your practice has no linked ERPNext Company. Ask an admin to provision the company before creating visits."),
			frappe.ValidationError,
		)

	patient = payload.get("patient")
	practitioner = payload.get("practitioner")
	encounter_date = payload.get("encounter_date")
	chief_complaint = (payload.get("custom_chief_complaint") or "").strip()
	if not (patient and practitioner and encounter_date and chief_complaint):
		frappe.throw(_("Patient, practitioner, date and chief complaint are required."))

	encounter_time = payload.get("encounter_time") or "09:00:00"
	appointment_type = payload.get("appointment_type") or "Consultation"

	# Both inserts in one logical unit. Frappe runs each insert in its own
	# autocommit-ish flush, so if the Encounter fails after the Appointment
	# lands, we'd orphan the appointment. Roll back explicitly on error.
	try:
		appt = frappe.get_doc({
			"doctype": "Patient Appointment",
			"patient": patient,
			"practitioner": practitioner,
			"appointment_date": encounter_date,
			"appointment_time": encounter_time,
			"appointment_type": appointment_type,
			"status": "Open",
			"company": company,
			"custom_practice": practice,
		})
		appt.flags.ignore_permissions = True
		appt.insert(ignore_permissions=True)

		enc_fields = {
			"doctype": "Patient Encounter",
			"patient": patient,
			"practitioner": practitioner,
			"encounter_date": encounter_date,
			"encounter_time": encounter_time,
			"appointment": appt.name,
			"appointment_type": appointment_type,
			"company": company,
			"custom_practice": practice,
			"custom_chief_complaint": chief_complaint,
			"custom_hopi": payload.get("custom_hopi") or "",
			"custom_subjective": payload.get("custom_subjective") or "",
			"custom_objective": payload.get("custom_objective") or "",
			"custom_assessment_text": payload.get("custom_assessment_text") or "",
			"custom_assessment_code": payload.get("custom_assessment_code") or "",
			"custom_plan": payload.get("custom_plan") or "",
		}
		if isinstance(payload.get("custom_examination_findings"), list):
			enc_fields["custom_examination_findings"] = payload["custom_examination_findings"]
		if isinstance(payload.get("custom_encounter_orders"), list):
			enc_fields["custom_encounter_orders"] = payload["custom_encounter_orders"]
		enc = frappe.get_doc(enc_fields)
		enc.flags.ignore_permissions = True
		enc.insert(ignore_permissions=True)

		# Healthcare's PatientEncounter.on_update fires on every save (including
		# insert) and unconditionally sets the linked appointment to "Closed".
		# That is wrong for a draft encounter: the appointment is still active.
		# Override the status to reflect the actual appointment date:
		#   - today or past  → "Checked In"  (doctor is actively seeing the patient)
		#   - future         → "Scheduled"   (pre-created encounter for upcoming visit)
		correct_appt_status = (
			"Checked In" if getdate(encounter_date) <= getdate() else "Scheduled"
		)
		frappe.db.set_value("Patient Appointment", appt.name, "status", correct_appt_status)

		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		raise

	return {"appointment": appt.name, "encounter": enc.name}


@frappe.whitelist()
def list_appointment_types() -> list:
	"""Return all Appointment Type names for the new-visit drawer.

	Appointment Type is global reference data (no tenancy). The REST
	/api/resource/Appointment Type call was returning an empty list for
	some practice-doctor sessions even though they had read permission;
	this endpoint bypasses that ambiguity by talking to the DB directly.
	Auth is enforced by the caller's session — no allow_guest.
	"""
	rows = frappe.get_all(
		"Appointment Type",
		fields=["name"],
		order_by="name asc",
		limit_page_length=200,
		ignore_permissions=True,
	)
	return [r["name"] for r in rows]


@frappe.whitelist()
def start_consultation_from_appointment(appointment: str) -> dict:
	"""Create a Patient Encounter from an existing Patient Appointment.

	Called when the doctor clicks 'Start' on a pre-booked appointment in the
	Appointments screen.  Sets the appointment status to 'Checked In'.

	If an encounter already exists (race-condition or double-click), returns it
	directly with ``existing: true`` so the SPA can open it without re-creating.
	Returns ``{encounter: <name>, existing: <bool>}``.
	"""
	practice = get_active_practice()

	appt = frappe.get_doc("Patient Appointment", appointment)
	if appt.get("custom_practice") != practice:
		raise frappe.PermissionError("Appointment does not belong to your practice.")

	existing = frappe.db.get_value("Patient Encounter", {"appointment": appointment}, "name")
	if existing:
		return {"encounter": existing, "existing": True}

	company = frappe.db.get_value("Practice", practice, "company")
	if not company:
		frappe.throw(
			_("Your practice has no linked ERPNext Company."),
			frappe.ValidationError,
		)

	try:
		enc = frappe.get_doc({
			"doctype": "Patient Encounter",
			"patient": appt.patient,
			"practitioner": appt.practitioner,
			"encounter_date": appt.appointment_date,
			"encounter_time": str(appt.appointment_time or "09:00:00"),
			"appointment": appointment,
			"appointment_type": appt.appointment_type,
			"company": company,
			"custom_practice": practice,
		})
		enc.flags.ignore_permissions = True
		enc.insert(ignore_permissions=True)

		frappe.db.set_value("Patient Appointment", appointment, "status", "Checked In")
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		raise

	return {"encounter": enc.name, "existing": False}


@frappe.whitelist()
def search_icd10(query: str = "", limit: int = 25) -> list:
	"""Search ICD-10-ZA codes by code prefix or display substring.

	No tenancy — Code Values are platform-wide reference data. The endpoint
	is whitelisted for any authenticated practice user; auth is enforced by
	the caller's session (no allow_guest).
	"""
	from medic_plus.api.perf import track_call
	track_call("search_icd10")
	return _search_code_values(system="ICD-10-ZA", query=query, limit=limit)


@frappe.whitelist()
def search_nappi(query: str = "", limit: int = 25) -> list:
	"""Search NAPPI (SA pharmaceutical product) codes."""
	from medic_plus.api.perf import track_call
	track_call("search_nappi")
	return _search_code_values(system="NAPPI", query=query, limit=limit)


@frappe.whitelist()
def search_loinc(query: str = "", limit: int = 25) -> list:
	"""Search LOINC (lab observation) codes."""
	from medic_plus.api.perf import track_call
	track_call("search_loinc")
	return _search_code_values(system="LOINC", query=query, limit=limit)


@frappe.whitelist()
def search_atc(query: str = "", limit: int = 25) -> list:
	"""Search ATC (drug class) codes — used for drug-class allergy matching."""
	from medic_plus.api.perf import track_call
	track_call("search_atc")
	return _search_code_values(system="ATC", query=query, limit=limit)


@frappe.whitelist()
def search_ucum(query: str = "", limit: int = 25) -> list:
	"""Search UCUM unit codes — used by FHIR Quantity datatypes."""
	from medic_plus.api.perf import track_call
	track_call("search_ucum")
	return _search_code_values(system="UCUM", query=query, limit=limit)


@frappe.whitelist()
def search_snomed(query: str = "", limit: int = 25) -> list:
	"""Search SNOMED-CT-ZA-stub.

	The full SNOMED CT-ZA catalogue is gated on IHTSDO Affiliate licence
	procurement (Phase 5.6 / issue #38) — this endpoint queries the small
	placeholder seed for development.
	"""
	from medic_plus.api.perf import track_call
	track_call("search_snomed")
	return _search_code_values(system="SNOMED-CT-ZA-stub", query=query, limit=limit)


@frappe.whitelist()
def get_patient_medical_aid(patient: str) -> list:
    """Return active Patient Insurance Policy rows + SA medical-aid extension."""
    _assert_patient_in_active_practice(patient)
    rows = frappe.get_all(
        "Patient Insurance Policy",
        filters={"patient": patient, "docstatus": ["<", 2]},
        fields=[
            "name", "insurance_payor", "insurance_plan", "policy_number",
            "policy_expiry_date", "custom_sa_scheme", "custom_principal_member_id",
            "custom_dependent_code", "custom_authorisation_reference",
        ],
        order_by="policy_expiry_date desc",
        limit=20,
    )
    return [
        {**r, "policy_expiry_date": str(r["policy_expiry_date"] or "")}
        for r in rows
    ]


@frappe.whitelist()
def get_encounter_detail(encounter: str) -> dict:
	"""Return a POPIA-safe composite payload for a single Patient Encounter.

	Cross-tenant guard: the encounter must belong to the caller's active
	Practice.  PermissionError is raised for cross-practice requests so
	the response cannot be used to probe Practice membership.

	Payload shape:
	  {
	    encounter: { ...SOAP fields, examination_findings: [...], orders: [...] },
	    problem_list: [ ...Patient Problem List rows for this patient ],
	  }
	"""
	practice = get_active_practice()
	enc_practice = frappe.db.get_value("Patient Encounter", encounter, "custom_practice")
	if enc_practice != practice:
		raise frappe.PermissionError("Encounter does not belong to your practice.")

	enc_doc = frappe.get_doc("Patient Encounter", encounter)

	enc_payload = {
		"name": enc_doc.name,
		"patient": enc_doc.patient,
		"encounter_date": str(enc_doc.encounter_date or ""),
		"chief_complaint": enc_doc.get("custom_chief_complaint") or "",
		"hopi": enc_doc.get("custom_hopi") or "",
		"subjective": enc_doc.get("custom_subjective") or "",
		"objective": enc_doc.get("custom_objective") or "",
		"assessment_text": enc_doc.get("custom_assessment_text") or "",
		"assessment_code": enc_doc.get("custom_assessment_code") or "",
		"plan": enc_doc.get("custom_plan") or "",
		"examination_findings": [
			{
				"body_system": row.body_system,
				"body_part": row.body_part,
				"finding": row.finding,
				"is_abnormal": bool(row.is_abnormal),
			}
			for row in (enc_doc.get("custom_examination_findings") or [])
		],
		"orders": [
			{
				"order_type": row.order_type,
				"order_name": row.order_name,
				"status": row.status,
				"notes": row.notes or "",
			}
			for row in (enc_doc.get("custom_encounter_orders") or [])
		],
	}

	problem_list = frappe.get_all(
		"Patient Problem List",
		filters={"patient": enc_doc.patient, "custom_practice": practice},
		fields=["name", "icd10_code", "description", "status", "onset_date", "severity"],
		order_by="onset_date desc",
		limit=50,
	)

	return {"encounter": enc_payload, "problem_list": problem_list}


@frappe.whitelist()
def get_patient_detail(patient: str) -> dict:
    """Return the composite payload for a Patient detail screen.

    Cross-tenant guard: the requested Patient must belong to the caller's
    active Practice. Cross-Practice requests raise PermissionError so the
    response cannot be used to probe Practice membership of arbitrary IDs.
    """
    practice = get_active_practice()
    patient_practice = frappe.db.get_value("Patient", patient, "custom_practice")
    if patient_practice != practice:
        raise frappe.PermissionError("Patient does not belong to your practice.")
    return build_patient_summary(patient_name=patient, practice=practice)


@frappe.whitelist()
def check_prescription_safety(patient: str, nappi_code_values: str = "[]") -> list:
    """Return aggregated safety warnings for the given NAPPI Code Values / patient.

    Called by the SPA prescription panel on every NAPPI selection change.
    ``nappi_code_values`` is a JSON-encoded list of Code Value names (e.g.
    ["719318-NAPPI", "719390-NAPPI"]).  Returns a list of warning dicts
    (see api/drug_safety.py for the shape).

    Cross-tenant guard: patient must belong to the caller's active practice.
    """
    import json as _json
    from medic_plus.api.drug_safety import (
        check_drug_allergy,
        check_drug_interaction,
        check_schedule_rule,
        _get_drug_master,
    )

    practice = get_active_practice()
    patient_practice = frappe.db.get_value("Patient", patient, "custom_practice")
    if patient_practice != practice:
        raise frappe.PermissionError("Patient does not belong to your practice.")

    cvs = _json.loads(nappi_code_values) if isinstance(nappi_code_values, str) else nappi_code_values

    all_warnings: list[dict] = []
    for nappi_cv in cvs:
        dm = _get_drug_master(nappi_cv)
        if not dm:
            continue
        drug_name = dm.get("drug_name") or nappi_cv
        atc_code = dm.get("atc_code")
        all_warnings.extend(check_drug_allergy(patient, atc_code, drug_name))
        all_warnings.extend(check_schedule_rule(nappi_cv, prescriber=None))

    all_warnings.extend(check_drug_interaction(cvs))
    return all_warnings


@frappe.whitelist()
def get_drug_master_by_nappi(nappi_code_value: str) -> dict | None:
    """Return Drug Master fields for the given NAPPI Code Value name.

    Used by the SPA prescription panel to auto-fill schedule, strength,
    and dosage form after NAPPI selection.
    """
    if not nappi_code_value:
        return None
    return frappe.db.get_value(
        "Drug Master",
        {"nappi_code_value": nappi_code_value},
        ["name", "drug_name", "nappi_code", "atc_code", "schedule", "strength", "dosage_form"],
        as_dict=True,
    )


# ── Billing & Claims ──────────────────────────────────────────────────────────

_INVOICE_PAGE_DEFAULT = 50
_INVOICE_PAGE_MAX = 200
_INVOICE_STATUS_OPTIONS = ["Draft", "Submitted", "Unpaid", "Overdue", "Paid", "Return", "Credit Note Issued"]


@frappe.whitelist()
def get_invoices(filters=None, limit_start=0, limit_page_length=None) -> dict:
	"""Return Sales Invoices for the active Practice, paginated.

	Scoped by Practice.company — the same field used by the Sales Invoice PQC.
	Only non-cancelled (docstatus != 2) invoices are returned.

	Filters (dict or JSON string):
	  ``status``      — str or list of statuses
	  ``date_from``   — YYYY-MM-DD
	  ``date_to``     — YYYY-MM-DD
	  ``patient``     — single Patient name

	Returns:
	  {rows, total, limit_start, limit_page_length,
	   summary: {total_invoiced, total_paid, total_outstanding}}
	"""
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except Exception:
			filters = {}
	filters = filters or {}

	try:
		limit_start = int(limit_start or 0)
	except (TypeError, ValueError):
		limit_start = 0
	try:
		limit_page_length = int(limit_page_length or _INVOICE_PAGE_DEFAULT)
	except (TypeError, ValueError):
		limit_page_length = _INVOICE_PAGE_DEFAULT
	limit_page_length = max(1, min(limit_page_length, _INVOICE_PAGE_MAX))

	practice = get_active_practice()
	company = frappe.db.get_value("Practice", practice, "company")
	if not company:
		return {"rows": [], "total": 0, "limit_start": limit_start,
				"limit_page_length": limit_page_length,
				"summary": {"total_invoiced": 0, "total_paid": 0, "total_outstanding": 0}}

	today = date.today()
	date_from = filters.get("date_from") or str(today.replace(month=1, day=1))
	date_to = filters.get("date_to") or str(today)

	inv_filters = {
		"company": company,
		"docstatus": ["!=", 2],
		"posting_date": ["between", [date_from, date_to]],
	}

	status_filter = filters.get("status")
	if status_filter:
		if isinstance(status_filter, str):
			status_filter = [status_filter]
		inv_filters["status"] = ["in", status_filter]

	patient_filter = filters.get("patient")
	if patient_filter:
		inv_filters["patient"] = patient_filter

	total = frappe.db.count("Sales Invoice", filters=inv_filters)

	rows = frappe.get_all(
		"Sales Invoice",
		filters=inv_filters,
		fields=[
			"name", "patient", "patient_name", "posting_date",
			"grand_total", "outstanding_amount", "status",
			"currency", "due_date",
		],
		order_by="posting_date desc, name desc",
		limit_start=limit_start,
		limit_page_length=limit_page_length,
	)

	# Batch-lookup appointments that reference these invoices.
	appt_by_inv: dict = {}
	if rows:
		inv_names = [r["name"] for r in rows]
		appts = frappe.get_all(
			"Patient Appointment",
			filters={"ref_sales_invoice": ["in", inv_names]},
			fields=["name", "ref_sales_invoice", "appointment_date", "appointment_type"],
			limit=len(inv_names) * 2,
		)
		appt_by_inv = {a["ref_sales_invoice"]: a for a in appts}

	# Summary totals over the full filtered set (not just this page).
	summary_rows = frappe.db.sql(
		"""SELECT SUM(grand_total) AS total_invoiced,
		          SUM(grand_total - outstanding_amount) AS total_paid,
		          SUM(outstanding_amount) AS total_outstanding
		   FROM `tabSales Invoice`
		   WHERE company = %(company)s
		     AND docstatus != 2
		     AND posting_date BETWEEN %(date_from)s AND %(date_to)s
		""",
		{"company": company, "date_from": date_from, "date_to": date_to},
		as_dict=True,
	)
	s = summary_rows[0] if summary_rows else {}

	formatted = [
		{
			"name": r["name"],
			"patient": r.get("patient"),
			"patient_name": r.get("patient_name"),
			"posting_date": str(r.get("posting_date") or ""),
			"due_date": str(r.get("due_date") or ""),
			"grand_total": float(r.get("grand_total") or 0),
			"outstanding_amount": float(r.get("outstanding_amount") or 0),
			"paid_amount": float(r.get("grand_total") or 0) - float(r.get("outstanding_amount") or 0),
			"status": r.get("status"),
			"currency": r.get("currency") or "ZAR",
			"appointment": appt_by_inv.get(r["name"], {}).get("name"),
			"appointment_date": str(appt_by_inv.get(r["name"], {}).get("appointment_date") or ""),
			"appointment_type": appt_by_inv.get(r["name"], {}).get("appointment_type"),
		}
		for r in rows
	]

	return {
		"rows": formatted,
		"total": total,
		"limit_start": limit_start,
		"limit_page_length": limit_page_length,
		"summary": {
			"total_invoiced": float(s.get("total_invoiced") or 0),
			"total_paid": float(s.get("total_paid") or 0),
			"total_outstanding": float(s.get("total_outstanding") or 0),
		},
	}
