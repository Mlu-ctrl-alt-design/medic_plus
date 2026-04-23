frappe.ui.form.on("Sick Note", {
	refresh(frm) {
		if (frm.is_new()) {
			frm.tour
				.init({ tour_name: "Sick Note Form Tour" })
				.then(() => frm.tour.start());
		}
	},
});
