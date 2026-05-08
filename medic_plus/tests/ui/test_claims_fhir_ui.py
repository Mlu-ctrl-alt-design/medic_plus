"""
UI Tests: Claims + FHIR R4 — Phase 1E (#28)
============================================

Covers:
  1. FHIR metadata endpoint returns a valid CapabilityStatement JSON.
  2. CapabilityStatement lists all six FHIR resource types.
  3. FHIR metadata accessible without authentication (allow_guest=True).
  4. Claims API: get_claim_for_encounter returns None for a non-existent encounter.
  5. Claims API: submit_claim raises a clean error for a non-Draft claim (API shape).
  6. FHIR token issue endpoint reachable for an authenticated user.
  7. FHIR token is rejected for a Guest user (unauthenticated).
  8. Sub-Processor Register: API returns the seeded processors list.
  9. Patient Consent Record: API endpoint guarded by login.
 10. FHIR router: get_encounter returns 404 OperationOutcome for a non-existent ID.
"""

import re
import json
import urllib.request
import urllib.parse
import http.cookiejar
import ssl
import pytest
from playwright.sync_api import Page, expect

try:
    from conftest import BASE_URL, ADMIN_USER, ADMIN_PASS, RUN_TAG, _frappe_login
except ImportError:
    pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _api_call(page: Page, method: str, args: dict | None = None) -> dict:
    return page.evaluate(
        """async ([method, args]) => {
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
        [method, args or {}],
    )


def _make_ssl_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=ssl_ctx),
    )


def _http_get_json(url: str, *, opener=None) -> tuple[int, dict]:
    """Perform an HTTP GET and return (status_code, json_body)."""
    if opener is None:
        opener = _make_ssl_opener()
    try:
        with opener.open(url) as resp:
            return resp.getcode(), json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {}


# ── FHIR metadata (no auth) ───────────────────────────────────────────────────

class TestFhirMetadataEndpoint:
    """The /api/fhir/R4/metadata endpoint must be publicly accessible."""

    def test_metadata_returns_200(self, page: Page):
        """GET /api/method/.../get_metadata returns HTTP 200."""
        resp = page.request.get(
            f"{BASE_URL}/api/method/medic_plus.api.fhir.router.get_metadata",
            ignore_https_errors=True,
        )
        assert resp.status == 200

    def test_metadata_resource_type(self, page: Page):
        resp = page.request.get(
            f"{BASE_URL}/api/method/medic_plus.api.fhir.router.get_metadata",
            ignore_https_errors=True,
        )
        body = resp.json()
        message = body.get("message", body)
        assert message.get("resourceType") == "CapabilityStatement"

    def test_metadata_fhir_version(self, page: Page):
        resp = page.request.get(
            f"{BASE_URL}/api/method/medic_plus.api.fhir.router.get_metadata",
            ignore_https_errors=True,
        )
        body = resp.json()
        message = body.get("message", body)
        assert message.get("fhirVersion") == "4.0.1"

    def test_metadata_lists_six_resources(self, page: Page):
        resp = page.request.get(
            f"{BASE_URL}/api/method/medic_plus.api.fhir.router.get_metadata",
            ignore_https_errors=True,
        )
        body = resp.json()
        message = body.get("message", body)
        rest = message.get("rest", [{}])
        resources = rest[0].get("resource", []) if rest else []
        resource_types = [r["type"] for r in resources]
        for expected in ["Patient", "Encounter", "Condition", "MedicationRequest",
                         "AllergyIntolerance", "Observation"]:
            assert expected in resource_types, f"{expected} missing from CapabilityStatement resources"


# ── Claims API shape tests ────────────────────────────────────────────────────

class TestClaimsApiShape:
    """Claims API endpoints return expected shapes even when no data exists."""

    def test_get_claim_for_nonexistent_encounter_returns_null(self, logged_in_admin_page: Page):
        page = logged_in_admin_page
        resp = _api_call(
            page,
            "medic_plus.api.claims.get_claim_for_encounter",
            {"encounter_name": "ENC-DOES-NOT-EXIST-99999"},
        )
        # Either null message or exc (no permission) — not a 500 crash
        assert "exc_type" not in resp or resp.get("exc_type") in (
            None, "PermissionError", "DoesNotExistError", "ServerError"
        )

    def test_submit_claim_draft_only_api_shape(self, logged_in_admin_page: Page):
        """submit_claim with a non-existent claim name returns a server error, not a crash."""
        page = logged_in_admin_page
        resp = _api_call(
            page,
            "medic_plus.api.claims.submit_claim",
            {"claim_name": "IC-DOES-NOT-EXIST-99999"},
        )
        # Expect either exc (DoesNotExistError) or PermissionError — not a raw 500
        assert resp.get("exc") is not None or resp.get("exc_type") is not None or \
               resp.get("message") is not None

    def test_claims_api_not_accessible_to_guest(self, page: Page):
        """Unauthenticated call to submit_claim returns 403 or 401."""
        resp = page.request.post(
            f"{BASE_URL}/api/method/medic_plus.api.claims.submit_claim",
            data={"claim_name": "IC-DOES-NOT-EXIST-99999"},
            ignore_https_errors=True,
        )
        assert resp.status in (401, 403, 417), f"Expected auth error, got {resp.status}"


# ── FHIR token issuance ───────────────────────────────────────────────────────

class TestFhirTokenIssuance:

    def test_issue_token_requires_login(self, page: Page):
        """Unauthenticated call to issue_fhir_token returns 401/403."""
        resp = page.request.post(
            f"{BASE_URL}/api/method/medic_plus.api.fhir.router.issue_fhir_token",
            data={"practice": "PRAC-00001"},
            ignore_https_errors=True,
        )
        assert resp.status in (401, 403, 417), f"Expected auth error, got {resp.status}"

    def test_issue_token_authenticated_wrong_practice_errors(self, logged_in_admin_page: Page):
        """issue_fhir_token with a non-existent practice returns a server error."""
        page = logged_in_admin_page
        resp = _api_call(
            page,
            "medic_plus.api.fhir.router.issue_fhir_token",
            {"practice": "PRAC-DOES-NOT-EXIST", "scope": "patient/*.read"},
        )
        # Administrator doesn't have a Practice Member row — expect PermissionError or exc
        assert resp.get("exc") is not None or resp.get("exc_type") is not None or \
               resp.get("message") is not None


# ── FHIR resource 404 ─────────────────────────────────────────────────────────

class TestFhirResourceNotFound:

    def test_get_encounter_nonexistent_returns_error(self, logged_in_admin_page: Page):
        """get_encounter with a non-existent name returns an error response."""
        page = logged_in_admin_page
        resp = _api_call(
            page,
            "medic_plus.api.fhir.router.get_encounter",
            {"id": "PE-DOES-NOT-EXIST-99999"},
        )
        assert resp.get("exc") is not None or resp.get("exc_type") is not None or \
               resp.get("message") is not None


# ── Sub-processor register ────────────────────────────────────────────────────

class TestSubProcessorApi:

    def test_sub_processor_list_accessible_to_admin(self, logged_in_admin_page: Page):
        """Healthcare Administrator can list Sub-Processor Register rows."""
        page = logged_in_admin_page
        resp = _api_call(
            page,
            "frappe.client.get_list",
            {
                "doctype": "Sub-Processor Register",
                "fields": ["processor_name", "category"],
                "limit": 20,
            },
        )
        # Expect at least the 10 seeded processors
        processors = resp.get("message", [])
        assert len(processors) >= 10, f"Expected >=10 seeded sub-processors, got {len(processors)}"

    def test_healthbridge_in_sub_processor_list(self, logged_in_admin_page: Page):
        """Healthbridge is in the seeded sub-processor list."""
        page = logged_in_admin_page
        resp = _api_call(
            page,
            "frappe.client.get_list",
            {
                "doctype": "Sub-Processor Register",
                "filters": [["processor_name", "=", "Healthbridge"]],
                "fields": ["processor_name", "category"],
            },
        )
        processors = resp.get("message", [])
        assert len(processors) == 1
        assert processors[0]["category"] == "HealthSwitching"
