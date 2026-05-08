"""
Context controller for /teleconsult/<room_id>.

Serves the teleconsult page for both practitioner and patient views.
- Practitioner: full encounter editor side-panel + video
- Patient: waiting room then video

URL patterns handled by Frappe's www router:
  /teleconsult/<room_id>?role=patient&token=<token>
  /teleconsult/<room_id>   (practitioner — must be authenticated practice member)
"""

import frappe


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)

    room_id = frappe.local.request.path.rstrip("/").split("/")[-1]
    role = frappe.form_dict.get("role", "practitioner")
    token = frappe.form_dict.get("token", "")

    context.room_id = room_id
    context.role = role
    context.token = token
    context.no_cache = 1

    if role == "patient":
        # Validate one-time token
        validation = _validate_patient_token(token, room_id)
        context.token_valid = validation.get("valid", False)
        context.appointment = validation.get("appointment", "")
    else:
        # Practitioner — verify practice membership and load appointment
        appointment = frappe.db.get_value(
            "Patient Appointment",
            {"video_room_id": room_id},
            ["name", "patient", "custom_practice", "custom_consultation_type"],
            as_dict=True,
        )
        context.appointment = appointment or {}
        context.token_valid = True  # practitioner auth is via Frappe session

    # Video provider config for the frontend
    context.video_provider = (
        frappe.db.get_single_value("Medic Plus Settings", "video_provider") or "jitsi"
    )
    context.video_base_url = (
        frappe.db.get_single_value("Medic Plus Settings", "video_base_url")
        or "https://meet.jit.si"
    )


def _validate_patient_token(token: str, room_id: str) -> dict:
    if not token:
        return {"valid": False}
    try:
        from medic_plus.api.tele import validate_patient_token
        return validate_patient_token(token=token, room_id=room_id)
    except Exception:
        return {"valid": False}
