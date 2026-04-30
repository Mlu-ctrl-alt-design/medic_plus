"""Playwright UI tests for Allergies + Conditions tabs and the
severe-allergy banner on the patient drawer (SA EMR Phase 1, #18).

Each test seeds the row it depends on directly via the live API
(/api/resource/Patient Allergy etc.) using the selfserve.test
session, so the assertion is deterministic regardless of demo-data
state. Cleanup deletes the seeded row in teardown.
"""

import json
import time
import pytest
from playwright.sync_api import Page, expect

try:
    from conftest import BASE_URL
except ImportError:
    BASE_URL = ""

DAYSTAR_URL = f"{BASE_URL}/daystar-health"
PRACTICE_USER = "selfserve.test@thedaystar.co.za"
PRACTICE_PASSWORD = "DaystarTest2026!"


def _login_practice_user(page: Page) -> str:
    """Log in and return the rotated csrf_token (needed for POST/DELETE)."""
    page.context.clear_cookies()
    page.goto(DAYSTAR_URL)
    page.locator('[data-testid="login-email"]').fill(PRACTICE_USER)
    page.locator('[data-testid="login-password"]').fill(PRACTICE_PASSWORD)
    page.locator('[data-testid="login-submit"]').click()
    expect(page.locator('[data-testid="nav-patients"]')).to_be_visible(timeout=15_000)
    # The SPA syncs the rotated csrf_token onto window.meridianApi.bootstrap.
    csrf = page.evaluate("() => (window.meridianApi && window.meridianApi.bootstrap && window.meridianApi.bootstrap.csrfToken) || ''")
    assert csrf, "csrfToken missing on window.meridianApi.bootstrap after login"
    return csrf


def _csrf_headers(csrf: str) -> dict:
    return {"X-Frappe-CSRF-Token": csrf, "Accept": "application/json"}


def _first_patient(page: Page) -> str:
    response = page.request.get(
        f"{BASE_URL}/api/resource/Patient",
        params={"limit_page_length": 1, "fields": json.dumps(["name"])},
    )
    assert response.ok, f"GET /api/resource/Patient failed: {response.status}"
    rows = response.json().get("data") or []
    assert rows, "No patients in the active practice — cannot run tab tests"
    return rows[0]["name"]


def _seed(page: Page, csrf: str, doctype: str, payload: dict) -> str:
    response = page.request.post(
        f"{BASE_URL}/api/resource/{doctype.replace(' ', '%20')}",
        data=payload,
        headers=_csrf_headers(csrf),
    )
    assert response.ok, f"POST /api/resource/{doctype} failed: {response.status} {response.text()}"
    return (response.json().get("data") or {}).get("name")


def _delete(page: Page, csrf: str, doctype: str, name: str) -> None:
    page.request.delete(
        f"{BASE_URL}/api/resource/{doctype.replace(' ', '%20')}/{name.replace(' ', '%20')}",
        headers=_csrf_headers(csrf),
    )


def _open_patient_drawer(page: Page, patient_id: str) -> None:
    page.goto(f"{DAYSTAR_URL}?drawer=patient&id={patient_id}")
    expect(page.locator('[data-testid="patient-detail-page"]')).to_be_visible(timeout=15_000)


class TestSevereAllergyBanner:
    def test_banner_shows_when_active_severe_allergy_exists(self, page: Page):
        csrf = _login_practice_user(page)
        patient_id = _first_patient(page)
        # Bust cache so the banner re-evaluates on the next drawer open.
        allergy_name = _seed(page, csrf, "Patient Allergy", {
            "patient": patient_id,
            "category": "Drug",
            "substance": f"Penicillin-{int(time.time() * 1000) % 100000}",
            "severity": "Severe",
            "status": "Active",
            "reaction": "Anaphylaxis",
        })
        try:
            _open_patient_drawer(page, patient_id)
            expect(page.locator('[data-testid="patient-severe-allergy-banner"]')).to_be_visible(timeout=10_000)
            expect(page.locator('[data-testid="patient-severe-allergy-banner"]')).to_contain_text("SEVERE ALLERGY")
        finally:
            _delete(page, csrf, "Patient Allergy", allergy_name)


class TestAllergiesTab:
    def test_tab_renders_seeded_row(self, page: Page):
        csrf = _login_practice_user(page)
        patient_id = _first_patient(page)
        substance = f"Aspirin-{int(time.time() * 1000) % 100000}"
        allergy_name = _seed(page, csrf, "Patient Allergy", {
            "patient": patient_id,
            "category": "Drug",
            "substance": substance,
            "severity": "Moderate",
            "status": "Active",
        })
        try:
            _open_patient_drawer(page, patient_id)
            page.locator('[data-testid="patient-tab-allergies"]').click()
            expect(page.locator('[data-testid="patient-tab-content-allergies"]')).to_be_visible()
            expect(page.locator('[data-testid="allergy-row"]').filter(has_text=substance)).to_be_visible(timeout=10_000)
        finally:
            _delete(page, csrf, "Patient Allergy", allergy_name)


class TestConditionsTab:
    def test_tab_renders_seeded_chronic_condition(self, page: Page):
        csrf = _login_practice_user(page)
        patient_id = _first_patient(page)
        # Need a Diagnosis row to link to. Reuse the first one available
        # or create a stub.
        diag_resp = page.request.get(
            f"{BASE_URL}/api/resource/Diagnosis",
            params={"limit_page_length": 1, "fields": json.dumps(["name"])},
        )
        diag_rows = diag_resp.json().get("data") or []
        if not diag_rows:
            # Practice users have no DocPerm on Diagnosis (it's a master
            # catalog seeded by an admin) — skip rather than fail.
            pytest.skip("No Diagnosis catalog rows on this site")
        diag_name = diag_rows[0]["name"]
        condition_name = _seed(page, csrf, "Patient Chronic Condition", {
            "patient": patient_id,
            "diagnosis": diag_name,
            "chronic_status": "Active",
            "started_on": "2024-01-01",
        })
        try:
            _open_patient_drawer(page, patient_id)
            page.locator('[data-testid="patient-tab-conditions"]').click()
            expect(page.locator('[data-testid="patient-tab-content-conditions"]')).to_be_visible()
            expect(page.locator('[data-testid="condition-row"]').filter(has_text=diag_name)).to_be_visible(timeout=10_000)
        finally:
            _delete(page, csrf, "Patient Chronic Condition", condition_name)


class TestICD10Picker:
    def test_picker_searches_seeded_codes(self, page: Page):
        csrf = _login_practice_user(page)
        # Smoke test the underlying endpoint; the React picker is a
        # thin wrapper around it.
        response = page.request.post(
            f"{BASE_URL}/api/method/medic_plus.api.daystar_health.search_icd10",
            data={"query": "diab", "limit": 5},
            headers=_csrf_headers(csrf),
        )
        assert response.ok, f"search_icd10 failed: {response.status}"
        rows = (response.json().get("message") or [])
        codes = [r["code"] for r in rows]
        assert "E10.9" in codes or "E11.9" in codes, f"expected diabetes codes; got {codes}"
