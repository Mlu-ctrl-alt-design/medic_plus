"""Phase 5.11 — Backup-and-restore drill scheduler and reminder logic.

Monthly scheduler function: send_drill_reminder()
  - Queries the most recent Backup Drill Log entry.
  - If none exists, or the most recent drill is > 35 days old, sends an
    ACTION REQUIRED reminder to Healthcare Administrators.
  - Otherwise sends a routine status email (no ACTION REQUIRED).

Whitelisted endpoint: get_last_drill_summary()
  - Returns the most recent drill log row as a dict.
  - Restricted to Healthcare Administrator.
"""

import frappe
from frappe.utils import today, date_diff, getdate


_DRILL_REMINDER_SUBJECT_OK = "Monthly Backup Drill — Completed on Time"
_DRILL_REMINDER_SUBJECT_OVERDUE = "ACTION REQUIRED — Backup Restore Drill Overdue"
_DRILL_THRESHOLD_DAYS = 35


def send_drill_reminder() -> None:
    """Send the monthly backup-drill reminder email to Healthcare Administrators.

    Called by the monthly scheduler event. Checks the age of the last drill;
    if overdue (or never performed) the subject line contains 'ACTION REQUIRED'.
    """
    last = frappe.db.get_value(
        "Backup Drill Log",
        filters={},
        fieldname=["drill_date", "smoke_pass", "run_by"],
        order_by="drill_date desc",
        as_dict=True,
    )

    if last is None:
        days_since = None
        overdue = True
    else:
        days_since = date_diff(today(), last.drill_date)
        overdue = days_since >= _DRILL_THRESHOLD_DAYS

    subject = _DRILL_REMINDER_SUBJECT_OVERDUE if overdue else _DRILL_REMINDER_SUBJECT_OK

    recipients = _get_admin_emails()
    if not recipients:
        return

    if overdue:
        if days_since is None:
            body = (
                "<p><strong>No backup restore drill has ever been recorded.</strong></p>"
                "<p>Please run <code>scripts/drill_restore.sh</code> and log the result "
                "in the <em>Backup Drill Log</em> DocType immediately.</p>"
            )
        else:
            body = (
                f"<p><strong>The last backup restore drill was {days_since} days ago</strong> "
                f"(threshold: {_DRILL_THRESHOLD_DAYS} days).</p>"
                "<p>Please run <code>scripts/drill_restore.sh</code> and log the result "
                "in the <em>Backup Drill Log</em> DocType.</p>"
            )
    else:
        body = (
            f"<p>The last backup restore drill was performed on "
            f"<strong>{last.drill_date}</strong> ({days_since} days ago) by "
            f"{last.run_by}. Smoke test: {'✓ Pass' if last.smoke_pass else '✗ Fail'}.</p>"
            "<p>Next drill due within "
            f"{_DRILL_THRESHOLD_DAYS - days_since} days.</p>"
        )

    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=body,
        now=True,
    )


@frappe.whitelist()
def get_last_drill_summary() -> dict:
    """Return the most recent Backup Drill Log row.

    Restricted to Healthcare Administrator.
    """
    if "Healthcare Administrator" not in frappe.get_roles():
        frappe.throw("Only Healthcare Administrators may access drill summaries.",
                     frappe.PermissionError)

    last = frappe.db.get_value(
        "Backup Drill Log",
        filters={},
        fieldname=["name", "drill_date", "backup_file_name", "backup_size_mb",
                   "restore_elapsed_s", "smoke_pass", "patient_count_restored",
                   "practice_count_restored", "run_by", "notes"],
        order_by="drill_date desc",
        as_dict=True,
    )
    if not last:
        return {"last_drill": None, "overdue": True, "days_since": None}

    days_since = date_diff(today(), last.drill_date)
    return {
        "last_drill": last,
        "overdue": days_since >= _DRILL_THRESHOLD_DAYS,
        "days_since": days_since,
    }


def _log_drill_result(
    *,
    drill_date: str,
    backup_file_name: str,
    backup_size_mb: float,
    restore_elapsed_s: int,
    smoke_pass: int,
    patient_count_restored: int = 0,
    practice_count_restored: int = 0,
    run_by: str = "Administrator",
    notes: str = "",
) -> str:
    """Insert a Backup Drill Log row. Called by scripts/drill_restore.sh via bench execute."""
    doc = frappe.get_doc({
        "doctype": "Backup Drill Log",
        "drill_date": drill_date,
        "backup_file_name": backup_file_name,
        "backup_size_mb": float(backup_size_mb),
        "restore_elapsed_s": int(restore_elapsed_s),
        "smoke_pass": int(smoke_pass),
        "patient_count_restored": int(patient_count_restored),
        "practice_count_restored": int(practice_count_restored),
        "run_by": run_by,
        "notes": notes,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def _get_admin_emails() -> list:
    """Return email addresses of all active Healthcare Administrator users.

    Falls back to the system admin email so the reminder is never silently dropped.
    """
    rows = frappe.db.sql(
        """
        SELECT DISTINCT u.email
        FROM `tabUser` u
        INNER JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE hr.role = 'Healthcare Administrator'
          AND u.enabled = 1
          AND u.email IS NOT NULL
          AND u.email != ''
        """,
        as_dict=True,
    )
    emails = [r.email for r in rows]
    if not emails:
        fallback = frappe.db.get_single_value("System Settings", "email_footer_address") or ""
        if fallback:
            emails = [fallback]
    return emails or ["Administrator"]
