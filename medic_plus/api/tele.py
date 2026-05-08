"""
medic_plus.api.tele — Telemedicine room management.

Supports Jitsi Meet (self-hosted) and LiveKit Cloud. Provider is configured
via Medic Plus Settings.video_provider ("jitsi" | "livekit").

Patient join URL uses a one-time token stored in Frappe cache (TTL = 2 hours).
The token is bound to the appointment so it cannot be reused for a different room.
"""

import frappe
from frappe.utils import now_datetime, today, getdate


# ── Room provisioning ─────────────────────────────────────────────────────────

def _provision_jitsi_room(room_id: str, base_url: str) -> dict:
    """Create a Jitsi room entry (rooms are pre-shared by URL in Jitsi Meet)."""
    practitioner_url = f"{base_url}/{room_id}"
    return {
        "room_id": room_id,
        "practitioner_url": practitioner_url,
    }


def _provision_livekit_room(room_id: str, api_key: str, api_secret: str, base_url: str) -> dict:
    """Create a LiveKit room via the LiveKit Server SDK."""
    try:
        from livekit import api as lk_api  # type: ignore
        lk = lk_api.LiveKitAPI(base_url, api_key, api_secret)
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            lk.room.create_room(lk_api.CreateRoomRequest(name=room_id))
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "LiveKit room creation failed")

    return {
        "room_id": room_id,
        "practitioner_url": f"{base_url}/join/{room_id}",
    }


@frappe.whitelist()
def create_room(appointment: str, practice: str, patient: str) -> dict:
    """
    Provision a video consultation room for the appointment.

    Writes video_room_id, video_join_url, and patient_join_url back to the
    Patient Appointment record. Returns the same fields plus a one-time token.
    """
    provider = frappe.db.get_single_value("Medic Plus Settings", "video_provider") or "jitsi"
    base_url = frappe.db.get_single_value("Medic Plus Settings", "video_base_url") or "https://meet.jit.si"

    room_id = f"medic-{frappe.generate_hash(appointment, 10).upper()}"

    if provider == "livekit":
        api_key = frappe.db.get_single_value("Medic Plus Settings", "livekit_api_key") or ""
        api_secret = frappe.db.get_single_value("Medic Plus Settings", "livekit_api_secret") or ""
        room_data = _provision_livekit_room(room_id, api_key, api_secret, base_url)
    else:
        room_data = _provision_jitsi_room(room_id, base_url)

    # Generate a one-time patient token (2-hour TTL)
    patient_token = frappe.generate_hash(f"{appointment}:{patient}", 24)
    cache_key = f"tele_patient_token:{patient_token}"
    frappe.cache.set_value(cache_key, appointment, expires_in_sec=7200)

    site_url = frappe.utils.get_url()
    patient_join_url = f"{site_url}/teleconsult/{room_id}?token={patient_token}&role=patient"
    practitioner_url = room_data["practitioner_url"]

    # Stamp the appointment
    frappe.db.set_value("Patient Appointment", appointment, {
        "video_room_id": room_id,
        "video_join_url": practitioner_url,
        "patient_join_url": patient_join_url,
    })

    return {
        "room_id": room_id,
        "practitioner_url": practitioner_url,
        "patient_join_url": patient_join_url,
        "patient_token": patient_token,
    }


# ── Consent helpers ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_tele_consent_status(patient: str, practice: str) -> dict:
    """
    Return telemedicine consent status for a patient:
    - "active"   — valid, non-expired, non-revoked consent exists
    - "expired"  — consent exists but past expiry_date
    - "revoked"  — consent exists but was revoked
    - "required" — no consent record found
    """
    record = frappe.db.get_value(
        "Telemedicine Consent",
        {"patient": patient, "practice": practice},
        ["name", "expiry_date", "revoked"],
        as_dict=True,
        order_by="creation desc",
    )

    if not record:
        return {"status": "required"}

    if record.get("revoked"):
        return {"status": "revoked", "consent": record["name"]}

    expiry = record.get("expiry_date")
    if expiry and getdate(expiry) < getdate(today()):
        return {"status": "expired", "consent": record["name"]}

    return {"status": "active", "consent": record["name"]}


@frappe.whitelist()
def record_tele_consent(patient: str, practice: str) -> dict:
    """Create a new Telemedicine Consent record for the patient."""
    doc = frappe.new_doc("Telemedicine Consent")
    doc.patient = patient
    doc.practice = practice
    doc.consent_date = today()
    doc.hpcsa_booklet_10_acknowledged = 1
    doc.insert(ignore_permissions=False)
    return {"consent": doc.name, "expiry_date": doc.expiry_date}


@frappe.whitelist()
def validate_patient_token(token: str, room_id: str) -> dict:
    """
    Validate a one-time patient join token.

    Returns {"valid": True, "appointment": <name>} or {"valid": False}.
    Token is NOT consumed here — patient must be authenticated to the waiting
    room before the token is cleared.
    """
    cache_key = f"tele_patient_token:{token}"
    appointment = frappe.cache.get_value(cache_key)
    if not appointment:
        return {"valid": False}

    expected_room = frappe.db.get_value("Patient Appointment", appointment, "video_room_id")
    if expected_room != room_id:
        return {"valid": False}

    return {"valid": True, "appointment": appointment}
