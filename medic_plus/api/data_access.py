"""
Patient data masking and two-sided OTP consent API.

Sensitive fields (SA ID, medical aid membership numbers, phone) are stored
unmasked in the DB.  This module provides:

  - get_masked_value()     → masked display string for the UI
  - request_unmask()       → creates a Data Unmask Request and sends OTPs to
                             both the requesting user AND the patient
  - verify_unmask()        → validates both OTPs; if correct returns the
                             plaintext value and writes a Clinical Access Log
  - expire_stale_requests() → scheduled task; marks expired Pending requests

Two-sided OTP design
--------------------
When a clinician wants to view a protected field:

  1. They click "View" on the masked field — calls request_unmask().
  2. System generates two independent 6-digit OTPs:
       • requester_otp  → sent to the clinician by email/SMS
       • patient_otp    → sent to the patient by email/SMS
  3. Only the *hashes* are stored in Data Unmask Request (SHA-256).
  4. The clinician's UI shows a two-input dialog. The patient reads their OTP
     from their phone/inbox and tells the clinician (in-person) or the patient
     can self-confirm via the patient portal.
  5. verify_unmask() compares both OTPs against their hashes.  Both must match
     and the request must not have expired (10-minute window).
  6. On success the plaintext value is returned *once* for the current HTTP
     response and a Clinical Access Log entry is written.  The value is never
     cached server-side after verification.

Staging note
------------
On staging, mute_emails=1 silences actual delivery.  request_unmask() returns
the OTPs in plaintext in the response *only when frappe.conf.developer_mode is
truthy*, so QA can test the flow without an SMS gateway.
"""

import hashlib
import random
import string

import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date


# ── Configuration ─────────────────────────────────────────────────────────────

#: Fields that require OTP consent to view unmasked.
PROTECTED_FIELDS: dict[str, list[str]] = {
    "Patient": [
        "custom_sa_id_number",
        "mobile",
    ],
    "Patient Insurance Policy": [
        "custom_membership_number",
        "custom_dependant_code",
    ],
}

#: How many minutes a Data Unmask Request stays valid.
OTP_EXPIRY_MINUTES = 10


# ── Internal helpers ───────────────────────────────────────────────────────────

def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def _mask(value: str | None, field: str) -> str:
    """Return a masked display version of *value* appropriate for *field*."""
    if not value:
        return "—"
    if field == "custom_sa_id_number":
        # Show only last 4 digits: *** *** 1234
        return f"*** *** {value[-4:]}" if len(value) >= 4 else "***"
    if field in ("mobile", "phone"):
        # Show only last 3 digits: +27 ** *** 567
        return f"+27 ** *** {value[-3:]}" if len(value) >= 3 else "***"
    if field in ("custom_membership_number",):
        return f"{'*' * max(0, len(value) - 3)}{value[-3:]}" if len(value) >= 3 else "***"
    # Generic: show first char + asterisks
    return value[0] + "*" * (len(value) - 1) if value else "—"


def _resolve_patient_contact(patient_name: str) -> tuple[str | None, str | None]:
    """Return (email, mobile) for the patient record."""
    row = frappe.db.get_value(
        "Patient", patient_name, ["email", "mobile"], as_dict=True
    )
    if not row:
        return None, None
    return row.get("email"), row.get("mobile")


def _send_otp(recipient_email: str | None, recipient_mobile: str | None, otp: str, role: str):
    """Send OTP via email (and SMS if configured). Silently drops on staging."""
    subject = _("Data Access Verification — Medic Plus")
    message = _(
        "Your one-time verification code is: <strong>{0}</strong><br><br>"
        "This code expires in {1} minutes. Do not share it."
    ).format(otp, OTP_EXPIRY_MINUTES)

    if recipient_email:
        frappe.sendmail(
            recipients=[recipient_email],
            subject=subject,
            message=message,
            now=True,
        )


def _log_access(
    *,
    accessed_by: str,
    practice: str,
    access_type: str,
    target_doctype: str,
    target_docname: str,
    target_field: str,
    patient: str,
    unmask_request: str | None = None,
):
    """Insert a Clinical Access Log entry (append-only)."""
    log = frappe.get_doc(
        {
            "doctype": "Clinical Access Log",
            "accessed_by": accessed_by,
            "practice": practice,
            "access_type": access_type,
            "timestamp": now_datetime(),
            "target_doctype": target_doctype,
            "target_docname": target_docname,
            "target_field": target_field,
            "patient": patient,
            "unmask_request": unmask_request,
        }
    )
    log.flags.ignore_permissions = True
    log.insert()
    frappe.db.commit()


def _get_practice_for_user(user: str) -> str | None:
    return frappe.db.get_value(
        "Practice Member", {"user": user}, "practice"
    )


def _resolve_patient_from_doc(doctype: str, docname: str) -> str | None:
    """Return the patient name linked to the target document."""
    if doctype == "Patient":
        return docname
    patient_field = "patient"
    return frappe.db.get_value(doctype, docname, patient_field)


# ── Public whitelisted API ─────────────────────────────────────────────────────

@frappe.whitelist()
def get_masked_value(doctype: str, docname: str, field: str) -> dict:
    """
    Return the masked display string for a protected field.

    Requires the caller to have read permission on the document.
    """
    frappe.has_permission(doctype, doc=docname, throw=True)

    if field not in PROTECTED_FIELDS.get(doctype, []):
        frappe.throw(_("Field '{0}' on {1} is not a protected field.").format(field, doctype))

    value = frappe.db.get_value(doctype, docname, field)
    return {"masked": _mask(value, field)}


@frappe.whitelist()
def request_unmask(doctype: str, docname: str, field: str) -> dict:
    """
    Initiate a two-sided OTP unmask flow.

    Creates a Data Unmask Request, generates two OTPs, and dispatches them:
      • requester OTP  → current session user (email)
      • patient OTP    → the patient linked to the document (email/SMS)

    Returns the request name (and, in developer_mode, both OTPs in plaintext
    for staging QA).
    """
    frappe.has_permission(doctype, doc=docname, throw=True)

    if field not in PROTECTED_FIELDS.get(doctype, []):
        frappe.throw(_("Field '{0}' on {1} is not a protected field.").format(field, doctype))

    user = frappe.session.user
    practice = _get_practice_for_user(user)
    patient = _resolve_patient_from_doc(doctype, docname)

    if not patient:
        frappe.throw(_("Cannot determine patient for this document."))

    if not practice:
        # Healthcare Administrators may not be practice members
        if "Healthcare Administrator" not in frappe.get_roles(user):
            frappe.throw(_("You are not associated with a Practice."))
        # For admins, use the practice field on the patient
        practice = frappe.db.get_value("Patient", patient, "custom_practice") or ""

    # Expire any existing pending requests for the same field/user
    frappe.db.set_value(
        "Data Unmask Request",
        {
            "requested_by": user,
            "target_doctype": doctype,
            "target_docname": docname,
            "target_field": field,
            "status": "Pending",
        },
        "status",
        "Expired",
    )
    frappe.db.commit()

    # Generate OTPs
    requester_otp = _generate_otp()
    patient_otp = _generate_otp()
    expires_at = add_to_date(now_datetime(), minutes=OTP_EXPIRY_MINUTES)

    # Persist hashes only
    req = frappe.get_doc(
        {
            "doctype": "Data Unmask Request",
            "patient": patient,
            "practice": practice,
            "requested_by": user,
            "status": "Pending",
            "target_doctype": doctype,
            "target_docname": docname,
            "target_field": field,
            "requester_otp_hash": _hash_otp(requester_otp),
            "patient_otp_hash": _hash_otp(patient_otp),
            "expires_at": expires_at,
        }
    )
    req.flags.ignore_permissions = True
    req.insert()
    frappe.db.commit()

    # Dispatch OTPs
    requester_email = frappe.db.get_value("User", user, "email")
    patient_email, patient_mobile = _resolve_patient_contact(patient)

    _send_otp(requester_email, None, requester_otp, "requester")
    _send_otp(patient_email, patient_mobile, patient_otp, "patient")

    response: dict = {"request": req.name}

    # Expose plaintext OTPs on developer_mode for staging QA only
    if frappe.conf.get("developer_mode"):
        response["_dev_requester_otp"] = requester_otp
        response["_dev_patient_otp"] = patient_otp

    return response


@frappe.whitelist()
def verify_unmask(request_name: str, requester_otp: str, patient_otp: str) -> dict:
    """
    Validate both OTPs and, if correct, return the unmasked field value once.

    Writes a Clinical Access Log entry on success.  The value is *not* cached;
    subsequent calls require a new request_unmask() flow.
    """
    req = _get_unmask_request(request_name)

    if req.requested_by != frappe.session.user:
        frappe.throw(_("This unmask request does not belong to you."), frappe.PermissionError)

    if req.status != "Pending":
        frappe.throw(_("This request is no longer active (status: {0}).").format(req.status))

    # Use stdlib fromisoformat so tests don't need a live Redis/System Settings
    import datetime as _dt
    expires = _dt.datetime.fromisoformat(str(req.expires_at))
    if now_datetime() > expires:
        frappe.db.set_value("Data Unmask Request", request_name, "status", "Expired")
        frappe.db.commit()
        frappe.throw(_("This unmask request has expired. Please start a new request."))

    if _hash_otp(requester_otp) != req.requester_otp_hash:
        frappe.throw(_("Your verification code is incorrect."))

    if _hash_otp(patient_otp) != req.patient_otp_hash:
        frappe.throw(_("Patient verification code is incorrect."))

    # Both OTPs valid — fetch plaintext value
    frappe.has_permission(req.target_doctype, doc=req.target_docname, throw=True)
    value = frappe.db.get_value(req.target_doctype, req.target_docname, req.target_field)

    # Mark request verified
    frappe.db.set_value(
        "Data Unmask Request",
        request_name,
        {"status": "Verified", "verified_at": now_datetime()},
    )
    frappe.db.commit()

    # Audit log
    _log_access(
        accessed_by=frappe.session.user,
        practice=req.practice,
        access_type="Unmask",
        target_doctype=req.target_doctype,
        target_docname=req.target_docname,
        target_field=req.target_field,
        patient=req.patient,
        unmask_request=request_name,
    )

    return {"value": value}


@frappe.whitelist()
def deny_unmask(request_name: str) -> dict:
    """
    Allow the patient (or admin) to explicitly deny a pending unmask request.
    Called from the patient portal or by the patient directly.
    """
    req = frappe.get_doc("Data Unmask Request", request_name)
    user = frappe.session.user

    # Only the patient or an admin can deny
    is_patient = frappe.db.get_value("Patient", req.patient, "email") == user
    is_admin = "Healthcare Administrator" in frappe.get_roles(user)

    if not (is_patient or is_admin):
        frappe.throw(_("You are not authorised to deny this request."), frappe.PermissionError)

    if req.status != "Pending":
        frappe.throw(_("Request is not pending."))

    frappe.db.set_value("Data Unmask Request", request_name, "status", "Denied")
    frappe.db.commit()

    _log_access(
        accessed_by=user,
        practice=req.practice,
        access_type="View",
        target_doctype=req.target_doctype,
        target_docname=req.target_docname,
        target_field=req.target_field,
        patient=req.patient,
        unmask_request=request_name,
    )

    return {"status": "Denied"}


def _get_unmask_request(name: str):
    """Thin wrapper so tests can mock request lookup without patching frappe.get_doc."""
    return frappe.get_doc("Data Unmask Request", name)


def expire_stale_requests():
    """
    Scheduled task (runs every 15 minutes) to expire timed-out requests.
    Registered in hooks.py under scheduler_events.
    """
    frappe.db.sql(
        """
        UPDATE `tabData Unmask Request`
           SET status = 'Expired'
         WHERE status = 'Pending'
           AND expires_at < NOW()
        """
    )
    frappe.db.commit()
