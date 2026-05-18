"""Patient Portal — Playwright UI tests.

Per medic_plus CLAUDE.md, every new feature must ship with Playwright tests.
Uses a module-scoped signed-in browser context so OTP rate limits don't bite.
"""
import os
import pytest
import frappe
from playwright.sync_api import Page


BASE_URL = os.getenv("MEDIC_BASE_URL", "https://medic-demo-staging.thedaystar.co.za")
SLUG = "ui-portal-test"
EMAIL = "ui-portal-test@example.com"


@pytest.fixture(scope="module")
def portal_fixtures():
	"""Provision a Practice + Patient + User for portal tests."""
	# Frappe writes logs relative to cwd; pin to sites/ so it finds the site
	os.chdir("/home/fruppa/frappe-bench/sites")
	frappe.init(site="medic-demo-staging.thedaystar.co.za")
	frappe.connect()

	if not frappe.db.exists("Practice", {"slug": SLUG}):
		frappe.get_doc({
			"doctype": "Practice", "practice_name": "UI Portal Test", "slug": SLUG,
			"is_active": 1, "email": "ui-portal-test@example.com",
		}).insert(ignore_permissions=True)
	practice = frappe.db.get_value("Practice", {"slug": SLUG}, "name")

	if not frappe.db.exists("Patient", {"email": EMAIL}):
		frappe.get_doc({
			"doctype": "Patient", "first_name": "Ui", "last_name": "Patient",
			"sex": "Female", "email": EMAIL, "custom_practice": practice,
			"status": "Active", "invite_user": 0,
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("User", {"email": EMAIL}):
		frappe.get_doc({
			"doctype": "User", "email": EMAIL, "first_name": "Ui",
			"enabled": 1, "user_type": "Website User", "send_welcome_email": 0,
			"roles": [{"role": "Patient"}],
		}).insert(ignore_permissions=True)

	# Clear OTP attempt counter so the suite isn't rate-limited from prior runs
	from medic_plus.api import patient_portal
	frappe.cache.delete_value(patient_portal._otp_attempt_key(SLUG, EMAIL))
	frappe.cache.delete_value(patient_portal._otp_verify_attempt_key(SLUG, EMAIL))
	frappe.db.commit()
	yield {"slug": SLUG, "email": EMAIL}


@pytest.fixture(scope="module")
def signed_in_state(browser, portal_fixtures):
	"""Sign in once and export storage state for reuse by all test pages."""
	from medic_plus.api import patient_portal
	context = browser.new_context(ignore_https_errors=True)
	page = context.new_page()
	page.goto(f"{BASE_URL}/portal/{SLUG}")
	page.wait_for_selector("input[type='email']", timeout=10000)
	page.fill("input[type='email']", EMAIL)
	page.click("button:has-text('Send code')")
	page.wait_for_selector("input[inputmode='numeric']", timeout=10000)
	code = frappe.cache.get_value(patient_portal._otp_cache_key(SLUG, EMAIL))
	assert code, "OTP not in cache — did request_portal_otp run?"
	page.fill("input[inputmode='numeric']", code)
	page.click("button:has-text('Sign in')")
	page.wait_for_selector("text=Welcome back", timeout=15000)
	state = context.storage_state()
	context.close()
	yield state


@pytest.fixture
def signed_in_page(browser, signed_in_state):
	context = browser.new_context(storage_state=signed_in_state, ignore_https_errors=True)
	page = context.new_page()
	yield page
	context.close()


def test_portal_login_page_renders(page: Page, portal_fixtures):
	page.goto(f"{BASE_URL}/portal/{SLUG}")
	page.wait_for_selector("input[type='email']", timeout=10000)
	page.wait_for_selector("text=Patient Portal", timeout=5000)


def test_portal_otp_flow_signs_user_in(signed_in_state):
	"""If this fixture loaded, the OTP flow succeeded end-to-end."""
	assert signed_in_state is not None
	# Should carry at least one cookie (sid)
	cookies = signed_in_state.get("cookies", [])
	assert any(c.get("name") == "sid" for c in cookies), "No sid cookie after OTP login"


def test_portal_tabs_navigate(signed_in_page: Page):
	signed_in_page.goto(f"{BASE_URL}/portal/{SLUG}?screen=appointments", wait_until="networkidle")
	signed_in_page.wait_for_selector("h1:has-text('Appointments')", timeout=15000)

	signed_in_page.goto(f"{BASE_URL}/portal/{SLUG}?screen=records", wait_until="networkidle")
	signed_in_page.wait_for_selector("h1:has-text('Records')", timeout=15000)

	signed_in_page.goto(f"{BASE_URL}/portal/{SLUG}?screen=profile", wait_until="networkidle")
	signed_in_page.wait_for_selector("h1:has-text('My profile')", timeout=15000)


def test_portal_profile_save(signed_in_page: Page):
	import time
	signed_in_page.goto(f"{BASE_URL}/portal/{SLUG}?screen=profile", wait_until="networkidle")
	signed_in_page.wait_for_selector("h1:has-text('My profile')", timeout=15000)
	# Unique per-run value — save() exits silently when payload is empty (no diff vs
	# current me), which would let a stale fixed value silently pass on a re-run.
	new_phone = "+27" + str(int(time.time()) % 1000000000).zfill(9)
	signed_in_page.locator("input[type='tel']").first.fill(new_phone)
	signed_in_page.click("button:has-text('Save changes')")
	signed_in_page.wait_for_selector("text=Saved", timeout=10000)


def test_portal_mobile_375_no_horizontal_scroll(signed_in_page: Page):
	signed_in_page.set_viewport_size({"width": 375, "height": 800})
	signed_in_page.goto(f"{BASE_URL}/portal/{SLUG}?screen=appointments")
	signed_in_page.wait_for_selector("h1:has-text('Appointments')", timeout=10000)
	has_h_scroll = signed_in_page.evaluate(
		"() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
	)
	assert not has_h_scroll, "Page has horizontal scroll at 375px"
