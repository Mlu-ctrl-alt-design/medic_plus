import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now, today

from medic_plus.api.release_notes import get_unseen_release_notes, mark_release_notes_seen

SEEN_FIELD = "custom_release_notes_seen_at"


class TestReleaseNote(FrappeTestCase):
	def setUp(self):
		self.published = frappe.get_doc(
			{
				"doctype": "Release Note",
				"title": "Test Published Note",
				"version": "v9.9.9",
				"published_on": today(),
				"is_published": 1,
				"body": "<p>Hello world</p>",
			}
		).insert(ignore_permissions=True)
		self.draft = frappe.get_doc(
			{
				"doctype": "Release Note",
				"title": "Test Draft Note",
				"published_on": today(),
				"is_published": 0,
				"body": "<p>Not ready</p>",
			}
		).insert(ignore_permissions=True)

	def _seen_at(self, value):
		frappe.db.set_value("User", "Administrator", SEEN_FIELD, value)

	def test_unseen_includes_published_excludes_draft(self):
		self._seen_at(add_to_date(now(), days=-1))
		notes = get_unseen_release_notes()
		names = [n["name"] for n in notes]
		self.assertIn(self.published.name, names)
		self.assertNotIn(self.draft.name, names)

	def test_mark_seen_clears_modal(self):
		self._seen_at(add_to_date(now(), days=-1))
		self.assertTrue(get_unseen_release_notes())
		mark_release_notes_seen()
		self.assertFalse(get_unseen_release_notes())

	def test_null_seen_at_initializes_silently(self):
		self._seen_at(None)
		notes = get_unseen_release_notes()
		self.assertEqual(notes, [])
		self.assertTrue(frappe.db.get_value("User", "Administrator", SEEN_FIELD))
