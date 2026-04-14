"""
UI Test: Doctor Sign-Up and Practice Creation
=============================================

Flow tested:
  1. Admin logs in to Frappe Desk
  2. Admin calls onboard_doctor API → creates Practice + User + Practitioner + Practice Member
  3. New doctor user appears in User list with Practice Doctor role
  4. Practice record appears with correct name
  5. Practice Member links doctor to practice

The onboard_doctor endpoint is guarded by System Manager role — no public
sign-up page exists yet (Phase 6). These tests exercise the admin-side
provisioning flow that runs before a doctor's first login.
"""

import re
import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL, ADMIN_USER, ADMIN_PASS, RUN_TAG, _frappe_login


# ── Test data ─────────────────────────────────────────────────────────────────

DR_EMAIL       = f"dr.test.{RUN_TAG}@medic-ui-test.local"
DR_FULL_NAME   = f"Dr Test Doctor {RUN_TAG}"
DR_MOBILE      = f"082{RUN_TAG}"
DR_HPCSA       = f"MP{RUN_TAG}"
DR_PRAC_NUMBER = f"PR{RUN_TAG}"
PRACTICE_NAME  = f"Test Practice {RUN_TAG}"


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDoctorSignupAndPracticeCreation:
    """Admin onboards a doctor; verifies all downstream records."""

    def test_admin_can_login_to_desk(self, page: Page):
        """Sanity: Administrator can reach the Frappe Desk."""
        _frappe_login(page, ADMIN_USER, ADMIN_PASS)
        expect(page).to_have_url(re.compile(r"/(app|desk)"), timeout=15_000)
        # Desk loaded: the main content area should be visible
        page.wait_for_selector(".desk-page, .page-container, #page-container, main", timeout=10_000)

    def test_onboard_doctor_api_creates_all_records(self, page: Page):
        """
        Call medic_plus.api.onboarding.onboard_doctor from within the browser
        (authenticated as Administrator) and assert the JSON response contains
        the expected record names.
        """
        _frappe_login(page, ADMIN_USER, ADMIN_PASS)

        # Call the API via fetch() in the page context; credentials ride the
        # session cookie that Frappe already set during login.
        result = page.evaluate(
            """async ([url, payload]) => {
                const resp = await fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded',
                              'X-Frappe-CSRF-Token': frappe.csrf_token},
                    body: new URLSearchParams(payload),
                });
                return resp.json();
            }""",
            [
                f"{BASE_URL}/api/method/medic_plus.api.onboarding.onboard_doctor",
                {
                    "full_name":       DR_FULL_NAME,
                    "email":           DR_EMAIL,
                    "mobile":          DR_MOBILE,
                    "hpcsa_number":    DR_HPCSA,
                    "practice_number": DR_PRAC_NUMBER,
                    "practice_name":   PRACTICE_NAME,
                },
            ],
        )

        assert "message" in result, f"Unexpected response: {result}"
        msg = result["message"]

        # API returns the created record names
        assert msg.get("user") == DR_EMAIL, f"User not in response: {msg}"
        assert "practice" in msg and msg["practice"], f"Practice not in response: {msg}"
        assert "practitioner" in msg and msg["practitioner"], f"Practitioner not in response: {msg}"

        # Stash created names on the class for subsequent tests
        TestDoctorSignupAndPracticeCreation.created_practice = msg["practice"]
        TestDoctorSignupAndPracticeCreation.created_practitioner = msg["practitioner"]

    def test_practice_appears_in_desk_list(self, page: Page):
        """After onboarding, the new Practice record is visible in the list view."""
        _frappe_login(page, ADMIN_USER, ADMIN_PASS)

        page.goto(f"{BASE_URL}/app/practice")
        page.wait_for_load_state("load")

        # The list view should show the practice name
        expect(
            page.get_by_text(PRACTICE_NAME, exact=False)
        ).to_be_visible(timeout=10_000)

    def test_doctor_user_has_practice_doctor_role(self, page: Page):
        """The provisioned user has exactly the 'Practice Doctor' role in the Desk."""
        _frappe_login(page, ADMIN_USER, ADMIN_PASS)

        # Navigate to the User form
        page.goto(f"{BASE_URL}/app/user/{DR_EMAIL}")
        page.wait_for_load_state("load")

        # Roles section lists Practice Doctor
        expect(
            page.get_by_text("Practice Doctor", exact=False)
        ).to_be_visible(timeout=10_000)

    def test_practice_member_links_doctor_to_practice(self, page: Page):
        """A Practice Member record exists linking the doctor to the new practice."""
        _frappe_login(page, ADMIN_USER, ADMIN_PASS)

        page.goto(f"{BASE_URL}/app/practice-member")
        page.wait_for_load_state("load")

        # Filter by user — use .first to avoid strict-mode error when Frappe
        # renders multiple buttons whose accessible name contains "filter".
        page.get_by_role("button", name=re.compile(r"filter", re.I)).first.click()
        page.wait_for_timeout(500)

        # Add filter: user = DR_EMAIL
        filter_input = page.locator("input[data-fieldname='user'], .filter-field input").last
        filter_input.fill(DR_EMAIL)
        page.keyboard.press("Enter")
        page.wait_for_load_state("load")

        # At least one row should match
        expect(
            page.get_by_text(DR_EMAIL, exact=False)
        ).to_be_visible(timeout=10_000)

    def test_doctor_can_login_to_desk(self, page: Page):
        """
        The newly provisioned doctor can authenticate and reach the Frappe Desk.

        Frappe sends a welcome email with a login link on provisioning; in tests
        we reset the password via the admin API first so we can log in immediately
        without waiting for email.
        """
        # Must be on a Frappe Desk page so frappe.csrf_token is available.
        _frappe_login(page, ADMIN_USER, ADMIN_PASS)

        # Reset the doctor's password via Admin API
        reset_result = page.evaluate(
            """async ([url, payload]) => {
                const resp = await fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded',
                              'X-Frappe-CSRF-Token': frappe.csrf_token},
                    body: new URLSearchParams(payload),
                });
                return resp.json();
            }""",
            [
                f"{BASE_URL}/api/method/frappe.core.doctype.user.user.update_password",
                {
                    "new_password": "TestPass@123",
                    "logout_all_sessions": 0,
                    "user": DR_EMAIL,
                },
            ],
        )
        # update_password returns {"message": "Password updated"} or similar
        assert reset_result.get("message") or "exc" not in reset_result, (
            f"Password reset failed: {reset_result}"
        )

        # Now log out and log in as the doctor
        page.goto(f"{BASE_URL}/api/method/logout")
        page.wait_for_load_state("load")

        _frappe_login(page, DR_EMAIL, "TestPass@123")
        expect(page).to_have_url(re.compile(r"/(app|desk)"), timeout=15_000)
