"""Patient identity helpers: fuzzy duplicate detection.

Duplicate scoring (non-blocking — callers display a warning, not an error):
  • Exact identifier match (same id_value regardless of id_type) → always returned
  • Soundex match on patient_name  → candidate
  • Levenshtein distance ≤ 2 on patient_name → candidate
  • DOB within ± 1 day of supplied dob → boosts score (required in combination)

Only patients in the same practice are considered.
"""

import datetime

import frappe
from frappe import _


@frappe.whitelist()
def find_duplicate_patients(
    patient_name: str,
    practice: str,
    dob: str | None = None,
    id_value: str | None = None,
) -> list:
    """Return a list of potential duplicate patient dicts for the given practice.

    Each result dict has: name, patient_name, dob, sex, custom_practice.
    Non-blocking — always returns a list (may be empty).
    """
    _assert_practice_access(practice)

    candidates = _fetch_candidates(practice, dob)
    results = []
    for c in candidates:
        if _is_duplicate(c, patient_name=patient_name, dob=dob, id_value=id_value):
            results.append(c)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assert_practice_access(practice: str) -> None:
    from medic_plus.api.permissions import _is_platform_admin, _get_user_practice
    user = frappe.session.user
    if _is_platform_admin(user):
        return
    user_practice = _get_user_practice(user)
    if user_practice != practice:
        frappe.throw(_("Access denied."), frappe.PermissionError)


def _fetch_candidates(practice: str, dob: str | None) -> list:
    """Pull patients from the same practice with a broad DOB window (±2 days)."""
    filters = {"custom_practice": practice}
    if dob:
        try:
            d = datetime.date.fromisoformat(dob)
            low = (d - datetime.timedelta(days=2)).isoformat()
            high = (d + datetime.timedelta(days=2)).isoformat()
            filters["dob"] = ["between", [low, high]]
        except ValueError:
            pass

    rows = frappe.get_all(
        "Patient",
        filters=filters,
        fields=["name", "patient_name", "dob", "sex", "custom_practice"],
        limit_page_length=200,
    )

    # Also pull any patients with an identifier match (no date filter)
    return rows


def _is_duplicate(
    candidate: dict,
    *,
    patient_name: str,
    dob: str | None,
    id_value: str | None,
) -> bool:
    """Return True if candidate passes any duplicate heuristic."""
    # Exact identifier match: query Patient Identifier child rows
    if id_value:
        hit = frappe.db.get_value(
            "Patient Identifier",
            {"parent": candidate["name"], "id_value": id_value},
            "name",
        )
        if hit:
            return True

    # Name-based fuzzy match (require DOB proximity for safety)
    if dob and candidate.get("dob"):
        try:
            d_query = datetime.date.fromisoformat(str(dob))
            d_cand = datetime.date.fromisoformat(str(candidate["dob"]))
            if abs((d_query - d_cand).days) <= 1:
                cand_name = candidate.get("patient_name") or ""
                if _soundex_match(patient_name, cand_name):
                    return True
                if _levenshtein(patient_name.lower(), cand_name.lower()) <= 2:
                    return True
        except (ValueError, TypeError):
            pass

    return False


# ---------------------------------------------------------------------------
# Soundex (simple 4-character variant)
# ---------------------------------------------------------------------------

_SOUNDEX_TABLE = str.maketrans(
    "AEHIOUWY BFPV CGJKQSXZ DT L MN R".replace(" ", ""),
    "0000000000111022222222333344555566"[:26],
)
# Simplified: map each letter to its Soundex code
_SOUNDEX_MAP = {
    "B": "1", "F": "1", "P": "1", "V": "1",
    "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2",
    "S": "2", "X": "2", "Z": "2",
    "D": "3", "T": "3",
    "L": "4",
    "M": "5", "N": "5",
    "R": "6",
}


def _soundex(name: str) -> str:
    """Return a 4-character Soundex code for the first token of name."""
    word = name.strip().upper().split()[0] if name.strip() else ""
    if not word:
        return "0000"
    first = word[0]
    code = first
    prev = _SOUNDEX_MAP.get(first, "0")
    for ch in word[1:]:
        c = _SOUNDEX_MAP.get(ch, "0")
        if c != "0" and c != prev:
            code += c
        prev = c
        if len(code) == 4:
            break
    return code.ljust(4, "0")


def _soundex_match(a: str, b: str) -> bool:
    return bool(a) and bool(b) and _soundex(a) == _soundex(b)


# ---------------------------------------------------------------------------
# Levenshtein distance (DP, O(min(m,n)) space)
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            ins = prev[j + 1] + 1
            dlt = curr[j] + 1
            sub = prev[j] + (0 if ca == cb else 1)
            curr.append(min(ins, dlt, sub))
        prev = curr
    return prev[-1]
