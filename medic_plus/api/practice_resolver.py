"""Resolve the active Practice for a user.

The Daystar Health SPA and its endpoints require a Practice context for every
operation. This module is the single source of truth for that resolution, and
the place to look when adding a new endpoint that needs tenant scoping.
"""

import frappe


def get_active_practice(user: str | None = None) -> str:
    user = user or frappe.session.user
    if user == "Guest":
        raise frappe.PermissionError("Sign in to access Daystar Health.")
    practice = frappe.db.get_value(
        "Practice Member", {"user": user}, "practice"
    )
    if not practice:
        raise frappe.PermissionError(
            "Your account is not linked to a practice."
        )
    return practice
