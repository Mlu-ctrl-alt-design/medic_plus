"""
Shared format validators for signup / registration flows.

Single source of truth for:
  - HPCSA registration number:  profession prefix + digits
                                  (e.g. MP1234567, DP0123456)
  - SA practice/billing number:  7 digits
  - SA mobile number:            10 digits, leading 0; normalised to +27 form

Callable from whitelisted endpoints, DocType validate() hooks, or directly in tests.
"""

import re

import frappe
from frappe import _


#: HPCSA profession prefixes. 2–3 uppercase letters.
#: Source: Health Professions Council of South Africa register categories.
HPCSA_PREFIXES = frozenset({
	"MP",  # Medical Practitioner
	"DP",  # Dental Practitioner
	"PS",  # Psychologist
	"PM",  # Physiotherapist
	"OT",  # Occupational Therapist
	"DH",  # Dental Hygienist
	"DT",  # Dental Therapist
	"OP",  # Optometrist
	"AU",  # Audiologist
	"SP",  # Speech-Language Pathologist
	"DI",  # Dietician
	"RD",  # Radiographer
	"MT",  # Medical Technologist
	"ST",  # Student
})

_HPCSA_RE = re.compile(r"^([A-Z]{2,3})(\d{4,8})$")
_PRACTICE_RE = re.compile(r"^\d{7}$")
_SA_MOBILE_RE = re.compile(r"^0\d{9}$")


def validate_hpcsa_number(value: str) -> str:
	"""Normalise and validate an HPCSA registration number.

	Returns the canonical upper-cased form, e.g. "mp 1234567" → "MP1234567".
	Raises frappe.ValidationError on bad format or unknown prefix.
	"""
	if not value:
		frappe.throw(_("HPCSA registration number is required."), frappe.ValidationError)

	cleaned = re.sub(r"\s+", "", value).upper()
	match = _HPCSA_RE.match(cleaned)
	if not match:
		frappe.throw(
			_("HPCSA number must be a profession prefix followed by digits, e.g. MP1234567."),
			frappe.ValidationError,
		)

	prefix = match.group(1)
	if prefix not in HPCSA_PREFIXES:
		frappe.throw(
			_("Unknown HPCSA profession prefix '{0}'.").format(prefix),
			frappe.ValidationError,
		)

	return cleaned


def validate_practice_number(value: str) -> str:
	"""Validate a 7-digit SA practice/billing number.

	Returns the cleaned value. Raises frappe.ValidationError on bad format.
	"""
	if not value:
		frappe.throw(_("Practice number is required."), frappe.ValidationError)

	cleaned = re.sub(r"\s+", "", value)
	if not _PRACTICE_RE.match(cleaned):
		frappe.throw(
			_("Practice number must be exactly 7 digits."),
			frappe.ValidationError,
		)
	return cleaned


def validate_sa_mobile(value: str) -> str:
	"""Validate and normalise a South African mobile number.

	Accepts `0821234567`, `+27821234567`, `27821234567`, `0027821234567`,
	or any of the above with spaces/dashes/parentheses.

	Returns the canonical E.164 form `+27821234567` — required by Frappe's
	`Phone` fieldtype and by Twilio SMS/WhatsApp delivery.
	Raises frappe.ValidationError on bad format.
	"""
	if not value:
		frappe.throw(_("Mobile number is required."), frappe.ValidationError)

	digits = re.sub(r"[^\d]", "", value)

	if digits.startswith("0027") and len(digits) == 13:
		digits = "0" + digits[4:]
	elif digits.startswith("27") and len(digits) == 11:
		digits = "0" + digits[2:]

	if not _SA_MOBILE_RE.match(digits):
		frappe.throw(
			_("Mobile number must be 10 digits starting with 0 (e.g. 0821234567)."),
			frappe.ValidationError,
		)
	return "+27" + digits[1:]
