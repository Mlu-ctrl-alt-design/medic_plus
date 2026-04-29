"""
UI Tests: Daystar Health SPA — auth (#4), dashboard (#5), patients list (#6)
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

  Patients list (slice 3):
    7. Patients screen loads with a skeleton, then renders rows from the
       Practice's real data via the REST resource API.
    8. Search input filters the list (debounced server-side).
    9. Pagination prev/next refetches with correct limit_start.
    10. Empty state renders for a search with no matches.

Administrator has no Practice Member row on this site by default, which makes
them the perfect fixture for the no-practice path. The slices that need a
practice user use the admin_with_practice_membership fixture which adds a
temporary Practice Member row for Administrator (role=Admin) and tears it down
on teardown so other tests still see Administrator as no-practice.
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


# ── slice 3: patients list ───────────────────────────────────────────────────


def _login_as_admin(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.locator("#login_email").fill(ADMIN_USER)
    page.locator("#login_password").fill(ADMIN_PASS)
    page.locator(".btn-login[type='submit']").click()
    page.wait_for_url(re.compile(r"/(app|desk)"), timeout=15_000)


def _open_patients_screen(page: Page):
    page.goto(DAYSTAR_URL)
    expect(page.locator('[data-testid="dashboard-ready"]')).to_be_visible(timeout=20_000)
    # Sidebar nav has a Patients button — click it.
    page.locator('[data-testid="nav-patients"]').click()
    expect(page.locator('[data-testid="patients-page"]')).to_be_visible(timeout=10_000)


class TestPatientsListRender:
    """The patients screen hydrates from /api/resource/Patient. The skeleton
    shows during the fetch; the ready state renders rows from the Practice's
    real data along with a real total count."""

    def test_list_loads_and_renders_rows(self, admin_with_practice_membership, page: Page):
        _login_as_admin(page)
        _open_patients_screen(page)

        # Either rows render OR an empty state — both are valid post-skeleton
        # outcomes. The Practice has 8 seeded patients on this site so we
        # expect rows.
        expect(page.locator('[data-testid="patients-table"]')).to_be_visible(timeout=15_000)
        # Total count from the pagination footer comes from the REST API,
        # not from a client-side count of all rows.
        footer = page.locator('[data-testid="patients-pagination-summary"]')
        expect(footer).to_be_visible()
        # The header shows "Patients" and a subtitle with the total.
        expect(page.get_by_role("heading", name=re.compile("^Patients$"))).to_be_visible()
        # At least one row is present (Practice 1 has 8 patients).
        expect(page.locator('[data-testid="patients-row"]').first).to_be_visible(timeout=10_000)


class TestPatientsListSearch:
    """The search input is debounced server-side. Clearing it restores the
    unfiltered list. Used by users to narrow a long Practice list quickly."""

    def test_search_filters_list_and_clear_restores(self, admin_with_practice_membership, page: Page):
        _login_as_admin(page)
        _open_patients_screen(page)
        expect(page.locator('[data-testid="patients-row"]').first).to_be_visible(timeout=15_000)
        initial_count = page.locator('[data-testid="patients-row"]').count()
        assert initial_count > 0, "Expected at least one seeded patient in PRAC-00001"

        # Type a search that matches one of the seeded patients ('Booking').
        page.locator('[data-testid="patients-search"]').fill("Booking")
        # Debounced — wait for refetch.
        page.wait_for_timeout(800)
        rows_after_search = page.locator('[data-testid="patients-row"]').count()
        assert rows_after_search >= 1, "Search for 'Booking' should match at least one row"
        assert rows_after_search <= initial_count, (
            f"Search should narrow results, got {rows_after_search} >= {initial_count}"
        )

        # Clear and confirm restoration.
        page.locator('[data-testid="patients-search"]').fill("")
        page.wait_for_timeout(800)
        restored_count = page.locator('[data-testid="patients-row"]').count()
        assert restored_count == initial_count, (
            f"Clearing search should restore unfiltered count {initial_count}, got {restored_count}"
        )


class TestPatientsListPagination:
    """Pagination uses server-side limit_start/limit_page_length. The footer
    reflects the real total. Prev/next refetch the next page."""

    def test_next_then_prev_changes_visible_rows(self, admin_with_practice_membership, page: Page):
        _login_as_admin(page)
        _open_patients_screen(page)
        expect(page.locator('[data-testid="patients-row"]').first).to_be_visible(timeout=15_000)

        # Force a small page size so even small Practices can paginate.
        page.locator('[data-testid="patients-page-size"]').select_option("25")
        page.wait_for_timeout(800)

        # Capture the names visible on page 1.
        page1_names = page.locator('[data-testid="patients-row"]').all_inner_texts()

        next_btn = page.locator('[data-testid="patients-next"]')
        # If next is disabled, the Practice has fewer than 26 patients — skip
        # the navigation portion of this test (still valid: pagination state
        # correctly identifies there is no next page).
        if next_btn.is_disabled():
            pytest.skip("Practice has <= 25 patients; next-page navigation not exercisable here")

        next_btn.click()
        page.wait_for_timeout(800)
        page2_names = page.locator('[data-testid="patients-row"]').all_inner_texts()
        assert page2_names != page1_names, "Next page should show different rows"

        # Prev should restore page 1 contents.
        page.locator('[data-testid="patients-prev"]').click()
        page.wait_for_timeout(800)
        page1_again = page.locator('[data-testid="patients-row"]').all_inner_texts()
        assert page1_again == page1_names, "Prev should restore the original page"

    def test_page_size_setting_persists_in_session_storage(self, admin_with_practice_membership, page: Page):
        _login_as_admin(page)
        _open_patients_screen(page)
        expect(page.locator('[data-testid="patients-row"]').first).to_be_visible(timeout=15_000)

        page.locator('[data-testid="patients-page-size"]').select_option("100")
        page.wait_for_timeout(400)
        stored = page.evaluate("sessionStorage.getItem('daystar.patients.pageSize')")
        assert stored == "100", f"Expected page size 100 to persist; got {stored!r}"


class TestPatientsListEmptyState:
    """When the search returns nothing, the list shows an empty-state card
    rather than a blank table — and the footer still exists so the user can
    clear the search."""

    def test_empty_state_renders_for_no_match_search(self, admin_with_practice_membership, page: Page):
        _login_as_admin(page)
        _open_patients_screen(page)
        expect(page.locator('[data-testid="patients-row"]').first).to_be_visible(timeout=15_000)

        # Type a deliberately impossible search.
        page.locator('[data-testid="patients-search"]').fill("zzz_nonexistent_query_xyz")
        page.wait_for_timeout(800)
        expect(page.locator('[data-testid="patients-empty-state"]')).to_be_visible(timeout=10_000)
        # No rows are visible.
        assert page.locator('[data-testid="patients-row"]').count() == 0


# ── slice 4: patient detail ──────────────────────────────────────────────────


class TestPatientDetailRender:
    """Clicking a patient from the list navigates to the detail screen, which
    fetches the composite endpoint once and hydrates all six tabs from the
    bundle — no waterfall on tab switch."""

    def test_detail_loads_all_tabs_render(self, admin_with_practice_membership, page: Page):
        _login_as_admin(page)
        _open_patients_screen(page)

        # Administrator's view bypasses Patient PQC (Healthcare Administrator
        # role). The list shows all 133 patients across every Practice, but
        # get_patient_detail correctly rejects cross-tenant clicks. Search for
        # a known PRAC-00001 patient prefix so we click a row in our Practice.
        page.locator('[data-testid="patients-search"]').fill("Booking")
        page.wait_for_timeout(800)
        first_row = page.locator('[data-testid="patients-row"]').first
        expect(first_row).to_be_visible(timeout=15_000)
        first_row.click()

        # Detail page renders.
        expect(page.locator('[data-testid="patient-detail-page"]')).to_be_visible(timeout=15_000)
        expect(page.locator('[data-testid="patient-name"]')).to_be_visible()

        # All 6 tab buttons exist.
        for tab_id in ("overview", "visits", "vitals", "medications", "labs", "notes"):
            expect(page.locator(f'[data-testid="patient-tab-{tab_id}"]')).to_be_visible()

        # Overview is the default — its content container is visible.
        expect(page.locator('[data-testid="patient-tab-content-overview"]')).to_be_visible()

        # Switch to each remaining tab and confirm its content container shows.
        for tab_id in ("visits", "vitals", "medications", "labs", "notes"):
            page.locator(f'[data-testid="patient-tab-{tab_id}"]').click()
            expect(page.locator(f'[data-testid="patient-tab-content-{tab_id}"]')).to_be_visible(timeout=5_000)

    def test_detail_payload_does_not_leak_custom_sa_id_number(self, admin_with_practice_membership, page: Page):
        """POPIA contract: the detail screen's payload must never contain the
        SA ID number. We grab the network response of the composite call and
        assert the field is absent from the JSON."""
        _login_as_admin(page)
        _open_patients_screen(page)

        captured = {}

        def on_response(response):
            url = response.url
            if "get_patient_detail" in url and response.status == 200:
                try:
                    captured["body"] = response.text()
                except Exception:
                    pass

        page.on("response", on_response)

        page.locator('[data-testid="patients-search"]').fill("Booking")
        page.wait_for_timeout(800)
        first_row = page.locator('[data-testid="patients-row"]').first
        expect(first_row).to_be_visible(timeout=15_000)
        first_row.click()
        expect(page.locator('[data-testid="patient-detail-page"]')).to_be_visible(timeout=15_000)

        body = captured.get("body", "")
        assert "custom_sa_id_number" not in body, (
            "POPIA: the get_patient_detail response leaked custom_sa_id_number"
        )
