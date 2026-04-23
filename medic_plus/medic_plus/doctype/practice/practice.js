// Practice form: surface an "Invite Staff" button so owners can add doctors,
// receptionists, or co-admins without leaving the Practice doc.
frappe.ui.form.on("Practice", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Invite Staff"), function () {
			open_invite_dialog(frm);
		}, __("Actions"));
	},
});

function open_invite_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Invite a staff member"),
		fields: [
			{
				fieldtype: "Data",
				fieldname: "full_name",
				label: __("Full Name"),
				reqd: 1,
			},
			{
				fieldtype: "Data",
				fieldname: "email",
				label: __("Email"),
				reqd: 1,
				options: "Email",
			},
			{
				fieldtype: "Column Break",
			},
			{
				fieldtype: "Select",
				fieldname: "role",
				label: __("Role"),
				options: ["Doctor", "Receptionist", "Admin"].join("\n"),
				default: "Doctor",
				reqd: 1,
			},
			{
				fieldtype: "Data",
				fieldname: "mobile",
				label: __("Mobile (optional)"),
				description: __("SA format, e.g. 0821234567"),
			},
			{
				fieldtype: "Section Break",
				label: __("Doctor details (only required for Doctor role)"),
				depends_on: "eval:doc.role === 'Doctor'",
			},
			{
				fieldtype: "Data",
				fieldname: "hpcsa_number",
				label: __("HPCSA Number"),
				description: __("Include the prefix, e.g. MP1234567."),
				depends_on: "eval:doc.role === 'Doctor'",
			},
			{
				fieldtype: "Data",
				fieldname: "practice_number",
				label: __("Practice Number"),
				description: __("7 digits."),
				depends_on: "eval:doc.role === 'Doctor'",
			},
		],
		primary_action_label: __("Send invite"),
		primary_action(values) {
			d.set_primary_action(__("Sending…"), null);
			d.disable_primary_action();
			frappe.call({
				method: "medic_plus.api.invitations.invite_staff",
				args: Object.assign({ practice: frm.doc.name }, values),
			}).then((r) => {
				const msg = (r && r.message && r.message.message) || __("Invite sent.");
				frappe.show_alert({ message: msg, indicator: "green" });
				d.hide();
				frm.reload_doc();
			}).catch(() => {
				// Frappe surfaces the error toast itself; just re-enable the button.
				d.set_primary_action(__("Send invite"), () => d.get_primary_btn().click());
				d.enable_primary_action();
			});
		},
	});
	d.show();
}
