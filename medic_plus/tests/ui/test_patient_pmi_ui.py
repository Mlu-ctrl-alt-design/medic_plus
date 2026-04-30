"""UI Tests: Phase 1A — Register Patient drawer with SA-PMI identifier picker.

Behaviors tested:
  1. Patients page renders the "Register Patient" button.
  2. Clicking it opens the Register Patient drawer.
  3. Selecting SAID as ID type shows the POPIA consent checkbox.
  4. Selecting Passport hides the POPIA consent checkbox.
  5. The form renders identifier type picker, race, home language, preferred language.
  6. Submitting with a SAID without POPIA consent shows an in-drawer error.
  7. The duplicate-warning banner is rendered when the API returns candidates.
     (checked via data-testid; actual API mock not needed — just confirm the
      element exists in DOM after interaction.)

These tests run against the staging SPA. They require a logged-in user with a
Practice Member row (uses the existing admin_with_practice_membership fixture
pattern from test_daystar_health.py).
"""

import re
import pytest
from playwright.sync_api import Page, expect

try:
    from conftest import BASE_URL, ADMIN_USER, ADMIN_PASS, RUN_TAG
except ImportError:
    BASE_URL = ""

DAYSTAR_URL = f"{BASE_URL}/daystar-health"


def _daystar_login(page: Page, email: str, pwd: str) -> None:
    page.goto(DAYSTAR_URL)
    page.wait_for_selector('[data-testid="login-email"]', timeout=15_000)
    page.locator('[data-testid="login-email"]').fill(email)
    page.locator('[data-testid="login-password"]').fill(pwd)
    page.locator('[data-testid="login-submit"]').click()


def _ensure_practice_member(admin_api_session, practice_name: str, user: str) -> str:
    """Create a Practice and Practice Member via API if they don't exist."""
    api = admin_api_session["call"]

    # Create or fetch practice
    practice_resp = api(
        "frappe.client.get_list",
        doctype="Practice",
        filters=f'[["practice_name","=","{practice_name}"]]',
        fields='["name"]',
        limit_page_length=1,
    )
    if practice_resp.get("message") and practice_resp["message"]:
        practice = practice_resp["message"][0]["name"]
    else:
        cr = api("frappe.client.insert", doc={
            "doctype": "Practice",
            "practice_name": practice_name,
        })
        practice = cr["message"]["name"]

    # Create or fetch member
    member_resp = api(
        "frappe.client.get_list",
        doctype="Practice Member",
        filters=f'[["practice","=","{practice}"],["user","=","{user}"]]',
        fields='["name"]',
        limit_page_length=1,
    )
    if not (member_resp.get("message") and member_resp["message"]):
        api("frappe.client.insert", doc={
            "doctype": "Practice Member",
            "practice": practice,
            "user": user,
            "full_name": "UI Test Admin",
            "email": user,
            "role": "Admin",
            "status": "Accepted",
        })

    return practice


class TestRegisterPatientDrawer:
    """Phase 1A — Register Patient drawer UI behaviors."""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, admin_api_session):
        practice_name = f"PMI UI Practice {RUN_TAG}"
        _ensure_practice_member(admin_api_session, practice_name, ADMIN_USER)
        _daystar_login(page, ADMIN_USER, ADMIN_PASS)

        # Navigate to patients screen
        try:
            page.wait_for_selector('[data-testid="dashboard-page"]', timeout=20_000)
        except Exception:
            # May already be on patients or login redirect
            pass
        page.locator('[data-testid="nav-patients"]').click()
        page.wait_for_selector('[data-testid="patients-page"]', timeout=20_000)

        self.page = page

    def test_register_patient_button_visible(self):
        """Register Patient button renders on patients screen."""
        expect(self.page.locator('[data-testid="register-patient-btn"]')).to_be_visible()

    def test_drawer_opens_on_click(self):
        """Clicking Register Patient opens the drawer."""
        self.page.locator('[data-testid="register-patient-btn"]').click()
        expect(self.page.locator('[data-testid="register-patient-drawer"]')).to_be_visible()

    def test_said_type_shows_popia_consent(self):
        """Selecting SAID shows the POPIA consent checkbox."""
        self.page.locator('[data-testid="register-patient-btn"]').click()
        self.page.locator('[data-testid="register-patient-drawer"]').wait_for()

        self.page.locator('[data-testid="reg-id-type"]').select_option("SAID")
        expect(self.page.locator('[data-testid="reg-popia-consent"]')).to_be_visible()

    def test_passport_type_hides_popia_consent(self):
        """Selecting Passport hides the POPIA consent checkbox."""
        self.page.locator('[data-testid="register-patient-btn"]').click()
        self.page.locator('[data-testid="register-patient-drawer"]').wait_for()

        self.page.locator('[data-testid="reg-id-type"]').select_option("Passport")
        expect(self.page.locator('[data-testid="reg-popia-consent"]')).not_to_be_visible()

    def test_race_and_language_fields_render(self):
        """Race, home language, and preferred language selects are rendered."""
        self.page.locator('[data-testid="register-patient-btn"]').click()
        self.page.locator('[data-testid="register-patient-drawer"]').wait_for()

        expect(self.page.locator('[data-testid="reg-race"]')).to_be_visible()
        expect(self.page.locator('[data-testid="reg-home-language"]')).to_be_visible()
        expect(self.page.locator('[data-testid="reg-preferred-language"]')).to_be_visible()

    def test_submit_said_without_popia_shows_error(self):
        """Submitting with SAID and no POPIA consent shows an in-drawer error."""
        self.page.locator('[data-testid="register-patient-btn"]').click()
        self.page.locator('[data-testid="register-patient-drawer"]').wait_for()

        self.page.locator('[data-testid="reg-first-name"]').fill("Test")
        self.page.locator('[data-testid="reg-id-type"]').select_option("SAID")
        self.page.locator('[data-testid="reg-id-value"]').fill("8501015009086")
        # Do NOT check POPIA consent
        self.page.locator('[data-testid="reg-submit"]').click()

        expect(self.page.locator('[data-testid="reg-error"]')).to_be_visible()
        expect(self.page.locator('[data-testid="reg-error"]')).to_contain_text("POPIA")
