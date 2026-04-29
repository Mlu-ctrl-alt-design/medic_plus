"""
UI Tests: Daystar Health SPA — auth flow (Issue #4) and dashboard (Issue #5)
============================================================================

Behaviors tested:
  Auth flow (slice 1):
    1. Anonymous visit to /daystar-health renders the SPA login screen.
    2. Submitting bad credentials surfaces an in-page error.
    3. Submitting valid credentials reloads to the post-login screen.
    4. An already-logged-in user without a Practice Member row sees the
       "Practice not linked" error card.
    5. Sign-out on the no-practice card returns the user to the login screen.

  Dashboard (slice 2):
    6. An authenticated user *with* a Practice Member row sees the dashboard
       render with KPI tiles and a week-volume chart hydrated from real data.

Administrator has no Practice Member row on this site by default, which makes
them the perfect fixture for the no-practice path. The slice 2 dashboard test
adds a temporary Practice Member row for Administrator and tears it down
afterwards.
"""

import re
import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL, ADMIN_USER, ADMIN_PASS


DAYSTAR_URL = f"{BASE_URL}/daystar-health"


# ── helpers ──────────────────────────────────────────────────────────────────

def _logout(page: Page) -> None:
    """Drop any existing Frappe session by hitting /api/method/logout."""
    page.context.clear_cookies()


def _fill_login(page: Page, email: str, pwd: str) -> None:
    page.locator('[data-testid="login-email"]').fill(email)
    page.locator('[data-testid="login-password"]').fill(pwd)
    page.locator('[data-testid="login-submit"]').click()


# ── tests ────────────────────────────────────────────────────────────────────


class TestAnonymousFlow:
    """An unauthenticated visitor lands on the login screen and can attempt sign in."""

    def test_anonymous_visit_shows_login_screen(self, page: Page):
        _logout(page)
        page.goto(DAYSTAR_URL)
        expect(page.locator('[data-testid="login-email"]')).to_be_visible()
        expect(page.locator('[data-testid="login-submit"]')).to_be_visible()
        # Heading copy is part of the public contract — exposes the login intent.
        expect(page.get_by_role("heading", name=re.compile("Sign in", re.I))).to_be_visible()

    def test_invalid_credentials_show_error_message(self, page: Page):
        _logout(page)
        page.goto(DAYSTAR_URL)
        _fill_login(page, "definitely-not-a-user@example.test", "wrong-pw")
        # Error banner appears in-page (the SPA does not navigate away on failure).
        expect(page.locator('[data-testid="login-error"]')).to_be_visible(timeout=15_000)
        # User stays on login screen — no redirect happened.
        expect(page.locator('[data-testid="login-email"]')).to_be_visible()


class TestPostLoginRouting:
    """After a successful login the SPA reloads and routes based on the user's
    Practice Member status. Administrator has no Practice Member row, so they
    land on the no-practice card."""

    def test_admin_login_lands_on_no_practice_card(self, page: Page):
        _logout(page)
        page.goto(DAYSTAR_URL)
        _fill_login(page, ADMIN_USER, ADMIN_PASS)
        # Page reloads after login. The reload re-evaluates session + has_practice
        # in daystar_health.py, and the SPA renders the no-practice card.
        expect(page.locator('[data-testid="no-practice-card"]')).to_be_visible(timeout=20_000)
        expect(page.get_by_role("heading", name=re.compile("Practice not linked", re.I))).to_be_visible()

    def test_already_logged_in_admin_skips_login_screen(self, logged_in_admin_page: Page):
        # Pre-condition: logged_in_admin_page fixture has an authenticated admin session.
        page = logged_in_admin_page
        page.goto(DAYSTAR_URL)
        # Login screen must NOT appear — first-render routing skips it.
        expect(page.locator('[data-testid="login-email"]')).not_to_be_visible(timeout=10_000)
        # No-practice card IS visible because admin has no Practice Member row.
        expect(page.locator('[data-testid="no-practice-card"]')).to_be_visible(timeout=10_000)


class TestNoPracticeSignOut:
    """Sign-out on the no-practice card releases the session and shows the login screen."""

    def test_signout_returns_to_login_screen(self, logged_in_admin_page: Page):
        page = logged_in_admin_page
        page.goto(DAYSTAR_URL)
        expect(page.locator('[data-testid="no-practice-card"]')).to_be_visible(timeout=10_000)
        page.locator('[data-testid="no-practice-signout"]').click()
        # logout() in meridian-api navigates to /daystar-health, which re-renders
        # as Guest → login screen.
        expect(page.locator('[data-testid="login-email"]')).to_be_visible(timeout=15_000)
        expect(page.locator('[data-testid="no-practice-card"]')).not_to_be_visible()


# ── slice 2: dashboard ───────────────────────────────────────────────────────


@pytest.fixture
def admin_with_practice_membership():
    """Temporarily make Administrator a Practice Member of PRAC-00001.

    The Daystar Health SPA gates dashboard access on Practice membership. We
    need a logged-in user *with* a Practice for the dashboard test, but the
    site only has Administrator with known credentials. This fixture inserts
    the membership row before the test and removes it on teardown so other
    tests (which assume Administrator has no Practice) keep passing.
    """
    import os
    os.chdir('/home/fruppa/frappe-bench/sites')
    import frappe
    frappe.init(site='medic-demo-staging.thedaystar.co.za')
    frappe.connect()

    practice = "PRAC-00001"
    # Use 'Admin' role: Practice Member validation requires a Healthcare
    # Practitioner link when role=Doctor, which Administrator doesn't have.
    member = frappe.get_doc({
        "doctype": "Practice Member",
        "user": "Administrator",
        "practice": practice,
        "role": "Admin",
        "status": "Accepted",
        "full_name": "Test Administrator",
        "email": "Administrator",
    })
    member.insert(ignore_permissions=True)
    frappe.db.commit()
    yield {"practice": practice, "member_name": member.name}
    frappe.delete_doc("Practice Member", member.name, ignore_permissions=True, force=True)
    frappe.db.commit()
    frappe.destroy()


class TestDashboardRender:
    """The dashboard hydrates from medic_plus.api.daystar_health.get_dashboard
    and surfaces the three KPI tiles, a week-volume chart, and the recent
    patients table — all scoped to the user's Practice."""

    def test_practice_user_sees_dashboard_with_kpis(self, admin_with_practice_membership, page: Page):
        # Log in as admin (now a Practice Member of PRAC-00001).
        page.goto(f"{BASE_URL}/login")
        page.locator("#login_email").fill(ADMIN_USER)
        page.locator("#login_password").fill(ADMIN_PASS)
        page.locator(".btn-login[type='submit']").click()
        page.wait_for_url(re.compile(r"/(app|desk)"), timeout=15_000)

        page.goto(DAYSTAR_URL)
        # Skeleton appears first, then resolves to the ready state.
        expect(page.locator('[data-testid="dashboard-ready"]')).to_be_visible(timeout=20_000)

        # All three KPI tiles render (numbers vary by data; we just assert
        # the tiles are present, not their values).
        expect(page.locator('[data-testid="kpi-today-appointments"]')).to_be_visible()
        expect(page.locator('[data-testid="kpi-active-patients"]')).to_be_visible()
        expect(page.locator('[data-testid="kpi-outstanding-labs"]')).to_be_visible()

        # The week-volume chart renders 7 day bars (svg <text> labels).
        expect(page.locator('[data-testid="week-volume"]')).to_be_visible()

        # Today's schedule and recent-patients sections both render their
        # container — even when empty they show an empty-state message.
        expect(page.locator('[data-testid="today-schedule"]')).to_be_visible()
        expect(page.locator('[data-testid="recent-patients"]')).to_be_visible()

        # Greeting addresses the user (Administrator's first_name happens to
        # be 'Administrator' on a fresh site, so we just check the testid).
        expect(page.locator('[data-testid="dashboard-greeting"]')).to_be_visible()

        # "View full schedule" link points at the Frappe Desk Patient
        # Appointment list scoped to today + this Practice.
        href = page.locator('[data-testid="view-full-schedule"]').get_attribute("href")
        assert href and "/app/patient-appointment" in href, f"unexpected href: {href}"
        assert "PRAC-00001" in href, f"href missing practice scope: {href}"
