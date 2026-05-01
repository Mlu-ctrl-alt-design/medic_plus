"""Add custom_practice indexes to all tenant-scoped tables.

Idempotent: checks SHOW INDEX before issuing ALTER TABLE so re-running
this patch on an already-indexed database is safe.
"""

import frappe


def _has_index(table: str, column: str) -> bool:
	rows = frappe.db.sql(
		"SHOW INDEX FROM `{table}` WHERE Column_name = %s".format(table=table),
		(column,),
	)
	return len(rows) > 0


def _table_exists(table: str) -> bool:
	rows = frappe.db.sql(
		"SELECT 1 FROM information_schema.tables "
		"WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
		(table,),
	)
	return len(rows) > 0


def _column_exists(table: str, column: str) -> bool:
	rows = frappe.db.sql(
		"SELECT 1 FROM information_schema.columns "
		"WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s LIMIT 1",
		(table, column),
	)
	return len(rows) > 0


def _add_index(table: str, column: str, index_name: str | None = None) -> None:
	if not _table_exists(table):
		return
	if not _column_exists(table, column):
		# Child tables inherit scoping from their parent and don't carry
		# their own `custom_practice` column — skip them silently.
		return
	idx = index_name or column
	if _has_index(table, column):
		return
	frappe.db.sql(
		f"ALTER TABLE `{table}` ADD INDEX `{idx}` (`{column}`)"
	)


def execute() -> None:
	"""Add custom_practice indexes and targeted column indexes."""

	# custom_practice on all tenant-scoped tables
	practice_tables = [
		"tabPatient",
		"tabPatient Appointment",
		"tabPatient Encounter",
		"tabInpatient Record",
		"tabSick Note",
		"tabWarehouse",
		"tabStock Entry",
		"tabData Unmask Request",
		"tabClinical Access Log",
		"tabPatient Allergy",
		"tabPatient Chronic Condition",
		"tabPatient Identifier",
	]
	for table in practice_tables:
		_add_index(table, "custom_practice")

	# Additional targeted indexes for high-traffic query patterns
	_add_index("tabPatient Encounter", "appointment_type")
	_add_index("tabClinical Access Log", "patient")
	_add_index("tabClinical Access Log", "accessor_user")

	frappe.db.commit()
