"""Phase 1B (#25) — point existing ICD-10 Code Value rows at ICD-10-ZA.

The Phase 1 demo seed of 34 ICD-10 codes was registered under the
generic WHO `ICD-10` system. Phase 1B introduces SA-canonical
`ICD-10-ZA` as the system the SPA picker now queries via search_icd10.
This patch updates the 34 demo rows in place so they remain reachable
from the picker without re-importing the seed.

Idempotent — re-running on a database that has already been migrated
is a no-op (no rows match `code_system = 'ICD-10'`).
"""

import frappe


def execute() -> None:
	frappe.db.sql(
		"UPDATE `tabCode Value` SET code_system = 'ICD-10-ZA' "
		"WHERE code_system = 'ICD-10'"
	)
	frappe.db.commit()
