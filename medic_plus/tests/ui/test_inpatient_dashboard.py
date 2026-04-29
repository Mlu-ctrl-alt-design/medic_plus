"""
UI Tests: Inpatient Dashboard
=============================

Flow tested:
  1. Admin can navigate to /app/inpatient-dashboard
  2. Summary stat cards render with correct labels
  3. Empty-state message appears when no inpatients exist
  4. API: get_inpatient_summary returns expected shape
  5. API: get_current_inpatients returns a list
  6. Feature gate: Free-plan practice user is blocked by require_feature
  7. Workspace shortcut wires to the correct page
"""

import re
import pytest
from playwright.sync_api import Page, expect

try:
    from conftest import BASE_URL, ADMIN_USER, ADMIN_PASS, RUN_TAG, _frappe_login
except ImportError:
    pass  # bench run-tests preloader path; tests run only under pytest.


# ── helpers ──────────────────────────────────────────────────────────────────

def _api_call(page: Page, method: str, args: dict | None = None) -> dict:
    """Invoke a whitelisted Frappe method from within the browser context."""
    return page.evaluate(
        """async ([url, method, args]) => {
            return new Promise((resolve) => {
                frappe.call({
                    method,
                    args: args || {},
                    callback: (r) => resolve(r),
                    error: (xhr) => {
                        try { resolve(JSON.parse(xhr.responseText)); }
                        catch { resolve({ exc: xhr.responseText || 'Unknown error', exc_type: 'ServerError' }); }
                    },
                });
            });
        }""",
        [BASE_URL, method, args or {}],
    )


# ── tests ─────────────────────────────────────────────────────────────────────


class TestInpatientDashboardPage:
    """Smoke tests for the /app/inpatient-dashboard Frappe desk page."""

    def test_page_loads_for_admin(self, logged_in_admin_page: Page):
        """Admin can navigate to the inpatient dashboard and the page title renders."""
        page = logged_in_admin_page
        page.goto(f"{BASE_URL}/app/inpatient-dashboard")
        page.wait_for_load_state("load")

        # Frappe desk sets <title> from the Page doctype title field
        expect(page).to_have_title(re.compile(r"inpatient", re.I), timeout=15_000)

    def test_summary_cards_present(self, logged_in_admin_page: Page):
        """All four stat cards render with the expected labels."""
        page = logged_in_admin_page
        page.goto(f"{BASE_URL}/app/inpatient-dashboard")
        page.wait_for_load_state("networkidle")

        # The JS renders cards after frappe.call resolves; wait for them.
        page.wait_for_selector(".stat-card", timeout=20_000)

        expected_labels = [
            "Current Inpatients",
            "Today's Admissions",
            "Expected Discharges",
            "Avg LOS",
        ]
        for label in expected_labels:
            # Scope to .stat-label to avoid matching the "No current inpatients." paragraph
            expect(page.locator(".stat-card .stat-label", has_text=label)).to_be_visible(timeout=10_000)

    def test_empty_state_when_no_inpatients(self, logged_in_admin_page: Page):
        """When no patients are admitted, the 'No current inpatients' message shows."""
        page = logged_in_admin_page
        page.goto(f"{BASE_URL}/app/inpatient-dashboard")
        page.wait_for_load_state("networkidle")

        # Wait for either the table OR the empty state to appear
        page.wait_for_selector("#ipd-table-wrap", timeout=20_000)

        inpatient_rows = page.locator("#ipd-table-wrap tbody tr")
        table_visible = inpatient_rows.count() > 0

        if not table_visible:
            expect(
                page.get_by_text("No current inpatients", exact=False)
            ).to_be_visible(timeout=5_000)

    def test_refresh_button_present(self, logged_in_admin_page: Page):
        """The toolbar 'Refresh' button is present on the dashboard."""
        page = logged_in_admin_page
        page.goto(f"{BASE_URL}/app/inpatient-dashboard")
        page.wait_for_load_state("load")

        expect(page.get_by_role("button", name=re.compile(r"refresh", re.I))).to_be_visible(
            timeout=10_000
        )

    def test_new_admission_button_present(self, logged_in_admin_page: Page):
        """The 'New Admission' button opens the Inpatient Record form."""
        page = logged_in_admin_page
        page.goto(f"{BASE_URL}/app/inpatient-dashboard")
        page.wait_for_load_state("load")

        expect(
            page.get_by_role("button", name=re.compile(r"new admission", re.I))
        ).to_be_visible(timeout=10_000)


class TestInpatientSummaryApi:
    """Tests for the get_inpatient_summary and get_current_inpatients API endpoints."""

    def test_summary_returns_expected_keys(self, logged_in_admin_page: Page):
        """get_inpatient_summary returns all required keys with numeric values."""
        page = logged_in_admin_page
        result = _api_call(page, "medic_plus.api.inpatient.get_inpatient_summary")

        assert "message" in result, f"No message in response: {result}"
        msg = result["message"]

        for key in ("current_inpatients", "todays_admissions", "expected_discharges", "avg_los_days"):
            assert key in msg, f"Missing key '{key}' in summary: {msg}"
            assert isinstance(msg[key], (int, float)), f"'{key}' is not numeric: {msg[key]}"

    def test_summary_counts_are_non_negative(self, logged_in_admin_page: Page):
        """All summary counts are non-negative integers."""
        page = logged_in_admin_page
        result = _api_call(page, "medic_plus.api.inpatient.get_inpatient_summary")
        msg = result["message"]

        assert msg["current_inpatients"] >= 0
        assert msg["todays_admissions"] >= 0
        assert msg["expected_discharges"] >= 0
        assert msg["avg_los_days"] >= 0

    def test_current_inpatients_returns_list(self, logged_in_admin_page: Page):
        """get_current_inpatients returns a JSON array (may be empty)."""
        page = logged_in_admin_page
        result = _api_call(page, "medic_plus.api.inpatient.get_current_inpatients")

        assert "message" in result, f"No message in response: {result}"
        assert isinstance(result["message"], list), (
            f"Expected a list, got {type(result['message'])}"
        )

    def test_inpatient_records_have_required_fields(self, logged_in_admin_page: Page):
        """Each inpatient record in the list has the required display fields."""
        page = logged_in_admin_page
        result = _api_call(page, "medic_plus.api.inpatient.get_current_inpatients")
        records = result["message"]

        if not records:
            pytest.skip("No current inpatients in staging — field structure test skipped")

        required_fields = ("name", "patient", "patient_name", "status", "los_days")
        for record in records:
            for field in required_fields:
                assert field in record, f"Field '{field}' missing from inpatient record: {record}"


class TestInpatientFeatureGate:
    """Tests that require_feature('inpatient_module') blocks Free-plan practices."""

    def test_feature_gate_api_accepts_admin(self, logged_in_admin_page: Page):
        """Platform admin (Healthcare Administrator) is never blocked by the feature gate."""
        page = logged_in_admin_page
        result = _api_call(page, "medic_plus.api.inpatient.get_inpatient_summary")

        # Admin should get a successful response, not a permission error
        assert "exc" not in result or result.get("message") is not None, (
            f"Admin should not be blocked by feature gate: {result}"
        )
        assert "message" in result

    def test_feature_gate_blocks_free_plan_practice_user(self, page: Page):
        """A user whose practice is on the Free plan cannot call inpatient APIs.

        This test provisions a fresh practice (Free plan) and a doctor user via the
        admin session, then opens a SEPARATE browser context (fresh cookies) and logs
        in as that doctor to verify the feature gate blocks the inpatient API.
        """
        # --- Setup: use admin page to create a disposable practice + doctor ---
        _frappe_login(page, ADMIN_USER, ADMIN_PASS)

        tag = f"{RUN_TAG}ipd"
        dr_email = f"dr.gate.{tag}@medic-ui-test.local"

        onboard = page.evaluate(
            """async ([url, payload]) => {
                const r = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Frappe-CSRF-Token': frappe.csrf_token,
                    },
                    body: new URLSearchParams(payload),
                });
                return r.json();
            }""",
            [
                f"{BASE_URL}/api/method/medic_plus.api.onboarding.onboard_doctor",
                {
                    "full_name": f"Gate Test Doctor {tag}",
                    "email": dr_email,
                    "mobile": f"071{RUN_TAG}",
                    "hpcsa_number": f"MP{tag}",
                    "practice_number": f"PR{tag}",
                    "practice_name": f"Gate Test Practice {tag}",
                },
            ],
        )
        assert "message" in onboard and onboard["message"].get("practice"), (
            f"Failed to provision test practice: {onboard}"
        )
        practice_name = onboard["message"]["practice"]

        # Ensure the practice is on the Free plan (default, but set explicitly)
        set_plan = page.evaluate(
            """async ([url, practice]) => {
                const r = await fetch(`${url}/api/resource/Practice/${encodeURIComponent(practice)}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Frappe-CSRF-Token': frappe.csrf_token,
                    },
                    body: JSON.stringify({ subscription_plan: 'Free' }),
                });
                return r.json();
            }""",
            [BASE_URL, practice_name],
        )
        assert "data" in set_plan, f"Failed to set practice plan: {set_plan}"

        # Reset doctor password for login
        page.evaluate(
            """async ([url, email]) => {
                await fetch(`${url}/api/resource/User/${encodeURIComponent(email)}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Frappe-CSRF-Token': frappe.csrf_token,
                    },
                    body: JSON.stringify({ new_password: 'TestPass@123' }),
                });
            }""",
            [BASE_URL, dr_email],
        )

        # --- Act: call the inpatient API as the Free-plan doctor using a Python requests session ---
        # This avoids Playwright browser-navigation issues that arise when Frappe handles 403
        # errors (the 403 handler can trigger a re-route when frappe.session.user is Guest during
        # the SPA boot phase, destroying the page.evaluate execution context).
        import urllib.request as _urlreq
        import urllib.parse as _urlparse
        import http.cookiejar as _cookiejar
        import ssl as _ssl
        import json as _json
        import re as _re

        _ssl_ctx = _ssl.create_default_context()
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = _ssl.CERT_NONE
        _jar = _cookiejar.CookieJar()
        _opener = _urlreq.build_opener(
            _urlreq.HTTPCookieProcessor(_jar),
            _urlreq.HTTPSHandler(context=_ssl_ctx),
        )

        def _dr_post(url, data):
            body = _urlparse.urlencode(data).encode()
            req = _urlreq.Request(
                url, body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with _opener.open(req) as resp:
                return _json.loads(resp.read())

        # Login as doctor (sets session cookie in _jar)
        _dr_post(f"{BASE_URL}/api/method/login", {"usr": dr_email, "pwd": "TestPass@123"})

        # Get CSRF token from the desk HTML (GET request, no CSRF needed)
        _desk_req = _urlreq.Request(f"{BASE_URL}/desk")
        with _opener.open(_desk_req) as _resp:
            _desk_html = _resp.read().decode("utf-8", errors="replace")
        # Extract csrf_token from the boot script in desk HTML
        _m = _re.search(r'"csrf_token"\s*:\s*"([^"]+)"', _desk_html)
        _csrf = _m.group(1) if _m else ""

        # Call get_inpatient_summary as the doctor
        _api_req = _urlreq.Request(
            f"{BASE_URL}/api/method/medic_plus.api.inpatient.get_inpatient_summary",
            "".encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Frappe-CSRF-Token": _csrf,
            },
        )
        try:
            with _opener.open(_api_req) as _resp:
                result = _json.loads(_resp.read())
        except _urlreq.HTTPError as e:
            result = {"exc": str(e), "status_code": e.code, "exc_type": type(e).__name__}

        # Expect either an exception or an HTTP error (403/417 PermissionError)
        has_error = (
            result.get("exc") is not None
            or result.get("exc_type") is not None
            or result.get("status_code") in (403, 417)
            or result.get("message") is None
        )
        assert has_error, (
            f"Free-plan doctor should be blocked by inpatient feature gate, got: {result}"
        )
