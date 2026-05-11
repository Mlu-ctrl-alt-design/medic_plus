frappe.query_reports["AI Acceptance Rate"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "practice",
			label: __("Practice"),
			fieldtype: "Link",
			options: "Practice",
		},
		{
			fieldname: "practitioner",
			label: __("Practitioner"),
			fieldtype: "Link",
			options: "Healthcare Practitioner",
		},
		{
			fieldname: "feature",
			label: __("Feature"),
			fieldtype: "Select",
			options: "\nnote_gen\nddx\nrx_check",
		},
	],
	onload(report) {
		report.page.add_inner_button(__("AI Inference Log"), function () {
			frappe.set_route("List", "AI Inference Log");
		});
	},
};
