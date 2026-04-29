"""
Tests for medic_plus.api.daystar_health and supporting modules.

The Daystar Health SPA is served at /daystar-health and depends on:
- medic_plus.api.practice_resolver — resolves the active Practice for a user,
  raising PermissionError when no membership exists or the user is Guest.
- medic_plus.api.daystar_health (forthcoming) — whitelisted endpoints for the SPA.

All external calls (frappe.db, frappe.session) are mocked. No documents are
created in the database.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe


def setUpModule():
    """Bind frappe LocalProxy objects so mock patching works correctly.

    See test_data_access.setUpModule for the rationale: Python 3.14 + LocalProxy
    needs the ContextVar bound, and frappe.throw() needs cache.hget() and lang.
    """
    frappe.local.session = frappe._dict(user="test@example.test")
    frappe.local.conf = frappe._dict(developer_mode=0)
    frappe.local.flags = frappe._dict()
    frappe.local.lang = "en"
    frappe.local.message_log = []
    frappe.local.error_log = []
    frappe.local.debug_log = []
    frappe.local.response = frappe._dict()

    cache_mock = MagicMock()
    cache_mock.hget.return_value = {}
    frappe.cache = cache_mock

    # frappe.db is a LocalProxy backed by a ContextVar. Bind it with a MagicMock
    # so per-test patch.object(...) calls can introspect it without RuntimeError.
    frappe.local.db = MagicMock()


class TestPracticeResolver(unittest.TestCase):
    """Behavior tests for practice_resolver.get_active_practice.

    The resolver is the single source of truth for "which Practice does this user
    belong to" across all Daystar Health endpoints. Every behavior here describes
    a contract callers rely on; implementation detail (which doctype it queries,
    which field it reads) is intentionally not asserted.
    """

    def _import(self):
        from medic_plus.api import practice_resolver
        return practice_resolver

    def test_returns_practice_for_member(self):
        """Given a user with a Practice Member row, the resolver returns the
        Practice name."""
        m = self._import()
        with patch("medic_plus.api.practice_resolver.frappe.db.get_value",
                   return_value="PRAC-00001") as gv:
            result = m.get_active_practice(user="doctor@example.test")
        self.assertEqual(result, "PRAC-00001")
        gv.assert_called_once()

    def test_raises_for_user_with_no_practice_membership(self):
        """A user without a Practice Member row cannot reach Daystar Health
        data. The resolver raises PermissionError so callers can surface the
        no-practice error card without leaking which Practices exist."""
        m = self._import()
        with patch("medic_plus.api.practice_resolver.frappe.db.get_value",
                   return_value=None):
            with self.assertRaises(frappe.PermissionError):
                m.get_active_practice(user="orphan@example.test")

    def test_raises_for_guest(self):
        """Guest users are anonymous visitors. They never have a Practice
        Member row, but we reject them before the database query so an
        anonymous visit cannot exfiltrate practice membership state."""
        m = self._import()
        with patch("medic_plus.api.practice_resolver.frappe.db.get_value") as gv:
            with self.assertRaises(frappe.PermissionError):
                m.get_active_practice(user="Guest")
        gv.assert_not_called()
