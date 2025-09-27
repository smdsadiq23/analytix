frappe.pages["so-wo-pending-status"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "SO WO Pending Status",
		single_column: true,
	});

	const $root = $(wrapper).find(".layout-main-section");

	// ===== STYLES =====
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
	.kpi-table { width:100%; border-collapse: collapse; margin-top:12px; }
	.kpi-table th, .kpi-table td { padding:8px; border:1px solid #e5e7eb; text-align:left; }
	.kpi-table th { background:#f9fafb; font-weight:600; }
	.kpi-details-table { width:100%; border-collapse: collapse; margin-top:12px; }
	.kpi-details-table td { padding:8px; border:1px solid #e5e7eb; vertical-align: top; }
	.kpi-details-table td:first-child { font-weight: 600; background: #f9fafb; width: 40%; }

	/* Clear Button for Link fields (Operation, SO, WO) — matches Flow Rate style */
	.frappe-control[data-fieldtype="Link"] .control-input,
	.frappe-control[data-fieldtype="Link"] .control-input-wrapper { position: relative; }
	.frappe-control[data-fieldtype="Link"] input.input-with-feedback { padding-right: 26px !important; }
	.frappe-control[data-fieldtype="Link"] .kpi-clear-btn {
		position: absolute;
		right: 8px;
		top: 50%;
		transform: translateY(-50%);
		border: 0;
		background: transparent;
		line-height: 1;
		padding: 0 6px;
		color: var(--gray-600);
		border-radius: 6px;
		cursor: pointer;
		z-index: 2;
	}
	.frappe-control[data-fieldtype="Link"] .kpi-clear-btn:hover {
		background: var(--gray-100);
	}

	/* Colors */
	.completed { background: #96BE37; color: white; }
	.pending { background: #ECAD4B; color: black; }
	.rejected { background: #EF4444; color: white; }

	/* Responsive */
	@media (max-width: 1100px) {
		.kpi-filter-row { flex-direction: column; align-items: stretch; }
		.kpi-dashboard-grid { grid-template-columns: 1fr; }
	}
	</style>`).appendTo(document.head);

	// ========== CLEAR BUTTON HELPER (from flow-rate-viewer) ==========
	function addClearButtonToLinkField(field) {
		const $host = field.$wrapper.find(".control-input, .control-input-wrapper").first().length
			? field.$wrapper.find(".control-input, .control-input-wrapper").first()
			: field.$wrapper;

		if ($host.find('.kpi-clear-btn[data-for="' + field.df.fieldname + '"]').length) return;

		$(
			`<button type="button" class="kpi-clear-btn" data-for="${field.df.fieldname}" title="Clear">×</button>`
		)
			.appendTo($host)
			.on("click", (e) => {
				e.preventDefault();
				e.stopPropagation();
				try {
					field.set_value("");
				} catch {}
				try {
					field.set_input && field.set_input("");
				} catch {}
				if (field.$input) {
					field.$input.val("").trigger("input").trigger("change");
				}
				if (field.on_change) field.on_change();
			});

		const toggleVisibility = () => {
			const hasValue = !!field.get_value();
			$host.find(`.kpi-clear-btn[data-for="${field.df.fieldname}"]`).toggle(hasValue);
		};

		toggleVisibility();

		const original_on_change = field.on_change;
		field.on_change = function () {
			toggleVisibility();
			if (original_on_change) original_on_change.call(this);
		};
	}

	// ========== CREATE FILTERS ==========
	let fSODateRange, fSOOperation, fSOSO;
	let fWODateRange, fWOOperation, fWOWO;

	function createFilters() {
		// Helper to get start and end of current year
		const getYearRange = () => {
			const currentYear = new Date().getFullYear();
			const startOfYear = `${currentYear}-01-01`;
			const endOfYear = `${currentYear}-12-31`;
			return [startOfYear, endOfYear];
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

		fSOOperation = page.add_field({
			fieldtype: "Link",
			fieldname: "so_operation",
			label: "Operation",
			options: "Operation",
		});

		fSOSO = page.add_field({
			fieldtype: "Link",
			fieldname: "sales_order",
			label: "Sales Order",
			options: "Sales Order",
			filters: { docstatus: 1 }
		});

		// WO Tab Filters
		fWODateRange = page.add_field({
			fieldtype: "DateRange",
			fieldname: "wo_date_range",
			label: "Ex-Fty Date Range",
			reqd: 1,
			default: defaultYearRange,
		});

		fWOOperation = page.add_field({
			fieldtype: "Link",
			fieldname: "wo_operation",
			label: "Operation",
			options: "Operation",
		});

		fWOWO = page.add_field({
			fieldtype: "Link",
			fieldname: "work_order",
			label: "Work Order",
			options: "Work Order",
			filters: { docstatus: 1 }
		});

		// Append to DOM
		$("#so-summary-filters").append($("<div>").append(fSODateRange.$wrapper));
		$("#so-summary-filters").append($("<div>").append(fSOOperation.$wrapper));
		$("#so-detail-filters").append($("<div>").append(fSOSO.$wrapper));

		$("#wo-summary-filters").append($("<div>").append(fWODateRange.$wrapper));
		$("#wo-summary-filters").append($("<div>").append(fWOOperation.$wrapper));
		$("#wo-detail-filters").append($("<div>").append(fWOWO.$wrapper));

		// Hide all initially
		[fSODateRange, fSOOperation, fSOSO, fWODateRange, fWOOperation, fWOWO].forEach((f) =>
			f.$wrapper.hide()
		);

		// ✅ Add clear buttons ONLY to Link fields (Operation, SO, WO)
		addClearButtonToLinkField(fSOOperation);
		addClearButtonToLinkField(fSOSO);
		addClearButtonToLinkField(fWOOperation);
		addClearButtonToLinkField(fWOWO);

		bindFilterEvents();
	}

	function bindFilterEvents() {
	// Helper to bind all relevant events
	function bindField(field) {
		if (!field.$input) return;
		// For Link fields: watch input, change, and Awesomplete select
		field.$input.on("input change awesomplete-selectcomplete", debouncedLoad);
		// For DateRange: already uses change
	}

	// Bind all filters
	bindField(fSOOperation);
	bindField(fSOSO);
	bindField(fWOOperation);
	bindField(fWOWO);

	// DateRange uses 'change'
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
          <h5>SO Pending at Chosen Operation</h5>
          <div class="kpi-filter-row" id="so-summary-filters"></div>
          <div class="kpi-card">
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
                <h6>Pending Units by Operation(SO)</h6>
                <table class="kpi-table" id="so-op-metrics-table">
                  <thead>
                    <tr>
                      <th>Process</th>
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
            <div>
              <div class="kpi-card">
                <h6>Pending Units by Operation</h6>
                <canvas id="so-chart"></canvas>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- WO TAB -->
      <div class="kpi-tab-pane" data-tab="wo" style="display:none;">
        <div class="kpi-section">
          <h5>WO Pending at Chosen Operation</h5>
          <div class="kpi-filter-row" id="wo-summary-filters"></div>
          <div class="kpi-card">
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
                <h6>Pending Units by Operation(WO)</h6>
                <table class="kpi-table" id="wo-op-metrics-table">
                  <thead>
                    <tr>
                      <th>Process</th>
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
            <div>
              <div class="kpi-card">
                <h6>Pending Units by Operation</h6>
                <canvas id="wo-chart"></canvas>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `);

	// 👇 Add manual breadcrumb bar
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
      <span style="color: #6b7280;">SO WO Pending Status</span>
    </div>
  `).prependTo($root);

	const $tabs = $root.find(".kpi-tabs");
	const $panes = $root.find(".kpi-tab-pane");

	// ========== SHOW/HIDE FILTERS ==========
	function updateTabFilters(tab) {
		[fSODateRange, fSOOperation, fSOSO, fWODateRange, fWOOperation, fWOWO].forEach((f) =>
			f.$wrapper.hide()
		);
		if (tab === "so") {
			fSODateRange.$wrapper.show();
			fSOOperation.$wrapper.show();
			fSOSO.$wrapper.show();
		} else {
			fWODateRange.$wrapper.show();
			fWOOperation.$wrapper.show();
			fWOWO.$wrapper.show();
		}
	}

	// ========== LOAD DATA ==========
	async function loadData(tab) {
		try {
			const filters = {};
			if (tab === "so") {
				filters.date_range = fSODateRange.get_value();
				filters.operation = fSOOperation.get_value();
				filters.sales_order = fSOSO.get_value();
			} else {
				filters.date_range = fWODateRange.get_value();
				filters.operation = fWOOperation.get_value();
				filters.work_order = fWOWO.get_value();
			}

			console.log(`🔄 Loading data for tab: ${tab}`);
			console.log("📥 Using filters:", filters);

			const resp = await frappe.call({
				method: "frappe.desk.query_report.run",
				args: { report_name: "SO WO Pending Status", filters },
			});

			console.log("✅ Raw response from backend:", resp);

			const dataMap = {};
			const reportSummary = resp?.message?.report_summary || [];

			if (!Array.isArray(reportSummary)) {
				console.warn("⚠️ report_summary is not an array:", reportSummary);
			} else {
				reportSummary.forEach((item) => {
					if (item.name && item.data !== undefined) {
						dataMap[item.name] = item.data;
					}
				});
			}

			console.log("🧩 Reconstructed dataMap from report_summary:", dataMap);

			if (tab === "so") {
				const detailSO = dataMap.detail_so;
				console.log("📦 Calling loadSOTab with:", detailSO);
				if (detailSO) {
					loadSOTab(detailSO);
				} else {
					console.warn("⚠️ No detail_so data found in response.");
				}
			} else if (tab === "wo") {
				const detailWO = dataMap.detail_wo;
				console.log("📦 Calling loadWOTab with:", detailWO);
				if (detailWO) {
					loadWOTab(detailWO);
				} else {
					console.warn("⚠️ No detail_wo data found in response.");
				}
			}
		} catch (error) {
			console.error("❌ Error loading data:", error);
			frappe.show_alert({ message: "Failed to load data", indicator: "red" }, 5);
		}
	}

	function loadSOTab(detailSO) {
		console.log("🚀 Inside loadSOTab");
		console.log("📦 detailSO:", detailSO);

		if (!detailSO) {
			console.warn("❌ No SO details object found. Skipping detail rendering.");
			// Clear tables & destroy chart if any
			$root.find("#so-details-table tbody, #so-metrics-table tbody").empty();
			const ctx = document.getElementById("so-chart")?.getContext("2d");
			if (ctx?.chart) ctx.chart.destroy();
			return;
		}

		const summaryData = detailSO.summary || [];
		const detailData = detailSO.details || {};
		const metrics = detailSO.metrics_by_op || [];

		// Render SO Summary Table (if you have one - add if needed)
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

		// Render SO Details Table
		const $detTbody = $root.find("#so-details-table tbody").empty();
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
			const label = key == 'so_quantity'? 'Quantity' : frappe.unscrub(key);
			const value = detailData[key] || "-";
			$detTbody.append(`<tr><td>${label}</td><td>${value}</td></tr>`);
		});

		// Render SO Metrics Table
		const $opTbody = $root.find("#so-op-metrics-table tbody").empty();
		if (metrics.length === 0) {
			$opTbody.append(`<tr><td colspan="6">No operations found</td></tr>`);
		} else {
			metrics.forEach((row) => {
				$opTbody.append(`
        <tr>
          <td>${row.operation || "-"}</td>
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

	function loadWOTab(detailWO) {
		console.log("🚀 Inside loadWOTab");
		console.log("📦 detailWO:", detailWO);

		// Clear all tables and destroy chart if no data
		if (!detailWO) {
			console.warn("❌ No WO details object found. Skipping detail rendering.");
			$root
				.find(
					"#wo-details-table tbody, #wo-op-metrics-table tbody, #wo-summary-table tbody"
				)
				.empty();
			const ctx = document.getElementById("wo-chart")?.getContext("2d");
			if (ctx?.chart) ctx.chart.destroy();
			return;
		}

		const summaryData = detailWO.summary || [];
		const detailData = detailWO.details || {};
		const metrics = detailWO.metrics_by_op || [];

		// 1. Render Summary Table
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

		// 2. Render WO Details Table
		const $detTbody = $root.find("#wo-details-table tbody").empty();
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
			const label = key == 'wo_quantity'? 'Quantity' : frappe.unscrub(key);
			const value = detailData[key] || "-";
			$detTbody.append(`<tr><td>${label}</td><td>${value}</td></tr>`);
		});

		// 3. Render Metrics by Operation
		const $opTbody = $root.find("#wo-op-metrics-table tbody").empty();

		if (metrics.length === 0) {
			$opTbody.append(`<tr><td colspan="6">No operations found</td></tr>`);
		} else {
			metrics.forEach((row) => {
				$opTbody.append(`
        <tr>
          <td>${row.operation || "-"}</td>
          <td>${row.size || "-"}</td>
          <td>${row.size_qty ?? 0}</td>
          <td class="completed">${row.completed_units ?? 0}</td>
          <td class="pending">${row.pending_units ?? 0}</td>
          <td class="rejected">${row.rejected_units ?? 0}</td>
        </tr>
      `);
			});
		}

		// 4. Render Chart
		renderChart("wo-chart", metrics, "Work Order");
	}

	function renderChart(canvasId, metrics, title) {
		if (!metrics || metrics.length === 0) return;

		const labels = [...new Set(metrics.map((r) => r.operation))];
		const completed = labels.map((op) =>
			metrics
				.filter((r) => r.operation === op)
				.reduce((sum, r) => sum + (r.completed_units || 0), 0)
		);
		const pending = labels.map((op) =>
			metrics
				.filter((r) => r.operation === op)
				.reduce((sum, r) => sum + (r.pending_units || 0), 0)
		);
		const rejected = labels.map((op) =>
			metrics
				.filter((r) => r.operation === op)
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
						{ label: "Completed", completed, backgroundColor: "#96BE37" },
						{ label: "Pending", pending, backgroundColor: "#ECAD4B" },
						{ label: "Rejected", rejected, backgroundColor: "#EF4444" },
					],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: {
						legend: { position: "top" },
						title: { display: true, text: `${title} - Units by Operation` },
					},
					scales: {
						y: { beginAtZero: true, title: { display: true, text: "Units" } },
						x: { title: { display: true, text: "Operation" } },
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
