"""
Calendar API — practitioner self-service schedule and time-block management.
All endpoints auto-resolve the practitioner from the logged-in user's Healthcare
Practitioner record.  Practice members who are not linked to a practitioner get a
clear error rather than a silent empty result.
"""

import frappe
from frappe import _
from frappe.utils import getdate, add_days


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_practice_member() -> str:
	"""Return the current user's practice name or raise PermissionError."""
	practice = frappe.db.get_value("Practice Member", {"user": frappe.session.user}, "practice")
	if not practice:
		frappe.throw(_("Access denied — not a practice member."), frappe.PermissionError)
	return practice


def _get_my_practitioner() -> str:
	"""Return the Healthcare Practitioner linked to the current user."""
	practitioner = frappe.db.get_value(
		"Healthcare Practitioner", {"user_id": frappe.session.user}, "name"
	)
	if not practitioner:
		frappe.throw(
			_("No Healthcare Practitioner record is linked to your account. "
			  "Ask your Practice Admin to set your User ID in your Practitioner profile."),
			frappe.ValidationError,
		)
	return practitioner


def _get_practitioner_schedule(practitioner: str) -> list:
	"""Return [{day, from_time, to_time}] for all active schedules."""
	try:
		prac_doc = frappe.get_doc("Healthcare Practitioner", practitioner)
	except Exception:
		return []

	slots = []
	for row in getattr(prac_doc, "practitioner_schedules", []) or []:
		if not row.schedule:
			continue
		try:
			sched = frappe.get_doc("Practitioner Schedule", row.schedule)
		except Exception:
			continue
		if sched.disabled:
			continue
		for slot in getattr(sched, "time_slots", []) or []:
			slots.append({
				"day": slot.day,
				"from_time": str(slot.from_time or ""),
				"to_time": str(slot.to_time or ""),
				"schedule_name": sched.schedule_name or sched.name,
				"doc_name": sched.name,
			})
	return slots


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_calendar_week(week_start: str) -> dict:
	"""Return appointments, time blocks, and recurring schedule for one week.

	week_start: ISO date string (YYYY-MM-DD) for the Monday of the desired week.
	"""
	_require_practice_member()
	practitioner = _get_my_practitioner()

	start = getdate(week_start)
	end = add_days(start, 6)

	appointments = frappe.get_all(
		"Patient Appointment",
		filters={
			"practitioner": practitioner,
			"appointment_date": ["between", [start, end]],
			"status": ["not in", ["Cancelled"]],
		},
		fields=[
			"name", "appointment_date", "appointment_time", "duration",
			"patient_name", "patient", "status", "appointment_type",
		],
		order_by="appointment_date asc, appointment_time asc",
	)

	# Blocks that overlap the week (start date falls within range)
	blocks = frappe.get_all(
		"Practice Time Block",
		filters={
			"practitioner": practitioner,
			"block_date": ["between", [start, end]],
		},
		fields=["name", "block_date", "end_date", "from_time", "to_time", "reason", "is_all_day"],
		order_by="block_date asc, from_time asc",
	)

	# Normalise time fields (Frappe returns timedelta objects)
	for b in blocks:
		b["from_time"] = str(b["from_time"] or "")
		b["to_time"] = str(b["to_time"] or "")

	for a in appointments:
		a["appointment_time"] = str(a["appointment_time"] or "")
		# Include encounter link if one exists for this appointment
		a["encounter"] = frappe.db.get_value(
			"Patient Encounter", {"appointment": a["name"]}, "name"
		)

	practitioner_name = frappe.db.get_value(
		"Healthcare Practitioner", practitioner, "practitioner_name"
	) or practitioner

	return {
		"week_start": str(start),
		"week_end": str(end),
		"practitioner": practitioner,
		"practitioner_name": practitioner_name,
		"appointments": appointments,
		"blocks": blocks,
		"schedule": _get_practitioner_schedule(practitioner),
	}


@frappe.whitelist()
def create_time_block(
	block_date: str,
	from_time: str = None,
	to_time: str = None,
	end_date: str = None,
	reason: str = None,
	is_all_day: int = 0,
) -> dict:
	"""Create a time block for the current practitioner."""
	practice = _require_practice_member()
	practitioner = _get_my_practitioner()

	block = frappe.get_doc({
		"doctype": "Practice Time Block",
		"practitioner": practitioner,
		"practice": practice,
		"block_date": block_date,
		"end_date": end_date or block_date,
		"from_time": from_time if not int(is_all_day) else None,
		"to_time": to_time if not int(is_all_day) else None,
		"reason": reason,
		"is_all_day": int(is_all_day),
	})
	block.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"name": block.name,
		"block_date": str(block.block_date),
		"from_time": str(block.from_time or ""),
		"to_time": str(block.to_time or ""),
		"reason": block.reason,
		"is_all_day": block.is_all_day,
	}


@frappe.whitelist()
def delete_time_block(block_name: str) -> dict:
	"""Delete a time block — only allowed by the owning practitioner."""
	_require_practice_member()
	practitioner = _get_my_practitioner()

	block = frappe.get_doc("Practice Time Block", block_name)
	if block.practitioner != practitioner:
		frappe.throw(_("Access denied."), frappe.PermissionError)

	block.delete()
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def get_my_practitioner_info() -> dict:
	"""Return practitioner name and whether a schedule exists — used on screen load."""
	_require_practice_member()

	prac = frappe.db.get_value(
		"Healthcare Practitioner",
		{"user_id": frappe.session.user},
		["name", "practitioner_name"],
		as_dict=True,
	)
	if not prac:
		return {"has_practitioner": False}

	has_schedule = bool(
		frappe.db.get_value(
			"Practitioner Service Unit Schedule", {"parent": prac["name"]}, "name"
		)
	)

	return {
		"has_practitioner": True,
		"practitioner": prac["name"],
		"practitioner_name": prac["practitioner_name"],
		"has_schedule": has_schedule,
		"desk_url": f"/app/healthcare-practitioner/{prac['name']}",
	}
