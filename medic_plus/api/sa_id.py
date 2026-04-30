"""South African ID number parser and checksum validator.

Algorithm (SA Dept of Home Affairs spec):
  1. Sum digits at 0-indexed positions 0, 2, 4, 6, 8, 10  → A
  2. Concatenate digits at positions 1, 3, 5, 7, 9, 11 → N; compute N × 2;
     sum the individual digits of that product             → B
  3. total = A + B
  4. check digit = (10 - total % 10) % 10
  5. Must equal id_number[12]

DOB encoding: YYMMDD at positions 0-5.
  • YY ≤ current_year_2digit → 2000 + YY
  • YY >  current_year_2digit → 1900 + YY

Sex encoding: 4-digit sequence at positions 6-9 (0000-4999 → Female, 5000-9999 → Male).
"""

import datetime
import re

import frappe
from frappe import _

_SAID_RE = re.compile(r"^\d{13}$")


def validate_said(id_number: str) -> None:
    """Validate an SA ID number; raises frappe.ValidationError on failure."""
    if not id_number or not _SAID_RE.match(id_number):
        frappe.throw(
            _("SA ID number must be exactly 13 digits (got {0!r}).").format(id_number),
            frappe.ValidationError,
        )
    if not _checksum_ok(id_number):
        frappe.throw(
            _("SA ID number '{0}' has an invalid checksum.").format(id_number),
            frappe.ValidationError,
        )


def parse_said(id_number: str) -> dict:
    """Parse DOB (YYYY-MM-DD string) and sex from a well-formed SA ID.

    Does NOT validate — call validate_said() first.
    Returns: {"dob": "YYYY-MM-DD", "sex": "Male" | "Female"}
    """
    yy = int(id_number[:2])
    mm = id_number[2:4]
    dd = id_number[4:6]
    current_2digit = datetime.date.today().year % 100
    year = 2000 + yy if yy <= current_2digit else 1900 + yy

    gender_seq = int(id_number[6:10])
    sex = "Male" if gender_seq >= 5000 else "Female"

    return {"dob": f"{year}-{mm}-{dd}", "sex": sex}


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _checksum_ok(id_number: str) -> bool:
    odd_sum = sum(int(id_number[i]) for i in range(0, 12, 2))
    even_concat = "".join(id_number[i] for i in range(1, 12, 2))
    doubled = int(even_concat) * 2
    doubled_sum = sum(int(d) for d in str(doubled))
    total = odd_sum + doubled_sum
    expected = (10 - (total % 10)) % 10
    return expected == int(id_number[12])
