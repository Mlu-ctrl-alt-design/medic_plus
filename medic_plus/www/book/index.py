import frappe


def get_context(context):
	slug = frappe.form_dict.get("practice") or ""
	context.slug = slug

	if not slug:
		context.practice = None
		context.practitioners = []
		return

	practice = frappe.db.get_value(
		"Practice",
		{"slug": slug, "is_active": 1},
		["name", "practice_name", "logo", "color", "phone", "email", "address"],
		as_dict=True,
	)
	context.practice = practice

	if not practice:
		context.practitioners = []
		return

	members = frappe.get_all(
		"Practice Member",
		filters={"practice": practice.name, "role": "Doctor"},
		pluck="practitioner",
	)
	practitioner_names = [m for m in members if m]

	if practitioner_names:
		context.practitioners = frappe.get_all(
			"Healthcare Practitioner",
			filters={"name": ("in", practitioner_names), "status": "Active"},
			fields=["name", "practitioner_name", "department", "image"],
		)
	else:
		context.practitioners = []
