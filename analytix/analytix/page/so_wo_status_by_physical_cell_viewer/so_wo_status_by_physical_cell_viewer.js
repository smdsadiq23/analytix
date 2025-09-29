frappe.pages["so-wo-status-by-physical-cell-viewer"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "SO WO Status by Physical Cell",
		single_column: true,
	});

	const $root = $(wrapper).find(".layout-main-section");

	// ===== STYLES (same) =====
	$("#kpi-ms-overflow-fix").remove();
	$(`<style id="kpi-ms-overflow-fix">
	.page-form .frappe-control { min-width: 0; }
	.kpi-tabs { display: flex; border-bottom: 1px solid var(--border-color); background: #f9fafb; }
	.kpi-tab { padding: 12px 24px; cursor: pointer; font-weight: 600; color: #6b7280; border: none; background: transparent; }
	.kpi-tab.active { background: #96BE37; color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; }

	/* Sections */
	.kpi-section { margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; }
	.kpi-section h5 { margin: 0 0 16px 0; color: #333; font-size: 16px; }

	/* Filters */
	.kpi-filter-row { display: flex; gap: 16px; margin-bottom: 16px; align-items: center; }
	.kpi-filter-row .frappe-control { min-width: 200px; }
	.frappe-control[data-fieldname="so_date_range"],
	.frappe-control[data-fieldname="wo_date_range"] { min-width: 280px !important; }

	/* Cards */
	.kpi-card { border:1px solid var(--border-color,#e5e7eb); border-radius:8px; padding:12px; background:#fff; margin-bottom:16px; }
	.kpi-card h6 { margin:0 0 6px 0; color:var(--text-muted,#6b7280); font-weight:600; }
	.kpi-card canvas { width:100%; height:420px; max-height:420px; }

	/* Scrollable tables */
	.kpi-scrollable-table {
		max-height: 220px;
		overflow-y: auto;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		background: white;
	}
	.kpi-scrollable-table table {
		width: 100%;
		border-collapse: collapse;
	}
	.kpi-scrollable-table th {
		position: sticky;
		top: 0;
		background: #f9fafb;
		z-index: 10;
		padding: 8px;
		border: 1px solid #e5e7eb;
		text-align: left;
		font-weight: 600;
	}
	.kpi-scrollable-table td {
		padding: 8px;
		border: 1px solid #e5e7eb;
		text-align: left;
	}

	/* Details table */
	.kpi-details-table { 
		width: 100%; 
		border-collapse: collapse; 
		margin-top: 12px; 
	}
	.kpi-details-table td { 
		padding: 8px; 
		border: 1px solid #e5e7eb; 
		vertical-align: top; 
	}
	.kpi-details-table td:first-child { 
		font-weight: 600; 
		background: #f9fafb; 
		width: 40%; 
	}

	/* === Clear Button (generic; Link / Date / DateRange) === */
	.kpi-clear-host { position: relative !important; }
	/* inset the × by giving more right padding */
	.kpi-clear-btn {
	position: absolute; right: 16px; top: 50%; transform: translateY(-50%);
	line-height: 1; padding: 0 8px; border: 0; background: transparent;
	color: var(--gray-600); cursor: pointer; border-radius: 6px; z-index: 2;
	}
	.kpi-clear-btn:hover { background: var(--gray-100); }

	/* Colors */
	.completed { background: #96BE37; color: white; }
	.pending { background: #ECAD4B; color: black; }
	.rejected { background: #EF4444; color: white; }

	/* Responsive */
	@media (max-width: 1100px) {
		.kpi-filter-row { flex-direction: column; align-items: stretch; }
		.kpi-dashboard-grid { grid-template-columns: 1fr; }
	}

	.awesomplete {
		z-index: 1000 !important;
	}
	</style>`).appendTo(document.head);

	// ========== CLEAR BUTTON HELPER ==========
	// attachClearButton(field, onClear) — works for Link + DateRange (and Date)
	function attachClearButton(field, onClear) {
		if (!field || !field.$wrapper) return;
		const fname = field.df.fieldname;

		const $host = field.$wrapper.find(".control-input, .control-input-wrapper").first().length
			? field.$wrapper.find(".control-input, .control-input-wrapper").first()
			: field.$wrapper;
		$host.addClass("kpi-clear-host");

		const ensure = () => {
			// find live input (Awesomplete/DateRange can rebuild DOM)
			let $inp = $host.find("input.input-with-feedback").first();
			if (!$inp.length) $inp = $host.find("input").first();
			if (!$inp.length && field.$input) $inp = field.$input;
			if ($inp && $inp.length) $inp.addClass("kpi-clear-pad");

			let $btn = $host.find(`.kpi-clear-btn[data-for="${fname}"]`);
			if (!$btn.length) {
				$btn = $(
					`<button type="button" class="kpi-clear-btn" data-for="${fname}" title="Clear">×</button>`
				).appendTo($host);

				// use mousedown so it works even while the input is focused
				$btn.on("mousedown", async (e) => {
					e.preventDefault();

					// 1) Clear the model immediately
					try {
						if (field.df.fieldtype === "DateRange") {
							if (field.set_value) await field.set_value([]);
							if (field.parse_validate_and_set_in_model)
								field.parse_validate_and_set_in_model({
									from_date: "",
									to_date: "",
								});
						} else {
							if (field.set_value) await field.set_value("");
							if (field.parse_validate_and_set_in_model)
								field.parse_validate_and_set_in_model("");
						}
					} catch {}

					// 2) Clear visible inputs + fire events (no need to blur manually)
					$host
						.find("input")
						.val("")
						.trigger("input")
						.trigger("change")
						.trigger("awesomplete-selectcomplete");

					// 3) Control callback + external loader
					try {
						field.on_change && field.on_change();
					} catch {}
					try {
						onClear && onClear();
					} catch {}

					toggle();
				});
			}

			const hasValue = () => {
				try {
					const v = field.get_value ? field.get_value() : null;
					if (field.df.fieldtype === "DateRange") {
						if (Array.isArray(v)) return !!(v[0] || v[1]);
						if (v && typeof v === "object") return !!(v.from_date || v.to_date);
						return !!v;
					}
					if (v == null) return false;
					return typeof v === "string" ? v.trim().length > 0 : !!v;
				} catch {
					return !!(($inp && $inp.val()) || "").toString().trim().length;
				}
			};

			const toggle = () => $btn.toggle(hasValue());

			// keep visibility synced
			$host
				.find("input")
				.off(".kpiClear")
				.on("input.kpiClear change.kpiClear awesomplete-selectcomplete.kpiClear", toggle);

			// wrap on_change once
			if (!field._kpiClearPatched) {
				const orig = field.on_change;
				field.on_change = function () {
					toggle();
					if (orig) orig.call(this);
				};
				field._kpiClearPatched = true;
			}

			toggle();
		};

		// initial
		ensure();

		// survive DOM re-renders
		try {
			if (field._kpiClearObserver) field._kpiClearObserver.disconnect();
			const obs = new MutationObserver(() => ensure());
			obs.observe($host[0], { childList: true, subtree: true });
			field._kpiClearObserver = obs;
		} catch {}
	}

	// ========== CREATE FILTERS ==========
	let fSODateRange, fSOPhysicalCell, fSOSO;
	let fWODateRange, fWOPhysicalCell, fWOWO;

	function createFilters() {
		const getYearRange = () => {
			const currentYear = new Date().getFullYear();
			return [`${currentYear}-01-01`, `${currentYear}-12-31`];
		};

		const defaultYearRange = getYearRange();

		// SO Tab Filters
		fSODateRange = page.add_field({
			fieldtype: "DateRange",
			fieldname: "so_date_range",
			label: "Ex-Fty Date Range",
			reqd: 1,
			default: defaultYearRange,
		});

		fSOPhysicalCell = page.add_field({
			fieldtype: "Link",
			fieldname: "so_physical_cell",
			label: "Physical Cell",
			options: "Physical Cell",
		});

		fSOSO = page.add_field({
			fieldtype: "Link",
			fieldname: "sales_order",
			label: "Sales Order",
			options: "Sales Order",
			filters: { docstatus: 1 },
		});

		// WO Tab Filters
		fWODateRange = page.add_field({
			fieldtype: "DateRange",
			fieldname: "wo_date_range",
			label: "Ex-Fty Date Range",
			reqd: 1,
			default: defaultYearRange,
		});

		fWOPhysicalCell = page.add_field({
			fieldtype: "Link",
			fieldname: "wo_physical_cell",
			label: "Physical Cell",
			options: "Physical Cell",
		});

		fWOWO = page.add_field({
			fieldtype: "Link",
			fieldname: "work_order",
			label: "Work Order",
			options: "Work Order",
			filters: { docstatus: 1 },
		});

		// Append to DOM
		$("#so-summary-filters").append($("<div>").append(fSODateRange.$wrapper));
		$("#so-summary-filters").append($("<div>").append(fSOPhysicalCell.$wrapper));
		$("#so-detail-filters").append($("<div>").append(fSOSO.$wrapper));

		$("#wo-summary-filters").append($("<div>").append(fWODateRange.$wrapper));
		$("#wo-summary-filters").append($("<div>").append(fWOPhysicalCell.$wrapper));
		$("#wo-detail-filters").append($("<div>").append(fWOWO.$wrapper));

		// Hide all initially
		[fSODateRange, fSOPhysicalCell, fSOSO, fWODateRange, fWOPhysicalCell, fWOWO].forEach((f) =>
			f.$wrapper.hide()
		);

		// Add clear buttons (Link + DateRange) — run debouncedLoad instantly on clear
		attachClearButton(fSODateRange, () => debouncedLoad && debouncedLoad());
		attachClearButton(fSOPhysicalCell, () => debouncedLoad && debouncedLoad());
		attachClearButton(fSOSO, () => debouncedLoad && debouncedLoad());

		attachClearButton(fWODateRange, () => debouncedLoad && debouncedLoad());
		attachClearButton(fWOPhysicalCell, () => debouncedLoad && debouncedLoad());
		attachClearButton(fWOWO, () => debouncedLoad && debouncedLoad());

		bindFilterEvents();
	}

	function bindFilterEvents() {
		function bindField(field) {
			if (!field.$input) return;
			field.$input.on("input change awesomplete-selectcomplete", debouncedLoad);
		}

		bindField(fSOPhysicalCell);
		bindField(fSOSO);
		bindField(fWOPhysicalCell);
		bindField(fWOWO);

		fSODateRange.$input?.on("change", debouncedLoad);
		fWODateRange.$input?.on("change", debouncedLoad);
	}

	// ========== RENDER LAYOUT ==========
	$root.html(`
    <div class="kpi-tabs">
      <button class="kpi-tab active" data-tab="so">Sales Order Status</button>
      <button class="kpi-tab" data-tab="wo">Work Order Status</button>
    </div>

    <div class="kpi-tab-content">
      <!-- SO TAB -->
      <div class="kpi-tab-pane" data-tab="so" style="display:block;">
        <div class="kpi-section">
          <h5>SO Pending at Chosen Physical Cell</h5>
          <div class="kpi-filter-row" id="so-summary-filters"></div>
          <div class="kpi-card">
            <div class="kpi-scrollable-table">
              <table class="kpi-table" id="so-summary-table">
                <thead>
                  <tr>
                    <th>SO Number</th>
                    <th>SO Quantity</th>
                    <th>Completed Units</th>
                    <th>Pending Units</th>
                    <th>Rejected Units</th>
                  </tr>
                </thead>
                <tbody></tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="kpi-section">
          <h5>Sales Order Details & Metrics</h5>
          <div class="kpi-filter-row" id="so-detail-filters"></div>
          <div class="kpi-dashboard-grid">
            <div>
              <div class="kpi-card">
                <h6>Sales Order Details</h6>
                <table class="kpi-details-table" id="so-details-table">
                  <tbody></tbody>
                </table>
              </div>
              <div class="kpi-card">
                <h6>Pending Units by Size & Physical Cell (SO)</h6>
                <div class="kpi-scrollable-table">
                  <table class="kpi-table" id="so-op-metrics-table">
                    <thead>
                      <tr>
                        <th>Physical Cell</th>
                        <th>Size</th>
                        <th>Total Units</th>
                        <th>Completed Units</th>
                        <th>Pending Units</th>
                        <th>Rejected Units</th>
                      </tr>
                    </thead>
                    <tbody></tbody>
                  </table>
                </div>
              </div>
            </div>
            <div>
              <div class="kpi-card">
                <h6>Pending Units by Physical Cell</h6>
                <canvas id="so-chart"></canvas>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- WO TAB -->
      <div class="kpi-tab-pane" data-tab="wo" style="display:none;">
        <div class="kpi-section">
          <h5>WO Pending at Chosen Physical Cell</h5>
          <div class="kpi-filter-row" id="wo-summary-filters"></div>
          <div class="kpi-card">
            <div class="kpi-scrollable-table">
              <table class="kpi-table" id="wo-summary-table">
                <thead>
                  <tr>
                    <th>WO Number</th>
                    <th>WO Quantity</th>
                    <th>Completed Units</th>
                    <th>Pending Units</th>
                    <th>Rejected Units</th>
                  </tr>
                </thead>
                <tbody></tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="kpi-section">
          <h5>Work Order Details & Metrics</h5>
          <div class="kpi-filter-row" id="wo-detail-filters"></div>
          <div class="kpi-dashboard-grid">
            <div>
              <div class="kpi-card">
                <h6>Work Order Details</h6>
                <table class="kpi-details-table" id="wo-details-table">
                  <tbody></tbody>
                </table>
              </div>
              <div class="kpi-card">
                <h6>Pending Units by Size & Physical Cell (WO)</h6>
                <div class="kpi-scrollable-table">
                  <table class="kpi-table" id="wo-op-metrics-table">
                    <thead>
                      <tr>
                        <th>Physical Cell</th>
                        <th>Size</th>
                        <th>Total Units</th>
                        <th>Completed Units</th>
                        <th>Pending Units</th>
                        <th>Rejected Units</th>
                      </tr>
                    </thead>
                    <tbody></tbody>
                  </table>
                </div>
              </div>
            </div>
            <div>
              <div class="kpi-card">
                <h6>Pending Units by Physical Cell</h6>
                <canvas id="wo-chart"></canvas>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `);

	// Breadcrumb
	const $breadcrumb = $(`
    <div class="breadcrumb-bar" style="
      padding: 8px 16px;
      background: #f9fafb;
      border-bottom: 1px solid #e5e7eb;
      font-size: 14px;
      margin-bottom: 16px;
    ">
      <a href="/app/kpi-hub" style="color: #1f2937; text-decoration: none;">KPI Hub</a>
      <span style="margin: 0 8px;">></span>
      <span style="color: #6b7280;">SO WO Status by Physical Cell</span>
    </div>
  `).prependTo($root);

	const $tabs = $root.find(".kpi-tabs");
	const $panes = $root.find(".kpi-tab-pane");

	function updateTabFilters(tab) {
		[fSODateRange, fSOPhysicalCell, fSOSO, fWODateRange, fWOPhysicalCell, fWOWO].forEach((f) =>
			f.$wrapper.hide()
		);
		if (tab === "so") {
			fSODateRange.$wrapper.show();
			fSOPhysicalCell.$wrapper.show();
			fSOSO.$wrapper.show();
		} else {
			fWODateRange.$wrapper.show();
			fWOPhysicalCell.$wrapper.show();
			fWOWO.$wrapper.show();
		}
	}

	// ========== LOAD DATA ==========
	async function loadData(tab) {
		try {
			const filters = {};
			if (tab === "so") {
				filters.date_range = fSODateRange.get_value();
				filters.physical_cell = fSOPhysicalCell.get_value();
				filters.sales_order = fSOSO.get_value();
			} else {
				filters.date_range = fWODateRange.get_value();
				filters.physical_cell = fWOPhysicalCell.get_value();
				filters.work_order = fWOWO.get_value();
			}

			const resp = await frappe.call({
				method: "frappe.desk.query_report.run",
				args: {
					report_name: "SO WO Status by Physical Cell",
					filters,
				},
			});

			const dataMap = {};
			const reportSummary = resp?.message?.report_summary || [];

			if (Array.isArray(reportSummary)) {
				reportSummary.forEach((item) => {
					if (item.name && item.data !== undefined) {
						dataMap[item.name] = item.data;
					}
				});
			}

			if (tab === "so") {
				const summarySO = dataMap.summary_so || [];
				const detailSO = dataMap.detail_so || {};
				loadSOTab(summarySO, detailSO);
			} else {
				const summaryWO = dataMap.summary_wo || [];
				const detailWO = dataMap.detail_wo || {};
				loadWOTab(summaryWO, detailWO);
			}
		} catch (error) {
			console.error("❌ Error loading data:", error);
			frappe.show_alert({ message: "Failed to load data", indicator: "red" }, 5);
		}
	}

	// ========== RENDER TABS ==========
	function loadSOTab(summaryData, detailData) {
		const $sumTbody = $root.find("#so-summary-table tbody").empty();
		if (summaryData.length === 0) {
			$sumTbody.append(`<tr><td colspan="5">No data found</td></tr>`);
		} else {
			summaryData.forEach((row) => {
				$sumTbody.append(`
					<tr>
						<td>${row.so_number || "-"}</td>
						<td>${row.so_quantity || 0}</td>
						<td class="completed">${row.completed_units || 0}</td>
						<td class="pending">${row.pending_units || 0}</td>
						<td class="rejected">${row.rejected_units || 0}</td>
					</tr>
				`);
			});
		}

		const $detTbody = $root.find("#so-details-table tbody").empty();
		const $opTbody = $root.find("#so-op-metrics-table tbody").empty();

		if (!detailData || Object.keys(detailData).length === 0) {
			$detTbody.append(`<tr><td colspan="2">Select a Sales Order to view details</td></tr>`);
			$opTbody.append(`<tr><td colspan="6">Select a Sales Order to view metrics</td></tr>`);
			const ctx = document.getElementById("so-chart")?.getContext("2d");
			if (ctx?.chart) ctx.chart.destroy();
			return;
		}

		// Details
		const fieldsToShow = [
			"so_quantity",
			"ex_factory_date",
			"fty_client",
			"product_family",
			"fty_prod_id",
			"style",
			"color",
			"material",
		];
		fieldsToShow.forEach((key) => {
			const label = key === "so_quantity" ? "SO Quantity" : frappe.unscrub(key);
			const value = detailData.details?.[key] || "-";
			$detTbody.append(`<tr><td>${label}</td><td>${value}</td></tr>`);
		});

		// Metrics: ONLY physical_cell, size, and quantities
		const metrics = detailData.metrics_by_cell || [];
		if (metrics.length === 0) {
			$opTbody.append(`<tr><td colspan="6">No physical cell data found</td></tr>`);
		} else {
			metrics.forEach((row) => {
				$opTbody.append(`
					<tr>
						<td>${row.physical_cell || "-"}</td>
						<td>${row.size || "-"}</td>
						<td>${row.size_qty || 0}</td>
						<td class="completed">${row.completed_units || 0}</td>
						<td class="pending">${row.pending_units || 0}</td>
						<td class="rejected">${row.rejected_units || 0}</td>
					</tr>
				`);
			});
		}

		renderChart("so-chart", metrics, "Sales Order");
	}

	function loadWOTab(summaryData, detailData) {
		const $sumTbody = $root.find("#wo-summary-table tbody").empty();
		if (summaryData.length === 0) {
			$sumTbody.append(`<tr><td colspan="5">No data found</td></tr>`);
		} else {
			summaryData.forEach((row) => {
				$sumTbody.append(`
					<tr>
						<td>${row.wo_number || "-"}</td>
						<td>${row.wo_quantity ?? 0}</td>
						<td class="completed">${row.completed_units ?? 0}</td>
						<td class="pending">${row.pending_units ?? 0}</td>
						<td class="rejected">${row.rejected_units ?? 0}</td>
					</tr>
				`);
			});
		}

		const $detTbody = $root.find("#wo-details-table tbody").empty();
		const $opTbody = $root.find("#wo-op-metrics-table tbody").empty();

		if (!detailData || Object.keys(detailData).length === 0) {
			$detTbody.append(`<tr><td colspan="2">Select a Work Order to view details</td></tr>`);
			$opTbody.append(`<tr><td colspan="6">Select a Work Order to view metrics</td></tr>`);
			const ctx = document.getElementById("wo-chart")?.getContext("2d");
			if (ctx?.chart) ctx.chart.destroy();
			return;
		}

		const fieldsToShow = [
			"wo_quantity",
			"sales_order",
			"wo_allocated_qty",
			"ex_factory_date",
			"fty_client",
			"product_family",
			"fty_prod_id",
			"style",
			"color",
			"material",
		];
		fieldsToShow.forEach((key) => {
			let label = frappe.unscrub(key);
			if (key === "wo_quantity") label = "WO Quantity";
			else if (key === "wo_allocated_qty") label = "WO Allocated Quantity";
			const value = detailData.details?.[key] || "-";
			$detTbody.append(`<tr><td>${label}</td><td>${value}</td></tr>`);
		});

		const metrics = detailData.metrics_by_cell || [];
		if (metrics.length === 0) {
			$opTbody.append(`<tr><td colspan="6">No physical cell data found</td></tr>`);
		} else {
			metrics.forEach((row) => {
				$opTbody.append(`
					<tr>
						<td>${row.physical_cell || "-"}</td>
						<td>${row.size || "-"}</td>
						<td>${row.size_qty ?? 0}</td>
						<td class="completed">${row.completed_units ?? 0}</td>
						<td class="pending">${row.pending_units ?? 0}</td>
						<td class="rejected">${row.rejected_units ?? 0}</td>
					</tr>
				`);
			});
		}

		renderChart("wo-chart", metrics, "Work Order");
	}

	// Simplified chart: group by physical_cell only
	function renderChart(canvasId, metrics, title) {
		if (!metrics || metrics.length === 0) return;

		const labels = [...new Set(metrics.map((r) => r.physical_cell))];
		const completed = labels.map((cell) =>
			metrics
				.filter((r) => r.physical_cell === cell)
				.reduce((sum, r) => sum + (r.completed_units || 0), 0)
		);
		const pending = labels.map((cell) =>
			metrics
				.filter((r) => r.physical_cell === cell)
				.reduce((sum, r) => sum + (r.pending_units || 0), 0)
		);
		const rejected = labels.map((cell) =>
			metrics
				.filter((r) => r.physical_cell === cell)
				.reduce((sum, r) => sum + (r.rejected_units || 0), 0)
		);

		loadChartJs().then(() => {
			const canvas = document.getElementById(canvasId);
			if (!canvas) return;
			const ctx = canvas.getContext("2d");
			if (ctx.chart) ctx.chart.destroy();

			ctx.chart = new Chart(ctx, {
				type: "bar",
				data: {
					labels: labels,
					datasets: [
						{ label: "Completed", data: completed, backgroundColor: "#96BE37" },
						{ label: "Pending", data: pending, backgroundColor: "#ECAD4B" },
						{ label: "Rejected", data: rejected, backgroundColor: "#EF4444" },
					],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: {
						legend: { position: "top" },
						title: { display: true, text: `${title} - Units by Physical Cell` },
					},
					scales: {
						y: { beginAtZero: true, title: { display: true, text: "Units" } },
						x: { title: { display: true, text: "Physical Cell" } },
					},
				},
			});
		});
	}

	async function loadChartJs() {
		if (window.Chart) return;
		await new Promise((resolve) =>
			frappe.require("https://cdn.jsdelivr.net/npm/chart.js", resolve)
		);
	}

	// ========== EVENTS ==========
	$tabs.on("click", ".kpi-tab", function () {
		const tab = $(this).data("tab");
		$tabs.find(".kpi-tab").removeClass("active");
		$(this).addClass("active");
		$panes.hide().filter(`[data-tab="${tab}"]`).show();
		updateTabFilters(tab);
		loadData(tab);
	});

	const debouncedLoad = frappe.utils.debounce(() => {
		const activeTab = $tabs.find(".active").data("tab");
		loadData(activeTab);
	}, 400);

	// Initialize
	frappe.after_ajax(() => {
		createFilters();
		updateTabFilters("so");
		loadData("so");
	});
};
