"""Drop the `Registration Request` DocType after orphan cleanup.

Two-stage drop:
  1. delete the DocType metadata via frappe.delete_doc (controller's on_trash
     normally also drops the table)
  2. fall back to an explicit DROP TABLE in case stage 1 left the table behind
     because the doctype source files were already deleted from disk before
     the patch ran (so the controller import failed silently)

Both stages are idempotent.
"""

import frappe


def execute():
	doctype_exists = frappe.db.exists("DocType", "Registration Request")
	if doctype_exists:
		remaining = frappe.db.count("Registration Request")
		if remaining:
			frappe.log_error(
				title="drop_registration_request_doctype aborted",
				message=f"{remaining} rows still exist — cleanup patch must run first.",
			)
			return
		frappe.delete_doc(
			"DocType", "Registration Request", force=1, ignore_permissions=True
		)

	# Belt-and-braces: ensure the underlying table is gone even if delete_doc
	# couldn't drop it (e.g. controller files already removed from disk).
	frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabRegistration Request`")
	frappe.db.commit()
