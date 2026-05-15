frappe.ui.form.on("Release Note", {
	refresh(frm) {
		if (frm.is_new()) {
			frm.tour
				.init({ tour_name: "Release Note Form Tour" })
				.then(() => frm.tour.start());
		}
	},
});
