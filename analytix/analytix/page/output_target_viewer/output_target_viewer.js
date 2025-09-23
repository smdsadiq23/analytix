// Viewer: Output vs Target
// Route: /app/output-target-viewer

frappe.pages["output-target-viewer"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Output vs Target",
		single_column: true,
	});
	const $root = $(wrapper).find(".layout-main-section");

	// ---------- CONFIG ----------
	const DOCTYPES = {
		physical_cell: "Physical Cell", // change if needed
		operation: "Operation",
	};
	const APPLY_COMPANY_FILTER = true;
	const COLORS = {
		output: "#96BE37", // bar
		target: "#ECAD4B", // line
	};

	// ---------- Controls ----------
	const fDate = page.add_field({
		fieldtype: "Date",
		fieldname: "date",
		label: "Date",
		default: frappe.datetime.get_today(),
		reqd: 1,
	});
	const fCell = page.add_field({
		fieldtype: "Link",
		fieldname: "physical_cell",
		label: "Physical Cell",
		options: DOCTYPES.physical_cell,
	});
	const fOp = page.add_field({
		fieldtype: "Link",
		fieldname: "operation",
		label: "Operation",
		options: DOCTYPES.operation,
	});

	// Optional: open table view with same filters
	const $tools = $(
		`<div class="d-flex align-items-center" style="gap:8px; margin:8px 0 12px;">
       <a class="btn btn-default btn-sm" data-action="open-report" href="javascript:void(0)">Open Report</a>
     </div>`
	).appendTo($root);

	// Company filter on link pickers (if applicable)
	const userCompany = frappe.defaults.get_default("Company");
	if (APPLY_COMPANY_FILTER && userCompany) {
		fCell.set_query && fCell.set_query(() => ({ filters: { company: userCompany } }));
		fOp.set_query && fOp.set_query(() => ({ filters: { company: userCompany } }));
	}

	// Prefill from URL
	const qp = frappe.utils.get_query_params();
	if (qp.date) fDate.set_value(qp.date);
	if (qp.physical_cell) fCell.set_value(qp.physical_cell);
	if (qp.operation) fOp.set_value(qp.operation);

	// Canvas
	const $canvas = $(`<canvas style="max-height:520px;"></canvas>`).appendTo($root);

	function loadChartJs() {
		return new Promise((resolve, reject) => {
			if (window.Chart) return resolve();
			frappe.require("https://cdn.jsdelivr.net/npm/chart.js", resolve);
			setTimeout(() => !window.Chart && reject(new Error("Chart.js failed to load")), 4000);
		});
	}

	function getFilters() {
		return {
			date: fDate.get_value(),
			physical_cell: fCell.get_value() || null,
			operation: fOp.get_value() || null,
		};
	}

	function debounce(fn, wait = 250) {
		let t;
		return (...a) => {
			clearTimeout(t);
			t = setTimeout(() => fn(...a), wait);
		};
	}

	async function run() {
		const filters = getFilters();
		if (!filters.date) {
			frappe.msgprint("Please select a Date.");
			return;
		}

		try {
			const resp = await frappe.call({
				method: "frappe.desk.query_report.run",
				args: { report_name: "Output vs Target", filters },
			});

			const result = (resp.message || {}).result || [];
			const labels = result.map((r) => r.hour_label || "");
			const output = result.map((r) => Number(r.output || 0));
			const target = result.map((r) => Number(r.target || 0));

			await loadChartJs();

			if ($canvas[0]._chart) $canvas[0]._chart.destroy();

			const ctx = $canvas[0].getContext("2d");
			$canvas[0]._chart = new Chart(ctx, {
				type: "bar",
				data: {
					labels,
					datasets: [
						{
							type: "bar",
							label: "Output (Qty)",
							data: output,
							backgroundColor: COLORS.output,
							borderColor: COLORS.output,
							borderWidth: 1,
						},
                        {
                        type: "line",
                        label: "Target (Qty)",
                        data: target,
                        borderColor: COLORS.target,
                        backgroundColor: COLORS.target,
                        borderWidth: 2,
                        pointRadius: 2,
                        tension: 0.25,
                        yAxisID: "y1"        // ← bind to secondary axis
                        },
					],
				},
				options: {
					responsive: true,
					interaction: { mode: "index", intersect: false },
					plugins: {
						legend: { position: "top" },
						title: { display: true, text: "Output vs Target (Hourly)" },
						tooltip: {
							callbacks: {
								label: (ctx) => {
									const v = Number(ctx.parsed.y ?? 0);
									const txt = Number.isFinite(v)
										? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
										: "0";
									return `${ctx.dataset.label}: ${txt}`;
								},
							},
						},
					},
					scales: {
						x: {
							title: { display: true, text: "Time (HH:00)" },
							ticks: { autoSkip: true, maxTicksLimit: 24 },
						},
						y: {
							title: { display: true, text: "Output Qty" },
							beginAtZero: true,
						},
						y1: {
							// secondary axis (right)
							position: "right",
							title: { display: true, text: "Target Qty" },
							beginAtZero: true,
							grid: { drawOnChartArea: false }, // keep grids from overlapping
						},
					},
				},
			});
		} catch (e) {
			frappe.msgprint({ title: "Chart", message: e.message || e, indicator: "red" });
		}
	}

	const runDebounced = debounce(run, 250);

	// Auto-run on filter change
	[fDate, fCell, fOp].forEach((ctrl) => {
		if (!ctrl) return;
		ctrl.$input && ctrl.$input.on("change", runDebounced);
		if (ctrl.df.fieldtype === "Link" && ctrl.$input) {
			ctrl.$input.on("awesomplete-selectcomplete", runDebounced);
		}
	});

	// Open Report with same filters
	$tools.on("click", '[data-action="open-report"]', function () {
		const f = getFilters();
		const params = $.param({
			date: f.date,
			physical_cell: f.physical_cell || "",
			operation: f.operation || "",
		});
		const url = frappe.urllib.get_full_url(
			`/app/query-report/${encodeURIComponent("Output vs Target")}?${params}`
		);
		window.open(url, "_blank", "noopener"); // safe new tab
	});

	// Initial render
	run();
};
