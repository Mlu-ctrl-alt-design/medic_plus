"""
Tests for medic_plus.api.daystar_health and supporting modules.

The Daystar Health SPA is served at /daystar-health and depends on:
- medic_plus.api.practice_resolver — resolves the active Practice for a user,
  raising PermissionError when no membership exists or the user is Guest.
- medic_plus.api.daystar_health (forthcoming) — whitelisted endpoints for the SPA.

All external calls (frappe.db, frappe.session) are mocked. No documents are
created in the database.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe


def setUpModule():
    """Bind frappe LocalProxy objects so mock patching works correctly.

    See test_data_access.setUpModule for the rationale: Python 3.14 + LocalProxy
    needs the ContextVar bound, and frappe.throw() needs cache.hget() and lang.
    """
    frappe.local.session = frappe._dict(user="test@example.test")
    frappe.local.conf = frappe._dict(developer_mode=0)
    frappe.local.flags = frappe._dict()
    frappe.local.lang = "en"
    frappe.local.message_log = []
    frappe.local.error_log = []
    frappe.local.debug_log = []
    frappe.local.response = frappe._dict()

    cache_mock = MagicMock()
    cache_mock.hget.return_value = {}
    frappe.cache = cache_mock

    # frappe.db is a LocalProxy backed by a ContextVar. Bind it with a MagicMock
    # so per-test patch.object(...) calls can introspect it without RuntimeError.
    frappe.local.db = MagicMock()


class TestPracticeResolver(unittest.TestCase):
    """Behavior tests for practice_resolver.get_active_practice.

    The resolver is the single source of truth for "which Practice does this user
    belong to" across all Daystar Health endpoints. Every behavior here describes
    a contract callers rely on; implementation detail (which doctype it queries,
    which field it reads) is intentionally not asserted.
    """

    def _import(self):
        from medic_plus.api import practice_resolver
        return practice_resolver

    def test_returns_practice_for_member(self):
        """Given a user with a Practice Member row, the resolver returns the
        Practice name."""
        m = self._import()
        with patch("medic_plus.api.practice_resolver.frappe.db.get_value",
                   return_value="PRAC-00001") as gv:
            result = m.get_active_practice(user="doctor@example.test")
        self.assertEqual(result, "PRAC-00001")
        gv.assert_called_once()

    def test_raises_for_user_with_no_practice_membership(self):
        """A user without a Practice Member row cannot reach Daystar Health
        data. The resolver raises PermissionError so callers can surface the
        no-practice error card without leaking which Practices exist."""
        m = self._import()
        with patch("medic_plus.api.practice_resolver.frappe.db.get_value",
                   return_value=None):
            with self.assertRaises(frappe.PermissionError):
                m.get_active_practice(user="orphan@example.test")

    def test_raises_for_guest(self):
        """Guest users are anonymous visitors. They never have a Practice
        Member row, but we reject them before the database query so an
        anonymous visit cannot exfiltrate practice membership state."""
        m = self._import()
        with patch("medic_plus.api.practice_resolver.frappe.db.get_value") as gv:
            with self.assertRaises(frappe.PermissionError):
                m.get_active_practice(user="Guest")
        gv.assert_not_called()


class TestDashboardFormatHelper(unittest.TestCase):
    """Behavior tests for dashboard_aggregator._format_dashboard.

    This is the pure-data-shaping helper: it takes already-fetched rows and
    counts and returns the dashboard payload. No DB, no session, no
    frappe.utils. Testing it in isolation gives us fast, focused coverage of
    the interesting transformation rules (capping, day-series shaping,
    breakdown labelling, greeting personalisation).
    """

    def _import(self):
        from medic_plus.api import dashboard_aggregator
        return dashboard_aggregator

    def _empty_inputs(self):
        """Default zero-state input the helper accepts. Tests override only
        the keys they care about, keeping each test focused on one rule."""
        return {
            "user_first_name": "",
            "today_appointments": [],
            "active_patient_count": 0,
            "outstanding_lab_count": 0,
            "weekly_encounter_counts": {},
            "recent_patient_rows": [],
            "view_full_schedule_url": "/app/patient-appointment",
            "today_label": "Wednesday, April 29",
        }

    def test_greeting_uses_user_first_name(self):
        """The greeting addresses the logged-in practitioner by first name so
        the dashboard feels personal. When the first name is empty the greeting
        falls back to a generic phrasing rather than an awkward 'Good morning, '."""
        m = self._import()
        inputs = self._empty_inputs()
        inputs["user_first_name"] = "Sanjay"
        payload = m._format_dashboard(**inputs)
        self.assertIn("Sanjay", payload["greeting"])

    def test_week_volume_returns_seven_days_even_with_sparse_input(self):
        """The week-volume chart needs a stable 7-day x-axis. When some days
        had zero encounters the helper must fill them with 0 rather than
        skipping them — otherwise the chart shifts left and labels lie."""
        m = self._import()
        inputs = self._empty_inputs()
        # Caller passes whatever counts they computed; the helper guarantees
        # there are exactly 7 day entries in the returned series.
        inputs["weekly_encounter_counts"] = {"Mon": 18, "Wed": 22}
        payload = m._format_dashboard(**inputs)
        self.assertEqual(len(payload["week_volume"]), 7)
        # And the days that had data are surfaced unchanged.
        by_day = {row["day"]: row["visits"] for row in payload["week_volume"]}
        self.assertEqual(by_day["Mon"], 18)
        self.assertEqual(by_day["Wed"], 22)
        # The missing days appear with 0, not as absent keys.
        for day in ("Tue", "Thu", "Fri", "Sat", "Sun"):
            self.assertEqual(by_day.get(day, "MISSING"), 0,
                             f"day {day} must default to 0, got {by_day.get(day, 'MISSING')}")

    def test_recent_patients_capped_at_six(self):
        """The 'Recently seen patients' table is a glance — six rows is the
        design limit. The helper must enforce it even if the caller hands in
        more rows, so future query tweaks can't accidentally bloat the table."""
        m = self._import()
        inputs = self._empty_inputs()
        # Twelve fictional rows; only the first six should survive.
        inputs["recent_patient_rows"] = [
            {"id": f"PAT-{i:03d}", "name": f"Patient {i}"} for i in range(12)
        ]
        payload = m._format_dashboard(**inputs)
        self.assertEqual(len(payload["recent_patients"]), 6)
        # The first-six order is preserved (caller is responsible for ordering).
        self.assertEqual(payload["recent_patients"][0]["id"], "PAT-000")
        self.assertEqual(payload["recent_patients"][5]["id"], "PAT-005")

    def test_today_appointments_kpi_counts_status_breakdown(self):
        """The Today's Appointments KPI shows the total plus a status breakdown
        so the doctor sees, at a glance, how many are confirmed vs still open.

        Patient Appointment uses Frappe Healthcare's real statuses
        (Confirmed / Open / Scheduled / No Show) — those are what the breakdown
        labels surface, not the mock's invented 'checked in / in room' which
        don't exist in the schema.
        """
        m = self._import()
        inputs = self._empty_inputs()
        inputs["today_appointments"] = [
            {"id": "A1", "status": "Confirmed", "time": "08:00", "duration": 30,
             "patient_id": "P1", "patient_name": "Alice", "reason": "Check-up",
             "practitioner": "Dr X"},
            {"id": "A2", "status": "Confirmed", "time": "09:00", "duration": 30,
             "patient_id": "P2", "patient_name": "Bob", "reason": "Follow-up",
             "practitioner": "Dr X"},
            {"id": "A3", "status": "Open", "time": "10:00", "duration": 30,
             "patient_id": "P3", "patient_name": "Carol", "reason": "Consult",
             "practitioner": "Dr Y"},
            {"id": "A4", "status": "Scheduled", "time": "11:00", "duration": 30,
             "patient_id": "P4", "patient_name": "Dan", "reason": "Vaccination",
             "practitioner": "Dr Y"},
        ]
        payload = m._format_dashboard(**inputs)
        kpi = payload["kpis"]["today_appointments"]
        self.assertEqual(kpi["value"], 4)
        # Breakdown surfaces the *real* statuses — at minimum we assert each
        # observed status is reflected in the breakdown count.
        self.assertEqual(kpi["breakdown"]["Confirmed"], 2)
        self.assertEqual(kpi["breakdown"]["Open"], 1)
        self.assertEqual(kpi["breakdown"]["Scheduled"], 1)


class TestGetDashboardEndpoint(unittest.TestCase):
    """Behavior tests for the whitelisted daystar_health.get_dashboard entry.

    The endpoint is intentionally a thin orchestrator: practice_resolver →
    DB reads → dashboard_aggregator → return. We test the contract: it must
    refuse callers without a Practice and produce the documented payload
    shape on success.
    """

    def _import(self):
        from medic_plus.api import daystar_health
        return daystar_health

    def test_rejects_user_with_no_practice(self):
        """A logged-in user without a Practice Member row gets PermissionError
        from the resolver and the endpoint surfaces it unchanged. The SPA
        translates that into the no-practice error card."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   side_effect=frappe.PermissionError("no practice")):
            with self.assertRaises(frappe.PermissionError):
                m.get_dashboard()

    def test_returns_documented_payload_shape_for_practice_user(self):
        """The dashboard contract: when a Practice user calls get_dashboard
        the endpoint returns a dict with greeting, kpis, today_schedule,
        week_volume, recent_patients, today_label, view_full_schedule_url.

        We mock build_dashboard rather than the DB so this stays an endpoint-
        level contract test — the aggregator's contents are covered by the
        format-helper tests above.
        """
        m = self._import()
        fake_payload = {
            "greeting": "Good morning, Dr. Aiyana",
            "today_label": "Wednesday, April 29",
            "kpis": {
                "today_appointments": {"value": 2, "breakdown": {"Confirmed": 2}},
                "active_patients": {"value": 41},
                "outstanding_labs": {"value": 5},
            },
            "today_schedule": [],
            "week_volume": [{"day": "Mon", "visits": 0}] * 7,
            "recent_patients": [],
            "view_full_schedule_url": "/app/patient-appointment",
        }
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.build_dashboard",
                   return_value=fake_payload) as bd:
            payload = m.get_dashboard()
        # The endpoint forwards the aggregator's output; spot-check the
        # documented top-level keys are present.
        for key in ("greeting", "kpis", "today_schedule", "week_volume",
                    "recent_patients", "view_full_schedule_url"):
            self.assertIn(key, payload, f"missing key: {key}")
        # And the aggregator was invoked with the resolved Practice (not None
        # or the user — orchestration contract).
        bd.assert_called_once()
        kwargs = bd.call_args.kwargs
        self.assertEqual(kwargs.get("practice"), "PRAC-00001")


class TestGetPatientDetailEndpoint(unittest.TestCase):
    """Behavior tests for the whitelisted daystar_health.get_patient_detail.

    The endpoint orchestrates: practice_resolver → cross-tenant guard
    (the requested patient must belong to the user's Practice) →
    build_patient_summary → return.
    """

    def _import(self):
        from medic_plus.api import daystar_health
        return daystar_health

    def test_rejects_user_with_no_practice(self):
        """No Practice Member → no patient detail. The SPA translates the
        PermissionError into the no-practice error card; we never even
        attempt the cross-tenant patient lookup."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   side_effect=frappe.PermissionError("no practice")):
            with self.assertRaises(frappe.PermissionError):
                m.get_patient_detail(patient="PAT-00001")

    def test_get_my_practitioner_profile_rejects_no_practice_user(self):
        """The profile screen requires a Practice context. A user without a
        Practice Member row gets PermissionError from the resolver — same
        no-practice path as every other Daystar Health endpoint."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   side_effect=frappe.PermissionError("no practice")):
            with self.assertRaises(frappe.PermissionError):
                m.get_my_practitioner_profile()

    def test_get_my_practitioner_profile_returns_user_and_practitioner_fields(self):
        """The profile payload joins the User core (name / email / phone) with
        the Healthcare Practitioner linked via the user's Practice Member row.
        Read-only this iteration — no editable fields, no Save affordance.
        Surfaces enough to render the design (first/last name, email, phone,
        specialty/department, HPCSA number, 2FA enabled state).
        """
        m = self._import()

        user_row = {
            "name": "doctor.a@example.test",
            "first_name": "Aiyana",
            "last_name": "Patel",
            "email": "doctor.a@example.test",
            "phone": "+27821234567",
            "user_image": "/files/doctor.jpg",
        }
        practitioner_row = {
            "name": "HLC-PRAC-2026-00118",
            "department": "Family Medicine",
            "custom_hpcsa_number": "MP123456",
            "custom_practice_number": "0123456",
        }

        # Three frappe.db.get_value calls in order:
        # 1. User row by email
        # 2. Practice Member.practitioner link to find the practitioner name
        # 3. Healthcare Practitioner row by name
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.frappe.session",
                   frappe._dict(user="doctor.a@example.test")), \
             patch("medic_plus.api.daystar_health.frappe.db.get_value",
                   side_effect=[user_row, "HLC-PRAC-2026-00118", practitioner_row]):
            payload = m.get_my_practitioner_profile()

        # Top-level keys describe the contract.
        self.assertIn("user", payload)
        self.assertIn("practitioner", payload)
        # User block carries the rendered fields.
        self.assertEqual(payload["user"]["first_name"], "Aiyana")
        self.assertEqual(payload["user"]["email"], "doctor.a@example.test")
        # 2FA state comes through at the top level as a boolean — the SPA
        # renders an enabled badge from this without calling Frappe again.
        # frappe.utils.user.user_has_2fa returns falsy for our mock setup.
        self.assertIn("two_factor_authentication", payload)
        # Practitioner block carries SA-specific fields.
        self.assertEqual(payload["practitioner"]["custom_hpcsa_number"], "MP123456")
        self.assertEqual(payload["practitioner"]["department"], "Family Medicine")

    def test_rejects_cross_tenant_patient_request(self):
        """A user signed into Practice A who requests a Patient that belongs
        to Practice B gets PermissionError — never the patient's data, never
        even a 'not found' that would confirm the patient exists. Distinct
        error from 'patient not found' so the caller can't probe Practice
        membership of arbitrary IDs."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.frappe.db.get_value",
                   return_value="PRAC-00002"):  # patient belongs elsewhere
            with self.assertRaises(frappe.PermissionError):
                m.get_patient_detail(patient="PAT-FROM-OTHER-PRACTICE")


class TestPatientPermissionQueryForDoctor(unittest.TestCase):
    """Behavior tests for the Patient PQC the Daystar Health patients-list
    screen relies on. The screen calls the REST resource API for Patient,
    which Frappe scopes via this PQC. We exercise the contract: a Doctor
    user signed into Practice A sees a query that filters to that Practice
    only — Practice B's patients are unreachable.
    """

    def _import(self):
        from medic_plus.api import permissions
        return permissions

    def test_query_restricts_doctor_to_their_own_practice(self):
        """The PQC returns a SQL fragment scoping `tabPatient`.`custom_practice`
        to the user's Practice. The patients list, which composes this fragment
        into its REST query, therefore can never expose another Practice's data."""
        m = self._import()
        # frappe.db.escape wraps strings in quotes; replicate that for the test.
        with patch("medic_plus.api.permissions._is_platform_admin", return_value=False), \
             patch("medic_plus.api.permissions.frappe.get_roles", return_value=["Doctor"]), \
             patch("medic_plus.api.permissions._get_user_practice", return_value="PRAC-00001"), \
             patch("medic_plus.api.permissions.frappe.db.escape", side_effect=lambda v: f"'{v}'"):
            condition = m.get_patient_permission_query(user="doctor.a@example.test")
        self.assertIn("custom_practice", condition)
        self.assertIn("PRAC-00001", condition)
        # The other practice is *not* in the condition — readers of the
        # condition (Frappe's query builder) cannot construct a query that
        # leaks it.
        self.assertNotIn("PRAC-00002", condition)

    def test_query_blocks_user_with_no_practice_membership(self):
        """A logged-in user who is not a platform admin, not a Patient, and
        has no Practice Member row is fenced off entirely — the PQC returns
        a tautology that matches no rows. This is the safety net behind the
        no-practice error card on the SPA."""
        m = self._import()
        with patch("medic_plus.api.permissions._is_platform_admin", return_value=False), \
             patch("medic_plus.api.permissions.frappe.get_roles", return_value=["System User"]), \
             patch("medic_plus.api.permissions._get_user_practice", return_value=None):
            condition = m.get_patient_permission_query(user="orphan@example.test")
        self.assertEqual(condition, "1=0")


class TestPatientSummaryFormatHelper(unittest.TestCase):
    """Behavior tests for patient_summary._format_patient_summary.

    The helper is a pure transformation: it accepts already-fetched rows and
    returns the patient detail composite payload. POPIA exclusion and per-tab
    caps are enforced here, so they're testable in isolation without DB or
    auth context.
    """

    def _import(self):
        from medic_plus.api import patient_summary
        return patient_summary

    def test_strips_custom_sa_id_number_from_patient_block(self):
        """The composite must never expose POPIA-protected fields. Even if
        the caller hands the helper a Patient row containing custom_sa_id_number,
        the field is stripped before serialisation. The detail screen has no
        unmask flow this iteration; the SA ID is simply unreachable."""
        m = self._import()
        patient_row = {
            "name": "PAT-00001",
            "patient_name": "Eleanor Chen",
            "dob": "1964-03-14",
            "sex": "Female",
            "mobile": "+27821234567",
            "email": "e.chen@example.test",
            "custom_sa_id_number": "6403140001088",
            "custom_practice": "PRAC-00001",
        }
        payload = m._format_patient_summary(
            patient_row=patient_row,
            visits=[], vitals=[], medications=[], labs=[], notes=[],
        )
        import json
        serialised = json.dumps(payload, default=str)
        self.assertNotIn("6403140001088", serialised,
                         "POPIA: SA ID value must never appear anywhere in the payload")
        self.assertNotIn("custom_sa_id_number", serialised,
                         "POPIA: the field key itself must not leak (would advertise a maskable field)")

    def test_per_tab_caps_enforced(self):
        """Each tab is capped at the design's load limit. Visits / Labs /
        Medications / Notes cap at 20; Vitals caps at 12 (the trend chart
        renders exactly 12 data points). Caps are enforced even when the
        caller hands in more rows — guards against future query tweaks
        accidentally bloating the payload."""
        m = self._import()
        # 30 of each — well over the caps.
        oversize = lambda kind: [{"id": f"{kind}-{i:03d}"} for i in range(30)]
        payload = m._format_patient_summary(
            patient_row={"name": "PAT-1"},
            visits=oversize("V"),
            vitals=oversize("VS"),
            medications=oversize("M"),
            labs=oversize("L"),
            notes=oversize("N"),
        )
        self.assertEqual(len(payload["visits"]), 20, "Visits cap must be 20")
        self.assertEqual(len(payload["vitals"]), 12, "Vitals cap must be 12 (trend chart length)")
        self.assertEqual(len(payload["medications"]), 20, "Medications cap must be 20")
        self.assertEqual(len(payload["labs"]), 20, "Labs cap must be 20")
        self.assertEqual(len(payload["notes"]), 20, "Notes cap must be 20")
        # The first 20 (or 12 for vitals) are preserved in order — caller is
        # responsible for ordering, helper doesn't reshuffle.
        self.assertEqual(payload["visits"][0]["id"], "V-000")
        self.assertEqual(payload["visits"][19]["id"], "V-019")
        self.assertEqual(payload["vitals"][0]["id"], "VS-000")
        self.assertEqual(payload["vitals"][11]["id"], "VS-011")


class TestFormatAppointmentsHelper(unittest.TestCase):
    """Behavior tests for daystar_health._format_appointments.

    Pure data-shaping helper: accepts already-fetched rows, returns
    SPA-ready dicts. No DB, no session. Tests cover field projection,
    date/time serialisation, and cross-tenant isolation (the helper
    never adds back the custom_practice field so it cannot leak tenancy
    info to the front-end).
    """

    def _import(self):
        from medic_plus.api import daystar_health
        return daystar_health

    def _sample_row(self, **overrides):
        base = {
            "name": "PA-00001",
            "appointment_date": "2026-05-01",
            "appointment_time": "09:00:00",
            "patient": "PAT-00001",
            "patient_name": "Alice Nkosi",
            "practitioner": "HLC-PRAC-2026-00001",
            "practitioner_name": "Dr. Aiyana Patel",
            "appointment_type": "Follow-up",
            "status": "Scheduled",
            "custom_practice": "PRAC-00001",
        }
        base.update(overrides)
        return base

    def test_returns_documented_keys_for_single_row(self):
        """Each shaped row must carry exactly the eight fields the SPA table
        columns map to. Extra DB fields (custom_practice, etc.) must be
        stripped so the payload can't leak tenancy context to the front-end."""
        m = self._import()
        result = m._format_appointments([self._sample_row()])
        self.assertEqual(len(result), 1)
        row = result[0]
        expected_keys = {
            "name", "appointment_date", "appointment_time",
            "patient", "patient_name",
            "practitioner", "practitioner_name",
            "appointment_type", "status",
        }
        self.assertEqual(set(row.keys()), expected_keys)
        self.assertNotIn("custom_practice", row,
                         "custom_practice must not leak into the SPA payload")

    def test_appointment_date_serialised_as_string(self):
        """The SPA renders appointment_date directly as text. The helper must
        coerce the value to str so Python date objects don't cause JSON
        serialisation errors and the table shows the ISO date string."""
        import datetime
        m = self._import()
        result = m._format_appointments([self._sample_row(appointment_date=datetime.date(2026, 5, 1))])
        self.assertEqual(result[0]["appointment_date"], "2026-05-01")

    def test_appointment_time_serialised_as_string(self):
        """appointment_time comes from Frappe as a timedelta. The helper coerces
        it to a str so the SPA's formatTime helper can split on ':' safely."""
        import datetime
        m = self._import()
        td = datetime.timedelta(hours=9, minutes=30)
        result = m._format_appointments([self._sample_row(appointment_time=td)])
        self.assertIsInstance(result[0]["appointment_time"], str)
        self.assertIn("9", result[0]["appointment_time"])

    def test_empty_input_returns_empty_list(self):
        """An empty row set produces an empty list — not None, not an error."""
        m = self._import()
        result = m._format_appointments([])
        self.assertEqual(result, [])

    def test_multiple_rows_preserved_in_order(self):
        """The helper must not reorder rows — the caller (frappe.get_all with
        order_by) is responsible for ordering. The helper only shapes."""
        m = self._import()
        rows = [self._sample_row(name=f"PA-{i:05d}", patient_name=f"Patient {i}") for i in range(5)]
        result = m._format_appointments(rows)
        self.assertEqual([r["name"] for r in result], [f"PA-{i:05d}" for i in range(5)])

    def test_none_values_coerced_to_empty_string_for_date_time(self):
        """When appointment_date or appointment_time is None (unscheduled slot),
        the helper coerces to '' so the front-end gets a predictable empty
        string rather than null/None which would crash the table renderer."""
        m = self._import()
        result = m._format_appointments([self._sample_row(appointment_date=None, appointment_time=None)])
        self.assertEqual(result[0]["appointment_date"], "")
        self.assertEqual(result[0]["appointment_time"], "")


class TestGetAppointmentsEndpoint(unittest.TestCase):
    """Behavior tests for the whitelisted daystar_health.get_appointments endpoint.

    The endpoint is a thin orchestrator: resolve practice → build filters →
    frappe.get_all → _format_appointments → return. We test the contract:
    reject callers without a Practice, honour date/status defaults, pass the
    practitioner filter through, and never expose another Practice's data.
    """

    def _import(self):
        from medic_plus.api import daystar_health
        return daystar_health

    def _fake_row(self, **overrides):
        base = {
            "name": "PA-00001",
            "appointment_date": "2026-04-30",
            "appointment_time": "10:00:00",
            "patient": "PAT-00001",
            "patient_name": "Bob Zulu",
            "practitioner": "HLC-PRAC-2026-00001",
            "practitioner_name": "Dr. Aiyana Patel",
            "appointment_type": "Consultation",
            "status": "Scheduled",
        }
        base.update(overrides)
        return base

    def test_rejects_user_with_no_practice(self):
        """A caller without a Practice Member row must never reach the DB.
        The resolver raises PermissionError and the endpoint surfaces it
        unchanged — same no-practice path as every other Daystar endpoint."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   side_effect=frappe.PermissionError("no practice")):
            with self.assertRaises(frappe.PermissionError):
                m.get_appointments()

    def test_returns_list_for_practice_user(self):
        """A Practice Member receives a list of appointment dicts. The list
        may be empty (no appointments in the window) or populated. We assert
        the return type and that the shaped keys are present."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.frappe.get_all",
                   return_value=[self._fake_row()]) as ga:
            result = m.get_appointments()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["patient"], "PAT-00001")
        # get_all was called with the practice filter — defence in depth beyond PQC.
        call_kwargs = ga.call_args.kwargs if ga.call_args.kwargs else ga.call_args[1]
        filters_used = call_kwargs.get("filters", {})
        self.assertEqual(filters_used.get("custom_practice"), "PRAC-00001")

    def test_default_status_filter_is_scheduled_and_open(self):
        """When no status filter is supplied, the endpoint restricts to
        Scheduled and Open appointments — the most useful default for a
        live schedule view."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.frappe.get_all",
                   return_value=[]) as ga:
            m.get_appointments()
        filters_used = ga.call_args.kwargs.get("filters", {}) if ga.call_args.kwargs else ga.call_args[1].get("filters", {})
        status_clause = filters_used.get("status")
        self.assertIsNotNone(status_clause, "status filter must always be set")
        status_list = status_clause[1] if isinstance(status_clause, list) else status_clause
        self.assertIn("Scheduled", status_list)
        self.assertIn("Open", status_list)

    def test_custom_status_filter_overrides_default(self):
        """When the caller supplies a status list, the endpoint uses it verbatim.
        This lets the SPA's status toggle buttons refetch with any combination."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.frappe.get_all",
                   return_value=[]) as ga:
            m.get_appointments(filters={"status": ["Closed", "Cancelled"]})
        filters_used = ga.call_args.kwargs.get("filters", {}) if ga.call_args.kwargs else ga.call_args[1].get("filters", {})
        status_clause = filters_used.get("status")
        status_list = status_clause[1] if isinstance(status_clause, list) else status_clause
        self.assertIn("Closed", status_list)
        self.assertIn("Cancelled", status_list)
        self.assertNotIn("Scheduled", status_list)

    def test_practitioner_filter_forwarded_when_supplied(self):
        """When the caller supplies a practitioner name, the endpoint adds it
        to the Frappe filters so only that practitioner's appointments are
        returned — used by the practitioner dropdown in the toolbar."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.frappe.get_all",
                   return_value=[]) as ga:
            m.get_appointments(filters={"practitioner": "HLC-PRAC-2026-00001"})
        filters_used = ga.call_args.kwargs.get("filters", {}) if ga.call_args.kwargs else ga.call_args[1].get("filters", {})
        self.assertEqual(filters_used.get("practitioner"), "HLC-PRAC-2026-00001")

    def test_practitioner_filter_absent_when_not_supplied(self):
        """When no practitioner filter is supplied, the Frappe filters must not
        include a practitioner key — it would otherwise match only records with
        practitioner=None, which is wrong."""
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.frappe.get_all",
                   return_value=[]) as ga:
            m.get_appointments()
        filters_used = ga.call_args.kwargs.get("filters", {}) if ga.call_args.kwargs else ga.call_args[1].get("filters", {})
        self.assertNotIn("practitioner", filters_used)

    def test_accepts_json_string_filters(self):
        """The Frappe whitelist layer sometimes delivers POST body values as
        JSON strings rather than parsed dicts. The endpoint accepts both forms
        so callers can safely pass filters as a JSON-encoded string."""
        import json
        m = self._import()
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value="PRAC-00001"), \
             patch("medic_plus.api.daystar_health.frappe.get_all",
                   return_value=[]):
            result = m.get_appointments(filters=json.dumps({"status": ["Open"]}))
        self.assertIsInstance(result, list)

    def test_cross_tenant_isolation_via_practice_filter(self):
        """The endpoint always scopes the query to the caller's Practice.
        Even if another Practice's appointments exist in the DB, the
        custom_practice filter ensures they are unreachable.

        We test this via the PQC contract: get_all is called with
        custom_practice = PRAC-00001, never with PRAC-00002. The PQC
        is a second line of defence; the explicit filter is first."""
        m = self._import()
        practice_a = "PRAC-00001"
        practice_b_row = self._fake_row(name="PA-99999", patient="PAT-99999")
        # Simulate: DB returns only practice-A rows (as it would with both the
        # explicit filter AND the PQC active). The endpoint must never loosen that.
        with patch("medic_plus.api.daystar_health.get_active_practice",
                   return_value=practice_a), \
             patch("medic_plus.api.daystar_health.frappe.get_all",
                   return_value=[self._fake_row()]) as ga:
            result = m.get_appointments()
        filters_used = ga.call_args.kwargs.get("filters", {}) if ga.call_args.kwargs else ga.call_args[1].get("filters", {})
        self.assertEqual(filters_used["custom_practice"], practice_a,
                         "Endpoint must always scope to the caller's Practice")
