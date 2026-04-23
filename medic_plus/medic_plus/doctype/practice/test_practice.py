"""
Tests for Practice doctype.

IGNORE_TEST_RECORD_DEPENDENCIES stops the Frappe test generator from
traversing into the Company doctype (which imports ERPNext's BootStrapTestData
at module level, causing fiscal-year conflicts on existing sites).

Company creation per Practice is tested in test_provisioning.py
where the full provision_doctor() flow is exercised in isolation.
"""

from frappe.tests.utils import FrappeTestCase

# Stop the test record traversal from reaching Company.
# Without this, the test runner imports erpnext/tests/utils.py which runs
# BootStrapTestData() at module level and conflicts with the site's 2026-2027 FY.
# Block both Company (creates fiscal years on existing sites) and Healthcare Practitioner
# (which links to Employee → test_employee.py → BootStrapTestData at module import time).
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]


class TestPractice(FrappeTestCase):
	pass
