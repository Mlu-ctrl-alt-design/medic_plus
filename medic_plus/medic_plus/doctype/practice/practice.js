// Practice form: surface "Invite Staff" / "Bulk Invite Staff" / "Import Patients"
// buttons so owners can grow their practice without leaving the Practice doc.
frappe.ui.form.on("Practice", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Invite Staff"), function () {
			open_invite_dialog(frm);
		}, __("Actions"));

		frm.add_custom_button(__("Bulk Invite Staff (CSV)"), function () {
			open_bulk_invite_dialog(frm);
		}, __("Actions"));

		frm.add_custom_button(__("Import Patients"), function () {
			open_patient_import_dialog(frm);
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

const STAFF_CSV_TEMPLATE =
	"email,full_name,role,mobile,hpcsa_number,practice_number\n" +
	"jane.doe@example.com,Jane Doe,Receptionist,0821234567,,\n" +
	"dr.john@example.com,Dr John Smith,Doctor,0837654321,MP1234567,9876543\n";

function open_bulk_invite_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Bulk invite staff from CSV"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "instructions",
				options:
					'<p style="margin:0 0 8px;">Paste a CSV with columns: <code>email, full_name, role, mobile, hpcsa_number, practice_number</code>. ' +
					'Doctor rows must include HPCSA + practice number. Each row is processed independently — failed rows are reported, successful rows are committed.</p>' +
					'<p style="margin:0 0 12px;"><a id="mp-staff-csv-template" href="#" style="font-weight:600;">Download CSV template</a></p>',
			},
			{
				fieldtype: "Code",
				fieldname: "csv_data",
				label: __("CSV"),
				options: "Text",
				reqd: 1,
				default: STAFF_CSV_TEMPLATE,
			},
		],
		primary_action_label: __("Process invites"),
		primary_action(values) {
			d.set_primary_action(__("Processing…"), null);
			d.disable_primary_action();
			frappe.call({
				method: "medic_plus.api.invitations.invite_staff_bulk",
				args: { practice: frm.doc.name, csv_data: values.csv_data },
			}).then((r) => {
				const result = (r && r.message) || {};
				const ok = (result.succeeded || []).length;
				const bad = (result.failed || []).length;
				if (bad === 0) {
					frappe.show_alert({
						message: __("{0} invites sent.").format([ok]),
						indicator: "green",
					});
					d.hide();
					frm.reload_doc();
				} else {
					render_bulk_result(d, result);
					d.set_primary_action(__("Process invites"), () => d.get_primary_btn().click());
					d.enable_primary_action();
				}
			}).catch(() => {
				d.set_primary_action(__("Process invites"), () => d.get_primary_btn().click());
				d.enable_primary_action();
			});
		},
	});
	d.show();
	// Wire the template-download link
	d.$wrapper.find("#mp-staff-csv-template").on("click", function (e) {
		e.preventDefault();
		const blob = new Blob([STAFF_CSV_TEMPLATE], { type: "text/csv;charset=utf-8" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = "medic_plus_staff_invite_template.csv";
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	});
}

function render_bulk_result(dialog, result) {
	const ok = (result.succeeded || []).length;
	const bad = result.failed || [];
	const rows = bad
		.map(
			(r) =>
				`<tr><td style="padding:4px 8px;">${r.row}</td>` +
				`<td style="padding:4px 8px;">${frappe.utils.escape_html(r.email || "")}</td>` +
				`<td style="padding:4px 8px;color:#991b1b;">${frappe.utils.escape_html(r.error || "")}</td></tr>`
		)
		.join("");
	const html =
		`<div class="alert alert-warning" style="margin-bottom:8px;">` +
		`<strong>${ok}</strong> succeeded, <strong>${bad.length}</strong> failed. ` +
		`Fix the rows below and re-submit only the failed ones.` +
		`</div>` +
		`<div style="max-height:240px;overflow:auto;border:1px solid #e5e7eb;border-radius:6px;">` +
		`<table style="width:100%;border-collapse:collapse;font-size:.88rem;">` +
		`<thead style="background:#f9fafb;"><tr>` +
		`<th style="padding:6px 8px;text-align:left;">Row</th>` +
		`<th style="padding:6px 8px;text-align:left;">Email</th>` +
		`<th style="padding:6px 8px;text-align:left;">Error</th>` +
		`</tr></thead><tbody>${rows}</tbody></table></div>`;
	dialog.fields_dict.instructions.$wrapper.html(html);
}

function open_patient_import_dialog(frm) {
	const base = frappe.urllib.get_base_url();
	const d = new frappe.ui.Dialog({
		title: __("Import patients from CSV"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "instructions",
				options:
					'<p>Patient bulk import uses Frappe\'s standard <strong>Data Import</strong> tool. ' +
					'Each imported patient will be auto-scoped to <strong>' + frappe.utils.escape_html(frm.doc.name) + '</strong> ' +
					'via the <code>before_insert</code> hook — you don\'t need to include a <code>custom_practice</code> column.</p>' +
					'<p style="margin-top:14px;"><a class="btn btn-default btn-sm" target="_blank" rel="noopener" ' +
					'href="' + base + '/app/data-import/new?reference_doctype=Patient">Open Data Import →</a> &nbsp;' +
					'<a class="btn btn-link btn-sm" id="mp-patient-csv-template" href="#">Download starter CSV</a></p>' +
					'<p style="margin-top:8px;font-size:.85rem;color:#6b7280;">Tip: Export your existing patient list from your old system as CSV, then map columns in the Data Import wizard.</p>',
			},
		],
		primary_action_label: __("Close"),
		primary_action() { d.hide(); },
	});
	d.show();
	d.$wrapper.find("#mp-patient-csv-template").on("click", function (e) {
		e.preventDefault();
		const tmpl =
			"first_name,last_name,sex,dob,mobile,email\n" +
			"Jane,Doe,Female,1990-03-15,0821234567,jane@example.com\n";
		const blob = new Blob([tmpl], { type: "text/csv;charset=utf-8" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = "medic_plus_patient_import_template.csv";
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	});
}
