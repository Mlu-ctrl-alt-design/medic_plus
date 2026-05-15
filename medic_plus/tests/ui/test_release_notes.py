"""
UI Tests: Release Notes "What's New" modal — Daystar Health SPA
================================================================

Behaviors tested:
  1. A user with an unseen published Release Note sees the modal on the
     daystar-health SPA after login.
  2. The modal renders the note's title, version badge, and body content.
  3. The get_unseen_release_notes endpoint returns the expected payload shape.
  4. Clicking "Got it" dismisses the modal.
  5. The dismissal is recorded server-side — reloading the SPA does not
     re-show the modal.
  6. A user who is already caught up (no unseen notes) sees no modal.

Fixtures init Frappe against the site declared in medic_plus/CLAUDE.md
(`medic-demo-staging.thedaystar.co.za`) — matching the existing UI suite's
conftest. Administrator has no Practice Member row by default, so each
fixture adds a temporary one (role=Admin) and tears it down, plus seeds /
resets the User.custom_release_notes_seen_at field the feature relies on.
"""

import re
import pytest
from playwright.sync_api import Page, expect

try:
    from conftest import BASE_URL, ADMIN_USER, ADMIN_PASS, RUN_TAG
except ImportError:
    BASE_URL = ""  # bench run-tests preloader path; tests run only under pytest.
    ADMIN_USER = ADMIN_PASS = RUN_TAG = ""

DAYSTAR_URL = f"{BASE_URL}/daystar-health"
SITE = "medic-demo-staging.thedaystar.co.za"
SEEN_FIELD = "custom_release_notes_seen_at"


# ── helpers ──────────────────────────────────────────────────────────────────

def _connect_frappe():
    import os
    os.chdir("/home/fruppa/frappe-bench/sites")
    import frappe
    frappe.init(site=SITE)
    frappe.connect()
    return frappe


def _make_practice_member(frappe, practice="PRAC-00001"):
    """Temporary Practice Member row so Administrator reaches the app shell
    (where the modal renders) instead of the no-practice card."""
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
    return member


def _login_as_admin(page: Page) -> None:
    page.goto(f"{BASE_URL}/login")
    page.locator("#login_email").fill(ADMIN_USER)
    page.locator("#login_password").fill(ADMIN_PASS)
    page.locator(".btn-login[type='submit']").click()
    page.wait_for_url(re.compile(r"/(app|desk)"), timeout=15_000)


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def release_note_env():
    """Administrator gains a Practice Member row plus one unseen, published
    Release Note. `seen_at` is backdated so the note counts as unseen."""
    frappe = _connect_frappe()
    member = _make_practice_member(frappe)
    note = frappe.get_doc({
        "doctype": "Release Note",
        "title": f"UI Test Release {RUN_TAG}",
        "version": "v9.9.9",
        "published_on": frappe.utils.today(),
        "is_published": 1,
        "body": f"<p>Automated UI test note {RUN_TAG}.</p>",
    })
    note.insert(ignore_permissions=True)
    frappe.db.set_value("User", "Administrator", SEEN_FIELD, "2020-01-01 00:00:00")
    frappe.db.commit()

    yield {"note_name": note.name, "title": note.title}

    frappe.delete_doc("Release Note", note.name, ignore_permissions=True, force=True)
    frappe.delete_doc("Practice Member", member.name, ignore_permissions=True, force=True)
    frappe.db.set_value("User", "Administrator", SEEN_FIELD, None)
    frappe.db.commit()
    frappe.destroy()


@pytest.fixture
def caught_up_env():
    """Administrator has a Practice Member row but is fully caught up:
    `seen_at` is set to now, so no published note counts as unseen."""
    frappe = _connect_frappe()
    member = _make_practice_member(frappe)
    frappe.db.set_value("User", "Administrator", SEEN_FIELD, frappe.utils.now())
    frappe.db.commit()

    yield {}

    frappe.delete_doc("Practice Member", member.name, ignore_permissions=True, force=True)
    frappe.db.set_value("User", "Administrator", SEEN_FIELD, None)
    frappe.db.commit()
    frappe.destroy()


# ── tests ────────────────────────────────────────────────────────────────────

class TestReleaseNotesModalAppears:
    """An unseen published Release Note surfaces as a modal on the SPA."""

    def test_modal_shows_on_login_with_unseen_note(self, release_note_env, page: Page):
        _login_as_admin(page)
        page.goto(DAYSTAR_URL)
        expect(page.locator('[data-testid="dashboard-ready"]')).to_be_visible(timeout=20_000)

        expect(page.locator('[data-testid="release-notes-modal"]')).to_be_visible(timeout=15_000)
        title = page.locator('[data-testid="release-notes-title"]').first
        expect(title).to_have_text(release_note_env["title"])

    def test_modal_renders_version_badge_and_body(self, release_note_env, page: Page):
        _login_as_admin(page)
        page.goto(DAYSTAR_URL)
        expect(page.locator('[data-testid="release-notes-modal"]')).to_be_visible(timeout=20_000)

        entry = page.locator('[data-testid="release-notes-entry"]').first
        expect(entry).to_be_visible()
        expect(page.locator('[data-testid="release-notes-version"]').first).to_have_text("v9.9.9")
        # Body is rendered from the note's HTML and contains the run-unique tag.
        expect(page.locator('[data-testid="release-notes-body"]').first).to_contain_text(RUN_TAG)

    def test_unseen_endpoint_returns_expected_fields(self, release_note_env, page: Page):
        captured = {}

        def on_response(response):
            if "get_unseen_release_notes" in response.url and response.status == 200:
                try:
                    captured["json"] = response.json()
                except Exception:
                    pass

        page.on("response", on_response)
        _login_as_admin(page)
        page.goto(DAYSTAR_URL)
        expect(page.locator('[data-testid="release-notes-modal"]')).to_be_visible(timeout=20_000)

        payload = captured.get("json")
        assert payload is not None, "get_unseen_release_notes response was not captured"
        notes = payload.get("message", [])
        assert isinstance(notes, list) and notes, f"expected a non-empty notes list, got {notes!r}"
        note = next((n for n in notes if n.get("name") == release_note_env["note_name"]), None)
        assert note is not None, "the seeded release note was not in the payload"
        for key in ("name", "title", "version", "body", "published_on"):
            assert key in note, f"release note payload missing key: {key}"


class TestReleaseNotesDismissal:
    """Dismissing the modal closes it and the acknowledgement persists."""

    def test_dismiss_closes_modal(self, release_note_env, page: Page):
        _login_as_admin(page)
        page.goto(DAYSTAR_URL)
        modal = page.locator('[data-testid="release-notes-modal"]')
        expect(modal).to_be_visible(timeout=20_000)

        page.locator('[data-testid="release-notes-dismiss"]').click()
        expect(modal).not_to_be_visible(timeout=10_000)

    def test_dismissal_persists_across_reload(self, release_note_env, page: Page):
        _login_as_admin(page)
        page.goto(DAYSTAR_URL)
        modal = page.locator('[data-testid="release-notes-modal"]')
        expect(modal).to_be_visible(timeout=20_000)
        page.locator('[data-testid="release-notes-dismiss"]').click()
        expect(modal).not_to_be_visible(timeout=10_000)

        # Reload: the dismissal was recorded server-side, so the modal stays gone.
        page.goto(DAYSTAR_URL)
        expect(page.locator('[data-testid="dashboard-ready"]')).to_be_visible(timeout=20_000)
        page.wait_for_timeout(2_000)  # let the get_unseen fetch settle
        expect(modal).not_to_be_visible()


class TestReleaseNotesCaughtUp:
    """A user with no unseen notes never sees the modal."""

    def test_no_modal_when_already_seen(self, caught_up_env, page: Page):
        _login_as_admin(page)
        page.goto(DAYSTAR_URL)
        expect(page.locator('[data-testid="dashboard-ready"]')).to_be_visible(timeout=20_000)
        page.wait_for_timeout(2_000)  # let the get_unseen fetch settle
        expect(page.locator('[data-testid="release-notes-modal"]')).not_to_be_visible()
