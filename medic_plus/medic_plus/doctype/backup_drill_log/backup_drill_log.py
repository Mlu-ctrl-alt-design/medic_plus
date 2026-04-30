import frappe
from frappe.model.document import Document


class BackupDrillLog(Document):
    def before_cancel(self):
        frappe.throw("Backup Drill Log records cannot be cancelled.")

    def on_trash(self):
        frappe.throw("Backup Drill Log records cannot be deleted.")
