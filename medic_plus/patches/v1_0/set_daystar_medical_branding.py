"""
Patch: set_daystar_medical_branding
Applied: 2026-04-09
Sets app_name and related branding fields to "Daystar Medical" in System Settings
and Website Settings.
"""

import frappe


def execute():
	# System Settings
	frappe.db.set_single_value("System Settings", "app_name", "Daystar Medical")
	frappe.db.set_single_value("System Settings", "otp_issuer_name", "Daystar Medical")

	# Website Settings
	frappe.db.set_single_value("Website Settings", "app_name", "Daystar Medical")
	frappe.db.set_single_value("Website Settings", "footer_powered", "Daystar Medical")

	frappe.db.commit()
