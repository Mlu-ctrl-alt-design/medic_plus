frappe.pages["inpatient-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Inpatient Dashboard",
		single_column: true,
	});

	// ─── state ────────────────────────────────────────────────────────────────
	let ward_filter = "";
	let summary = {};
	let inpatients = [];

	// ─── toolbar ──────────────────────────────────────────────────────────────
	page.add_inner_button(__("Refresh"), () => load_all());
	page.add_inner_button(__("New Admission"), () =>
		frappe.new_doc("Inpatient Record")
	);

	// ─── layout ───────────────────────────────────────────────────────────────
	const container = $(`
		<div class="inpatient-dashboard container-fluid px-0 py-3">
			<div id="ipd-summary" class="row g-3 mb-4"></div>
			<div id="ipd-filter" class="mb-3"></div>
			<div id="ipd-table-wrap"></div>
		</div>
	`).appendTo(page.main);

	// ─── bootstrap ────────────────────────────────────────────────────────────
	load_all();

	// ─── data loading ─────────────────────────────────────────────────────────
	function load_all() {
		render_loading_cards();
		Promise.all([load_summary(), load_inpatients()]).then(() => {
			render_summary_cards();
			render_ward_filter();
			render_table();
		});
	}

	function load_summary() {
		return frappe
			.call({ method: "medic_plus.api.inpatient.get_inpatient_summary" })
			.then((r) => {
				summary = r.message || {};
			});
	}

	function load_inpatients() {
		return frappe
			.call({ method: "medic_plus.api.inpatient.get_current_inpatients" })
			.then((r) => {
				inpatients = r.message || [];
			});
	}

	// ─── summary cards ────────────────────────────────────────────────────────
	function render_loading_cards() {
		const cards_html = [
			{ label: "Current Inpatients", color: "#2563eb" },
			{ label: "Today's Admissions", color: "#16a34a" },
			{ label: "Expected Discharges", color: "#ea580c" },
			{ label: "Avg LOS (days)", color: "#9333ea" },
		]
			.map(
				(c) => `
			<div class="col-6 col-md-3">
				<div class="stat-card" style="border-left:4px solid ${c.color}">
					<div class="stat-label">${c.label}</div>
					<div class="stat-value text-muted">—</div>
				</div>
			</div>`
			)
			.join("");
		$("#ipd-summary").html(cards_html);
	}

	function render_summary_cards() {
		const cards = [
			{
				label: "Current Inpatients",
				value: summary.current_inpatients ?? 0,
				color: "#2563eb",
				icon: "users",
			},
			{
				label: "Today's Admissions",
				value: summary.todays_admissions ?? 0,
				color: "#16a34a",
				icon: "log-in",
			},
			{
				label: "Expected Discharges",
				value: summary.expected_discharges ?? 0,
				color: "#ea580c",
				icon: "log-out",
			},
			{
				label: "Avg LOS (days)",
				value: summary.avg_los_days ?? 0,
				color: "#9333ea",
				icon: "clock",
			},
		];

		const html = cards
			.map(
				(c) => `
			<div class="col-6 col-md-3">
				<div class="stat-card" style="border-left:4px solid ${c.color}">
					<div class="stat-label">${c.label}</div>
					<div class="stat-value" style="color:${c.color}">${c.value}</div>
				</div>
			</div>`
			)
			.join("");
		$("#ipd-summary").html(html);
	}

	// ─── ward filter ─────────────────────────────────────────────────────────
	function render_ward_filter() {
		const wards = [...new Set(inpatients.map((r) => r.current_ward).filter(Boolean))];

		if (!wards.length) {
			$("#ipd-filter").empty();
			return;
		}

		const buttons = [
			`<button class="btn btn-sm ${
				ward_filter === "" ? "btn-primary" : "btn-default"
			}" data-ward="">All Wards</button>`,
		]
			.concat(
				wards.map(
					(w) =>
						`<button class="btn btn-sm ${
							ward_filter === w ? "btn-primary" : "btn-default"
						} ms-1" data-ward="${frappe.utils.escape_html(w)}">${frappe.utils.escape_html(w)}</button>`
				)
			)
			.join("");

		$("#ipd-filter").html(
			`<div class="d-flex align-items-center gap-2">
				<span class="text-muted small me-2">Filter by ward:</span>
				${buttons}
			</div>`
		);

		$("#ipd-filter").off("click", "[data-ward]").on("click", "[data-ward]", function () {
			ward_filter = $(this).data("ward");
			render_ward_filter();
			render_table();
		});
	}

	// ─── inpatient table ─────────────────────────────────────────────────────
	function render_table() {
		const rows = ward_filter
			? inpatients.filter((r) => r.current_ward === ward_filter)
			: inpatients;

		if (!rows.length) {
			$("#ipd-table-wrap").html(
				`<div class="text-center text-muted py-5">
					<i class="fa fa-bed fa-2x mb-2"></i>
					<p>No current inpatients${ward_filter ? " in this ward" : ""}.</p>
				</div>`
			);
			return;
		}

		const tbody = rows
			.map((r) => {
				const status_color = {
					Admitted: "blue",
					"Admission Scheduled": "orange",
				}[r.status] || "gray";

				const los_badge =
					r.los_days > 7
						? `<span class="badge bg-danger">${r.los_days}d</span>`
						: `<span class="badge bg-secondary">${r.los_days}d</span>`;

				const exp_discharge = r.expected_discharge
					? frappe.datetime.str_to_user(r.expected_discharge)
					: "—";

				const overdue =
					r.expected_discharge &&
					frappe.datetime.get_diff(frappe.datetime.now_date(), r.expected_discharge) > 0;

				return `<tr>
					<td>
						<a href="/app/inpatient-record/${encodeURIComponent(r.name)}" target="_blank">
							${frappe.utils.escape_html(r.patient_name || r.patient)}
						</a>
						<br><small class="text-muted">${r.gender || ""}</small>
					</td>
					<td>${frappe.utils.escape_html(r.current_ward || "—")}</td>
					<td>${r.admitted_datetime ? frappe.datetime.str_to_user(r.admitted_datetime) : "—"}</td>
					<td class="text-center">${los_badge}</td>
					<td>${frappe.utils.escape_html(r.primary_practitioner || "—")}</td>
					<td class="${overdue ? "text-danger fw-bold" : ""}">${exp_discharge}</td>
					<td>
						<span class="indicator-pill ${status_color}">
							${frappe.utils.escape_html(r.status || "—")}
						</span>
					</td>
					<td>
						<a href="/app/inpatient-record/${encodeURIComponent(r.name)}"
						   class="btn btn-xs btn-default">View</a>
					</td>
				</tr>`;
			})
			.join("");

		const html = `
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead class="table-light">
						<tr>
							<th>Patient</th>
							<th>Ward / Service Unit</th>
							<th>Admitted</th>
							<th class="text-center">LOS</th>
							<th>Practitioner</th>
							<th>Exp. Discharge</th>
							<th>Status</th>
							<th></th>
						</tr>
					</thead>
					<tbody>${tbody}</tbody>
				</table>
			</div>
			<p class="text-muted small text-end">${rows.length} patient(s) shown</p>
		`;
		$("#ipd-table-wrap").html(html);
	}
};

// ─── page styles ──────────────────────────────────────────────────────────────
frappe.pages["inpatient-dashboard"].on_page_show = function () {
	if (!document.getElementById("ipd-styles")) {
		const style = document.createElement("style");
		style.id = "ipd-styles";
		style.textContent = `
			.inpatient-dashboard .stat-card {
				background: var(--card-bg, #fff);
				border-radius: 8px;
				padding: 16px 20px;
				box-shadow: 0 1px 4px rgba(0,0,0,.08);
			}
			.inpatient-dashboard .stat-label {
				font-size: 12px;
				text-transform: uppercase;
				letter-spacing: .5px;
				color: var(--text-muted);
				margin-bottom: 4px;
			}
			.inpatient-dashboard .stat-value {
				font-size: 28px;
				font-weight: 700;
				line-height: 1;
			}
			.inpatient-dashboard table th {
				font-size: 12px;
				text-transform: uppercase;
				letter-spacing: .4px;
			}
		`;
		document.head.appendChild(style);
	}
};
