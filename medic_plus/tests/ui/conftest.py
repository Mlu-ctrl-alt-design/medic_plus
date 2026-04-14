"""
Pytest configuration and shared fixtures for Medic Plus UI tests.

Run with:
    cd /home/fruppa/frappe-bench
    env/bin/python -m pytest apps/medic_plus/medic_plus/tests/ui/ -v --headed
    env/bin/python -m pytest apps/medic_plus/medic_plus/tests/ui/ -v          # headless

Requires:
    env/bin/pip install playwright pytest-playwright
    env/bin/playwright install chromium
"""

import re
import time
import pytest
from playwright.sync_api import Page, expect

# ── Site configuration ────────────────────────────────────────────────────────

BASE_URL = "https://medic-demo-staging.thedaystar.co.za"
ADMIN_USER = "Administrator"
ADMIN_PASS = "admin"

# Unique suffix so parallel runs don't clash (epoch-based)
RUN_TAG = str(int(time.time()))[-6:]


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_context_args():
    """Extra context args: ignore self-signed cert on staging, generous timeouts."""
    return {"ignore_https_errors": True}


@pytest.fixture(autouse=True)
def set_default_timeout(page):
    """Apply a 90-second default timeout to every test page (Frappe loads many JS assets)."""
    page.set_default_timeout(90_000)
    page.set_default_navigation_timeout(90_000)


@pytest.fixture(scope="session")
def admin_api_session(playwright):
    """
    Reusable requests session authenticated as Administrator.
    Returned as a dict with `cookies` and a helper `call(method, **params)`.
    """
    import urllib.request, urllib.parse, json, http.cookiejar, ssl

    jar = http.cookiejar.CookieJar()
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=ssl_ctx),
    )

    def post(url, data: dict):
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with opener.open(req) as resp:
            return json.loads(resp.read())

    # Login
    post(f"{BASE_URL}/api/method/login", {"usr": ADMIN_USER, "pwd": ADMIN_PASS})

    def call(method: str, **params) -> dict:
        return post(f"{BASE_URL}/api/method/{method}", {"cmd": method, **params})

    return {"call": call, "opener": opener}


@pytest.fixture
def logged_in_admin_page(page: Page) -> Page:
    """Navigate to Frappe Desk already logged in as Administrator."""
    _frappe_login(page, ADMIN_USER, ADMIN_PASS)
    return page


def _frappe_login(page: Page, user: str, password: str) -> None:
    """Helper: perform Frappe Desk login."""
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("load")

    # Handle cases where we're already logged in
    if "/app" in page.url or "/desk" in page.url or "/app/" in page.url:
        return

    # Frappe login page has both a login form and a signup form.
    # Use the specific login field IDs and the .btn-login class on the submit button.
    page.locator("#login_email").fill(user)
    page.locator("#login_password").fill(password)
    page.locator(".btn-login[type='submit']").click()
    page.wait_for_url(re.compile(r"/(app|desk)"), timeout=15_000)
