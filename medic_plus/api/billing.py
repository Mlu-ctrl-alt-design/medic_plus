"""Subscription billing for medic_plus.

Self-contained plan enforcement without portal_shell dependency.
Plans are defined in code; the Practice document stores the chosen tier
and subscription_status.

Paystack is used for payment processing via /api/method/...paystack_webhook.
"""

import functools
import hashlib
import hmac
import json

import frappe
from frappe.utils import add_months, today


# ---------------------------------------------------------------------------
# Plan catalogue
# ---------------------------------------------------------------------------

MEDIC_PLANS: dict[str, dict] = {
    "Free": {
        "label": "Free / Trial",
        "price_monthly": 0,
        "price_label": "Free",
        "is_trial": True,
        "features": {
            "appointments": True,
            "patient_records": True,
            "sick_notes": True,
            "prescriptions": True,
            "dispensing": True,
            "inpatient_module": False,
            "sms_reminders": False,
            "medical_aid": False,
            "advanced_reports": False,
            "api_access": False,
        },
        "limits": {
            "Patient": 30,       # max patients  (0 = unlimited)
            "users": 2,          # max Practice Members
        },
        "highlight": [],
    },
    "Basic": {
        "label": "Basic",
        "price_monthly": 499,
        "price_label": "R 499 / month",
        "is_trial": False,
        "features": {
            "appointments": True,
            "patient_records": True,
            "sick_notes": True,
            "prescriptions": True,
            "dispensing": True,
            "inpatient_module": False,
            "sms_reminders": False,
            "medical_aid": False,
            "advanced_reports": False,
            "api_access": False,
        },
        "limits": {
            "Patient": 100,
            "users": 3,
        },
        "highlight": ["Up to 100 patients", "Up to 3 staff users"],
    },
    "Pro": {
        "label": "Pro",
        "price_monthly": 999,
        "price_label": "R 999 / month",
        "is_trial": False,
        "features": {
            "appointments": True,
            "patient_records": True,
            "sick_notes": True,
            "prescriptions": True,
            "dispensing": True,
            "inpatient_module": True,
            "sms_reminders": True,
            "medical_aid": True,
            "advanced_reports": True,
            "api_access": False,
        },
        "limits": {
            "Patient": 0,        # unlimited
            "users": 0,          # unlimited
        },
        "highlight": [
            "Unlimited patients",
            "Inpatient module",
            "SMS reminders",
            "Medical aid integration",
            "Advanced reports",
        ],
        "is_popular": True,
    },
}

_PLAN_ORDER = ["Free", "Basic", "Pro"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_practice() -> str | None:
    from medic_plus.api.permissions import _get_user_practice as _perm_practice
    return _perm_practice()


def _is_platform_admin() -> bool:
    from medic_plus.api.permissions import _is_platform_admin as _perm_admin
    return _perm_admin()


def get_practice_plan(practice: str = None) -> str:
    """Return the subscription plan key for the given (or current user's) practice."""
    practice = practice or _get_user_practice()
    if not practice:
        return "Free"
    plan = frappe.db.get_value("Practice", practice, "subscription_plan")
    return plan if plan in MEDIC_PLANS else "Free"


def get_practice_status(practice: str = None) -> str:
    """Return subscription_status: Trialing | Active | Past Due | Cancelled."""
    practice = practice or _get_user_practice()
    if not practice:
        return "Trialing"
    return frappe.db.get_value("Practice", practice, "subscription_status") or "Trialing"


def is_plan_active(practice: str = None) -> bool:
    status = get_practice_status(practice)
    return status in ("Active", "Trialing")


def has_feature(feature_key: str, practice: str = None) -> bool:
    if _is_platform_admin():
        return True
    plan_key = get_practice_plan(practice)
    plan = MEDIC_PLANS.get(plan_key, MEDIC_PLANS["Free"])
    return bool(plan["features"].get(feature_key, False))


def is_within_limit(identifier: str, practice: str = None) -> bool:
    """Return True if the practice has not yet hit its plan limit for `identifier`.

    identifier = DocType name (e.g. "Patient") or limit_key (e.g. "users").
    0 limit = unlimited.
    """
    if _is_platform_admin():
        return True
    practice = practice or _get_user_practice()
    if not practice:
        return False

    plan_key = get_practice_plan(practice)
    plan = MEDIC_PLANS.get(plan_key, MEDIC_PLANS["Free"])
    limit = plan["limits"].get(identifier, 0)

    if limit == 0:
        return True

    current = _count_usage(identifier, practice)
    return current < limit


def _count_usage(identifier: str, practice: str) -> int:
    """Live count of a resource for the given practice."""
    if identifier == "Patient":
        return frappe.db.count("Patient", {"custom_practice": practice})
    if identifier == "users":
        return frappe.db.count("Practice Member", {"practice": practice})
    return 0


# ---------------------------------------------------------------------------
# Enforcement decorators
# ---------------------------------------------------------------------------

def require_feature(feature_key: str):
    """Decorator: block the endpoint if the practice's plan lacks this feature."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_feature(feature_key):
                plan_key = get_practice_plan()
                idx = _PLAN_ORDER.index(plan_key) if plan_key in _PLAN_ORDER else 0
                needed = _first_plan_with_feature(feature_key)
                frappe.throw(
                    f"The <b>{feature_key.replace('_', ' ').title()}</b> feature is not included in your "
                    f"<b>{MEDIC_PLANS[plan_key]['label']}</b> plan."
                    + (f" Upgrade to <b>{MEDIC_PLANS[needed]['label']}</b> to unlock it." if needed else ""),
                    frappe.PermissionError,
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _first_plan_with_feature(feature_key: str) -> str | None:
    for key in _PLAN_ORDER:
        if MEDIC_PLANS[key]["features"].get(feature_key):
            return key
    return None


def require_limit(identifier: str):
    """Decorator: block the endpoint if the practice is at their limit."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_within_limit(identifier):
                plan_key = get_practice_plan()
                plan = MEDIC_PLANS.get(plan_key, MEDIC_PLANS["Free"])
                limit = plan["limits"].get(identifier, 0)
                label = identifier if identifier != "Patient" else "patients"
                frappe.throw(
                    f"Your <b>{plan['label']}</b> plan limit of <b>{limit} {label}</b> has been reached. "
                    f"Please upgrade your subscription to add more.",
                    frappe.ValidationError,
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Whitelisted API endpoints
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_billing_summary() -> dict:
    """Return current plan status, usage, and available upgrades for a practice."""
    practice = _get_user_practice()
    if not practice and not _is_platform_admin():
        frappe.throw("No practice associated with your account.", frappe.PermissionError)

    plan_key = get_practice_plan(practice)
    plan = MEDIC_PLANS.get(plan_key, MEDIC_PLANS["Free"])
    status = get_practice_status(practice)

    usage = {}
    for identifier, limit in plan["limits"].items():
        current = _count_usage(identifier, practice) if practice else 0
        usage[identifier] = {
            "current": current,
            "limit": limit,
            "pct": round(current / limit * 100) if limit else 0,
            "at_limit": limit > 0 and current >= limit,
        }

    trial_ends_on = None
    if practice:
        trial_ends_on = frappe.db.get_value("Practice", practice, "trial_ends_on")

    return {
        "plan_key": plan_key,
        "plan_label": plan["label"],
        "price_label": plan["price_label"],
        "status": status,
        "trial_ends_on": str(trial_ends_on) if trial_ends_on else None,
        "features": plan["features"],
        "usage": usage,
        "available_plans": _get_available_plans(plan_key),
    }


def _get_available_plans(current_key: str) -> list:
    """Return plans the practice can upgrade to (higher tiers only)."""
    current_idx = _PLAN_ORDER.index(current_key) if current_key in _PLAN_ORDER else 0
    result = []
    for key in _PLAN_ORDER[current_idx + 1:]:
        p = MEDIC_PLANS[key]
        result.append({
            "key": key,
            "label": p["label"],
            "price_monthly": p["price_monthly"],
            "price_label": p["price_label"],
            "highlight": p.get("highlight", []),
            "is_popular": p.get("is_popular", False),
            "features": p["features"],
        })
    return result


@frappe.whitelist()
def get_all_plans() -> list:
    """Return all plans for display on pricing/upgrade page."""
    return [
        {
            "key": key,
            **{k: v for k, v in plan.items() if k not in ("is_trial",)},
        }
        for key, plan in MEDIC_PLANS.items()
    ]


@frappe.whitelist()
def initiate_paystack_checkout(plan_key: str) -> dict:
    """Create a Paystack payment initialisation and return the checkout URL.

    The practice is identified from the session user's practice membership.
    On successful payment, Paystack POSTs to the webhook endpoint which upgrades the plan.
    """
    if plan_key not in MEDIC_PLANS:
        frappe.throw(f"Invalid plan: {plan_key}")

    practice = _get_user_practice()
    if not practice:
        frappe.throw("No practice associated with your account.")

    plan = MEDIC_PLANS[plan_key]
    if plan.get("is_trial"):
        frappe.throw("Cannot checkout a free/trial plan.")

    secret_key = frappe.db.get_single_value("Medic Plus Settings", "paystack_secret_key") if frappe.db.exists("DocType", "Medic Plus Settings") else None
    if not secret_key:
        # Return a placeholder so the UI can show a config message
        return {
            "status": "not_configured",
            "message": "Paystack secret key is not configured. Please contact support.",
        }

    import requests

    practice_doc = frappe.get_doc("Practice", practice)
    email = practice_doc.email or frappe.session.user
    amount_kobo = plan["price_monthly"] * 100  # Paystack uses kobo (ZAR cents)

    callback_url = f"{frappe.utils.get_url()}/api/method/medic_plus.api.billing.paystack_verify"

    payload = {
        "email": email,
        "amount": amount_kobo,
        "currency": "ZAR",
        "callback_url": callback_url,
        "metadata": {
            "practice": practice,
            "plan_key": plan_key,
            "custom_fields": [
                {"display_name": "Practice", "variable_name": "practice", "value": practice},
                {"display_name": "Plan", "variable_name": "plan_key", "value": plan_key},
            ],
        },
    }

    resp = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=payload,
        headers={"Authorization": f"Bearer {secret_key}", "Content-Type": "application/json"},
        timeout=15,
    )
    data = resp.json()
    if not data.get("status"):
        frappe.throw(f"Paystack error: {data.get('message', 'Unknown error')}")

    return {
        "status": "ok",
        "checkout_url": data["data"]["authorization_url"],
        "reference": data["data"]["reference"],
    }


@frappe.whitelist(allow_guest=True)
def paystack_verify(reference: str = None) -> None:
    """Callback URL after Paystack redirect (GET). Verify and upgrade plan."""
    if not reference:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/billing?error=no_reference"
        return

    secret_key = _get_paystack_secret()
    if not secret_key:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/billing?error=config"
        return

    import requests
    resp = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {secret_key}"},
        timeout=15,
    )
    data = resp.json()
    if data.get("status") and data["data"]["status"] == "success":
        meta = data["data"].get("metadata", {})
        practice = meta.get("practice")
        plan_key = meta.get("plan_key")
        if practice and plan_key:
            _activate_plan(practice, plan_key, reference)
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/billing?success=1"
    else:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/billing?error=payment_failed"


@frappe.whitelist(allow_guest=True)
def paystack_webhook() -> None:
    """Paystack webhook endpoint (POST). Verifies HMAC signature and upgrades plan."""
    secret_key = _get_paystack_secret()
    if not secret_key:
        frappe.local.response.http_status_code = 500
        return

    raw_body = frappe.request.get_data()
    sig = frappe.get_request_header("X-Paystack-Signature", "")
    expected = hmac.new(secret_key.encode(), raw_body, hashlib.sha512).hexdigest()

    if not hmac.compare_digest(sig, expected):
        frappe.local.response.http_status_code = 400
        frappe.log_error("Paystack webhook: invalid signature", "Billing")
        return

    event = json.loads(raw_body)
    if event.get("event") == "charge.success":
        data = event.get("data", {})
        meta = data.get("metadata", {})
        practice = meta.get("practice")
        plan_key = meta.get("plan_key")
        reference = data.get("reference")
        if practice and plan_key:
            _activate_plan(practice, plan_key, reference)

    frappe.local.response.http_status_code = 200


def _activate_plan(practice: str, plan_key: str, reference: str = None) -> None:
    """Set the practice's subscription plan to Active."""
    if plan_key not in MEDIC_PLANS:
        frappe.log_error(f"Unknown plan key: {plan_key}", "Billing")
        return

    frappe.db.set_value(
        "Practice",
        practice,
        {
            "subscription_plan": plan_key,
            "subscription_status": "Active",
            "subscription_reference": reference or "",
            "current_period_end": str(add_months(today(), 1)),
        },
    )
    frappe.db.commit()
    frappe.log_error(
        f"Practice {practice} upgraded to {plan_key} (ref: {reference})", "Billing Activation"
    )


def _get_paystack_secret() -> str | None:
    try:
        return frappe.db.get_single_value("Medic Plus Settings", "paystack_secret_key")
    except Exception:
        return frappe.conf.get("paystack_secret_key")


# ---------------------------------------------------------------------------
# Lifecycle hook — called from doc_events on Practice insert
# ---------------------------------------------------------------------------

def start_trial_for_practice(doc, method=None) -> None:
    """Set Free/Trialing status when a new practice is provisioned.

    Called from hooks.py doc_events on Practice after_insert.
    """
    from frappe.utils import add_days
    trial_end = str(add_days(today(), 14))
    frappe.db.set_value(
        "Practice",
        doc.name,
        {
            "subscription_plan": "Free",
            "subscription_status": "Trialing",
            "trial_ends_on": trial_end,
        },
    )
