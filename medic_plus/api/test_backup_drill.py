"""Phase 5.11 — Backup-and-restore drill: integration tests.

Covers:
  1. Backup Drill Log is append-only (delete blocked for all roles).
  2. Monthly reminder fires 'ACTION REQUIRED' when last drill > 35 days ago.
  3. Reminder does NOT include 'ACTION REQUIRED' when last drill <= 35 days ago.
  4. Reminder fires 'ACTION REQUIRED' when no drill log rows exist at all.
"""

import frappe
from frappe.tests import IntegrationTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


def _make_drill_log(days_ago: int = 0) -> str:
    """Insert a Backup Drill Log row *days_ago* days in the past."""
    drill_date = frappe.utils.add_days(frappe.utils.today(), -days_ago)
    return frappe.get_doc({
        "doctype": "Backup Drill Log",
        "drill_date": drill_date,
        "backup_file_name": f"backup_{days_ago}d_ago.tar.gz",
        "backup_size_mb": 512.0,
        "restore_elapsed_s": 420,
        "smoke_pass": 1,
        "patient_count_restored": 120,
        "practice_count_restored": 3,
        "run_by": "Administrator",
        "notes": f"Test drill {days_ago} days ago",
    }).insert(ignore_permissions=True).name


class TestBackupDrillLogAppendOnly(IntegrationTestCase):
    """Backup Drill Log rows cannot be deleted by any role."""

    def test_delete_raises_permission_error_for_system_manager(self):
        """Even System Manager cannot delete a Backup Drill Log row."""
        name = _make_drill_log(10)
        with self.assertRaises((frappe.PermissionError, frappe.exceptions.ValidationError)):
            frappe.get_doc("Backup Drill Log", name).delete()

    def test_delete_via_db_raises_or_is_blocked(self):
        """frappe.delete_doc respects the no-delete permission."""
        name = _make_drill_log(11)
        with self.assertRaises((frappe.PermissionError, frappe.exceptions.ValidationError)):
            frappe.delete_doc("Backup Drill Log", name, ignore_permissions=False)

    def test_insert_succeeds(self):
        """Inserting a Backup Drill Log row succeeds without error."""
        name = _make_drill_log(5)
        self.assertTrue(frappe.db.exists("Backup Drill Log", name))


class TestDrillReminderActionRequired(IntegrationTestCase):
    """Monthly reminder fires ACTION REQUIRED when drill is overdue or missing."""

    def setUp(self):
        # Clear all existing drill logs to control the state
        frappe.db.sql("DELETE FROM `tabBackup Drill Log`", auto_commit=True)

    def test_no_drill_logs_triggers_action_required(self):
        """No drill log rows → reminder subject contains 'ACTION REQUIRED'."""
        import unittest.mock as mock
        from medic_plus.api.backup_drill import send_drill_reminder
        with mock.patch("frappe.sendmail") as mock_mail:
            send_drill_reminder()
        calls = mock_mail.call_args_list
        self.assertTrue(
            any("ACTION REQUIRED" in str(c) for c in calls),
            "Expected 'ACTION REQUIRED' in sendmail call when no drill logs exist",
        )

    def test_overdue_drill_triggers_action_required(self):
        """Drill > 35 days ago → reminder subject contains 'ACTION REQUIRED'."""
        import unittest.mock as mock
        _make_drill_log(36)
        from medic_plus.api.backup_drill import send_drill_reminder
        with mock.patch("frappe.sendmail") as mock_mail:
            send_drill_reminder()
        calls = mock_mail.call_args_list
        self.assertTrue(
            any("ACTION REQUIRED" in str(c) for c in calls),
            "Expected 'ACTION REQUIRED' when last drill was 36 days ago",
        )

    def test_exactly_35_days_triggers_action_required(self):
        """Drill exactly 35 days ago → ACTION REQUIRED (threshold is strictly < 35)."""
        import unittest.mock as mock
        _make_drill_log(35)
        from medic_plus.api.backup_drill import send_drill_reminder
        with mock.patch("frappe.sendmail") as mock_mail:
            send_drill_reminder()
        calls = mock_mail.call_args_list
        self.assertTrue(
            any("ACTION REQUIRED" in str(c) for c in calls),
        )


class TestDrillReminderNoAction(IntegrationTestCase):
    """Monthly reminder does NOT fire ACTION REQUIRED when drill is current."""

    def setUp(self):
        frappe.db.sql("DELETE FROM `tabBackup Drill Log`", auto_commit=True)

    def test_recent_drill_no_action_required(self):
        """Drill 10 days ago → reminder does NOT say ACTION REQUIRED."""
        import unittest.mock as mock
        _make_drill_log(10)
        from medic_plus.api.backup_drill import send_drill_reminder
        with mock.patch("frappe.sendmail") as mock_mail:
            send_drill_reminder()
        calls = mock_mail.call_args_list
        # Either no email sent, or email sent without ACTION REQUIRED
        if calls:
            self.assertFalse(
                any("ACTION REQUIRED" in str(c) for c in calls),
                "Did not expect ACTION REQUIRED when drill was 10 days ago",
            )

    def test_yesterday_drill_no_action_required(self):
        """Drill yesterday → definitely no ACTION REQUIRED."""
        import unittest.mock as mock
        _make_drill_log(1)
        from medic_plus.api.backup_drill import send_drill_reminder
        with mock.patch("frappe.sendmail") as mock_mail:
            send_drill_reminder()
        calls = mock_mail.call_args_list
        if calls:
            self.assertFalse(any("ACTION REQUIRED" in str(c) for c in calls))
