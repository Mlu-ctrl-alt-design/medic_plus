frappe.ui.form.on("Practice Registration Request", {
	refresh(frm) {
		if (frm.is_new()) return;

		const paid = frm.doc.payment_status === "Paid";
		const provisioned = Boolean(frm.doc.provisioned_practice);
		const isSystemManager = (frappe.user_roles || []).includes("System Manager");

		if (paid && !provisioned) {
			frm.add_custom_button(__("Force Provision"), async () => {
				const confirmed = await new Promise((resolve) => {
					frappe.confirm(
						__("Provision practice <b>{0}</b> now? This creates the Company, Practice, Practitioner, and Practice Member records.", [frm.doc.practice_name]),
						() => resolve(true),
						() => resolve(false),
					);
				});
				if (!confirmed) return;

				frappe.dom.freeze(__("Provisioning…"));
				try {
					const { message } = await frappe.call({
						method: "medic_plus.api.yoco.force_provision",
						args: { request_name: frm.doc.name },
					});
					frappe.show_alert({ message: message.message, indicator: "green" }, 7);
					frm.reload_doc();
				} finally {
					frappe.dom.unfreeze();
				}
			}, __("Actions"));
		}

		if (!paid && !provisioned && isSystemManager) {
			frm.add_custom_button(__("Mark Paid (Admin Override)"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Admin Payment Override"),
					fields: [
						{
							fieldtype: "HTML",
							options: `<div class="alert alert-warning">${
								__("Use this only when the customer has paid out-of-band (EFT, complimentary, demo) and a Yoco webhook will never arrive. The override is logged on this request's timeline.")
							}</div>`,
						},
						{
							label: __("Reason"),
							fieldname: "reason",
							fieldtype: "Small Text",
							description: __("E.g. \"EFT received 2026-05-09, ref 12345\" or \"Complimentary — internal demo\"."),
							reqd: 1,
						},
					],
					primary_action_label: __("Mark Paid + Provision"),
					primary_action: async (values) => {
						dialog.hide();
						frappe.dom.freeze(__("Provisioning…"));
						try {
							const { message } = await frappe.call({
								method: "medic_plus.api.yoco.admin_mark_paid_and_provision",
								args: {
									request_name: frm.doc.name,
									reason: values.reason,
								},
							});
							frappe.show_alert({ message: message.message, indicator: "green" }, 7);
							frm.reload_doc();
						} finally {
							frappe.dom.unfreeze();
						}
					},
				});
				dialog.show();
			}, __("Actions"));
		}

		if (provisioned) {
			frm.add_custom_button(__("Open Practice"), () => {
				frappe.set_route("Form", "Practice", frm.doc.provisioned_practice);
			}, __("Actions"));
		}
	},
});
