"""
UI Tests: Daystar Health SPA — auth flow (Issue #4)
====================================================

Behaviors tested:
  1. Anonymous visit to /daystar-health renders the SPA login screen.
  2. Submitting bad credentials surfaces an in-page error.
  3. Submitting valid credentials reloads to the post-login screen.
  4. An already-logged-in user without a Practice Member row sees the
     "Practice not linked" error card.
  5. Sign-out on the no-practice card returns the user to the login screen.

Administrator has no Practice Member row on this site, which makes them the
perfect fixture for the no-practice path. Test 3 asserts the post-login render
(either dashboard or no-practice card) — proving the login wire round-trips.
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
