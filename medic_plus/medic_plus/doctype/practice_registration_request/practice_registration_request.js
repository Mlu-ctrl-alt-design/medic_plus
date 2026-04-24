frappe.ui.form.on("Practice Registration Request", {
	refresh(frm) {
		if (frm.is_new()) return;

		const paid = frm.doc.payment_status === "Paid";
		const provisioned = Boolean(frm.doc.provisioned_practice);

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

		if (provisioned) {
			frm.add_custom_button(__("Open Practice"), () => {
				frappe.set_route("Form", "Practice", frm.doc.provisioned_practice);
			}, __("Actions"));
		}
	},
});
