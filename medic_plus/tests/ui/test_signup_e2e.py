"""
End-to-end signup funnel:
  /signup → OTP → create checkout → simulate webhook → /signup/complete → logged in

Yoco checkout is simulated via the dev-only `_test_mark_paid` endpoint
(gated on developer_mode). The test never hits real Yoco.

Prerequisites:
  - developer_mode=1 on the target site
  - mute_emails can stay 1 (completion URL is logged to Error Log in dev mode)
"""

import re
import time
import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL, RUN_TAG, ADMIN_USER, ADMIN_PASS, _frappe_login


EMAIL = f"e2e.signup.{RUN_TAG}@medic-ui-test.local"
PRACTICE_NAME = f"E2E Practice {RUN_TAG}"
PASSWORD = "T3stPassw0rd!"
# SA mobile format: 10 digits, prefix must be a real cell network code
# (082 = Vodacom, valid). RUN_TAG provides 6 unique digits — pad to 10 with
# a suffix so each pytest invocation produces a unique User.mobile_no
# (which has a unique index that survives our PRR cleanup).
MOBILE = f"082{RUN_TAG}1"


def test_signup_funnel_e2e(page: Page):
    # Step 1: fill out the form
    page.goto(f"{BASE_URL}/signup")
    page.locator('input[name="practice_name"]').fill(PRACTICE_NAME)
    page.locator('input[name="full_name"]').fill(f"E2E Tester {RUN_TAG}")
    page.locator('input[name="email"]').fill(EMAIL)
    page.locator('input[name="mobile"]').fill(MOBILE)
    # HPCSA: 4-8 digits
    page.locator('input[name="hpcsa_number"]').fill(f"{RUN_TAG[-5:].zfill(5)}")
    # Practice number: exactly 7 digits
    page.locator('input[name="practice_number"]').fill(f"{RUN_TAG[-6:].zfill(6)}0")
    page.get_by_role("button", name=re.compile("send.*code|next|continue|verify|get code", re.I)).first.click()

    # Step 2: OTP field visible; fetch dev OTP from the response
    expect(page.locator("body")).to_contain_text(re.compile("code|otp|verif", re.I), timeout=15_000)
    dev_otp_el = page.locator("[data-dev-otp]")
    expect(dev_otp_el).to_be_visible(timeout=10_000)
    otp = dev_otp_el.inner_text().strip()
    assert re.fullmatch(r"\d{6}", otp), f"expected 6-digit OTP, got {otp!r}"

    # Type each OTP digit through the first input — the page's auto-advance
    # handler then walks focus across the remaining 5 inputs. (Filling each
    # input separately races with the auto-focus handler and drops digits.)
    page.locator('#otp-input input[data-otp="0"]').focus()
    page.keyboard.type(otp, delay=20)
    page.get_by_role("button", name=re.compile("verify", re.I)).first.click()

    # Step 3: payment card — request_name exposed on window.__mpReq.
    page.wait_for_function("() => !!window.__mpReq", timeout=15_000)
    expect(page.locator("#step-3.active")).to_be_visible(timeout=5_000)
    request_name = page.evaluate("window.__mpReq")
    assert request_name, "window.__mpReq was not set"

    # Simulate the webhook instead of going through Yoco
    resp = page.request.post(
        f"{BASE_URL}/api/method/medic_plus.api.signup._test_mark_paid",
        data={"request_name": request_name},
    )
    assert resp.ok, f"_test_mark_paid failed: {resp.status} {resp.text()}"

    # Retrieve the completion URL from the Error Log (written in developer_mode)
    completion_url = _fetch_completion_url(page, EMAIL)

    # Visit it, set password, confirm auto-login. Generous timeout because
    # frappe-web.bundle is large and the page's verify call only fires once
    # frappe.call is defined (gated by whenFrappeReady in complete.html).
    page.goto(completion_url)
    page.wait_for_selector(
        "#form-block:not([style*='display:none'])",
        timeout=45_000, state="visible",
    )
    page.locator('input[name="password"]').fill(PASSWORD)
    page.locator('input[name="confirm_password"]').fill(PASSWORD)
    page.get_by_role("button", name=re.compile("set password|activate|log in", re.I)).first.click()

    # /app/practice and /desk/practice are equivalent aliases for the Desk page;
    # which one Frappe lands on depends on the user's last-known prefix cookie.
    page.wait_for_url(re.compile(r".*/(app|desk)/practice.*"), timeout=30_000)
    expect(page).to_have_url(re.compile(r".*/(app|desk)/practice.*"))


def _fetch_completion_url(page: Page, email: str) -> str:
    """Poll the Error Log (via REST) for the DEV completion URL we logged.

    Uses an authenticated Administrator session via raw HTTP — the page's
    own context is Guest, which cannot read Error Log. The DEV completion
    URL lives in the body (`error` column) under a method/title of
    `[DEV] Completion URL for <email>`.
    """
    import http.cookiejar
    import json
    import ssl
    import urllib.parse
    import urllib.request

    jar = http.cookiejar.CookieJar()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=ctx),
    )

    def post(url, body):
        req = urllib.request.Request(
            url, urllib.parse.urlencode(body).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with opener.open(req) as resp:
            return json.loads(resp.read())

    def get(url):
        with opener.open(url) as resp:
            return json.loads(resp.read())

    # Authenticate as Administrator
    post(f"{BASE_URL}/api/method/login", {"usr": ADMIN_USER, "pwd": ADMIN_PASS})

    title_filter = json.dumps([["method", "=", f"[DEV] Completion URL for {email}"]])
    fields = json.dumps(["error"])
    qs = urllib.parse.urlencode({
        "doctype": "Error Log",
        "filters": title_filter,
        "fields": fields,
        "order_by": "creation desc",
        "limit_page_length": 1,
    })
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            data = get(f"{BASE_URL}/api/method/frappe.client.get_list?{qs}")
            rows = data.get("message") or []
            for row in rows:
                m = re.search(r"https?://\S+/signup/complete\?token=\S+", row.get("error", ""))
                if m:
                    return m.group(0)
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError(f"Completion URL not found in Error Log for {email}")
