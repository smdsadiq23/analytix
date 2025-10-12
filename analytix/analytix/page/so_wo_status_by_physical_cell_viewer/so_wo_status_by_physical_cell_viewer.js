frappe.pages["so-wo-status-by-physical-cell-viewer"].on_page_load = function (wrapper) {
	// ---- idempotent remount: clean up previous mount on navigation back/forward ----
	if (wrapper.__pc_cleanup) {
		try {
			wrapper.__pc_cleanup();
		} catch {}
	}

	// Call the shared helper
	CX.mountBreadcrumb({
		wrapper,
		trail: [
			{ label: "KPI Hub", href: "/app/kpi-hub" },
			{ label: "SO WO Status by Physical Cell" }
		]
	});

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "SO WO Status by Physical Cell",
		single_column: true,
	});

	const $root = $(wrapper).find(".layout-main-section");
	const MOUNT_ID = "sopc-viewer-mount";

	// fresh mount container
	$root.empty().append(`<div id="${MOUNT_ID}"></div>`);
	const $mount = $root.find("#" + MOUNT_ID);

	// ===== STYLES =====
	$("#kpi-ms-overflow-fix").remove();
	$(`<style id="kpi-ms-overflow-fix">
    #${MOUNT_ID}.page-form .frappe-control { min-width: 0; }
    .kpi-tabs { display: flex; border-bottom: 1px solid var(--border-color); background: #f9fafb; }
    .kpi-tab { padding: 12px 24px; cursor: pointer; font-weight: 600; color: #6b7280; border: none; background: transparent; }
    .kpi-tab.active { background: #96BE37; color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; }
    .kpi-section { margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; }
    .kpi-section h5 { margin: 0 0 16px 0; color: #333; font-size: 16px; }
    .kpi-filter-row { display: flex; gap: 16px; margin-bottom: 16px; align-items: center; }
    .kpi-filter-row .frappe-control { min-width: 200px; }
    .frappe-control[data-fieldname="so_date_range"],
    .frappe-control[data-fieldname="wo_date_range"] { min-width: 280px !important; }
    .kpi-card { border:1px solid var(--border-color,#e5e7eb); border-radius:8px; padding:12px; background:#fff; margin-bottom:16px; }
    .kpi-card h6 { margin:0 0 6px 0; color:var(--text-muted,#6b7280); font-weight:600; }
    .kpi-card canvas { width:100%; height:420px; max-height:420px; }
    .kpi-scrollable-table { max-height: 220px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; background: white; }
    .kpi-scrollable-table table { width: 100%; border-collapse: collapse; }
    .kpi-scrollable-table th { position: sticky; top: 0; background: #f9fafb; z-index: 10; padding: 8px; border: 1px solid #e5e7eb; text-align: left; font-weight: 600; }
    .kpi-scrollable-table td { padding: 8px; border: 1px solid #e5e7eb; text-align: left; }
    .kpi-details-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    .kpi-details-table td { padding: 8px; border: 1px solid #e5e7eb; vertical-align: top; }
    .kpi-details-table td:first-child { font-weight: 600; background: #f9fafb; width: 40%; }
    .kpi-clear-host { position: relative !important; }
    .kpi-clear-btn { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); line-height: 1; padding: 0 8px; border: 0; background: transparent; color: var(--gray-600); cursor: pointer; border-radius: 6px; z-index: 2; }
    .kpi-clear-btn:hover { background: var(--gray-100); }
    .completed { background: #96BE37; color: white; }
    .pending { background: #ECAD4B; color: black; }
    .rejected { background: #EF4444; color: white; }
    .wip { background: #3B82F6; color: white; } /* ✅ WIP styling — MATCHES OPERATION REPORT */
    @media (max-width: 1100px) { .kpi-filter-row { flex-direction: column; align-items: stretch; } .kpi-dashboard-grid { grid-template-columns: 1fr; } }
    .awesomplete {
      z-index: 10000 !important;
    }
    .awesomplete > ul {
      z-index: 10000 !important;
      position: absolute !important;
      top: auto !important;
      bottom: auto !important;
    }
  </style>`).appendTo(document.head);

	// ========== CLEAR BUTTON HELPER ==========
	function attachClearButton(field, onClear) {
		if (!field || !field.$wrapper) return;
		const fname = field.df.fieldname;

		const $host = field.$wrapper.find(".control-input, .control-input-wrapper").first().length
			? field.$wrapper.find(".control-input, .control-input-wrapper").first()
			: field.$wrapper;
		$host.addClass("kpi-clear-host");

		const ensure = () => {
			let $inp = $host.find("input.input-with-feedback").first();
			if (!$inp.length) $inp = $host.find("input").first();
			if (!$inp.length && field.$input) $inp = field.$input;

			let $btn = $host.find(`.kpi-clear-btn[data-for="${fname}"]`);
			if (!$btn.length) {
				$btn = $(
					`<button type="button" class="kpi-clear-btn" data-for="${fname}" title="Clear">×</button>`
				).appendTo($host);
				$btn.on("mousedown", async (e) => {
					e.preventDefault();
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
					$host
						.find("input")
						.val("")
						.trigger("input")
						.trigger("change")
						.trigger("awesomplete-selectcomplete");
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

			$host
				.find("input")
				.off(".kpiClear")
				.on("input.kpiClear change.kpiClear awesomplete-selectcomplete.kpiClear", toggle);

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

		ensure();

		if (field._kpiClearObserver) field._kpiClearObserver.disconnect();
		const obs = new MutationObserver(() => ensure());
		obs.observe($host[0], { childList: true, subtree: true });
		field._kpiClearObserver = obs;
	}

	// ========== LAYOUT ==========
	$mount.html(`
    <div class="kpi-tabs">
      <button class="kpi-tab active" data-tab="so">Sales Order Status</button>
      <button class="kpi-tab" data-tab="wo">Work Order Status</button>
    </div>

    <div class="kpi-tab-content">
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
                    <th>Completion %</th>
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
                <table class="kpi-details-table" id="so-details-table"><tbody></tbody></table>
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
                        <th>Completion %</th>
                        <th>WIP</th> <!-- ✅ WIP as LAST column, like Operation report -->
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
                    <th>Completion %</th>
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
                <table class="kpi-details-table" id="wo-details-table"><tbody></tbody></table>
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
                        <th>Completion %</th>
                        <th>WIP</th> <!-- ✅ LAST column -->
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

	// ========== FILTERS ==========
	let fSODateRange, fSOPhysicalCell, fSOSO;
	let fWODateRange, fWOPhysicalCell, fWOWO;

	function createFilters() {
		const getYearRange = () => {
			const y = new Date().getFullYear();
			return [`${y}-01-01`, `${y}-12-31`];
		};
		const defaultYearRange = getYearRange();

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

		$mount.find("#so-summary-filters").append($("<div>").append(fSODateRange.$wrapper));
		$mount.find("#so-summary-filters").append($("<div>").append(fSOPhysicalCell.$wrapper));
		$mount.find("#so-detail-filters").append($("<div>").append(fSOSO.$wrapper));

		$mount.find("#wo-summary-filters").append($("<div>").append(fWODateRange.$wrapper));
		$mount.find("#wo-summary-filters").append($("<div>").append(fWOPhysicalCell.$wrapper));
		$mount.find("#wo-detail-filters").append($("<div>").append(fWOWO.$wrapper));

		[fSODateRange, fSOPhysicalCell, fSOSO, fWODateRange, fWOPhysicalCell, fWOWO].forEach((f) =>
			f.$wrapper.hide()
		);

		attachClearButton(fSODateRange, debouncedLoad);
		attachClearButton(fSOPhysicalCell, debouncedLoad);
		attachClearButton(fSOSO, debouncedLoad);
		attachClearButton(fWODateRange, debouncedLoad);
		attachClearButton(fWOPhysicalCell, debouncedLoad);
		attachClearButton(fWOWO, debouncedLoad);

		bindFilterEvents();
	}

	function bindFilterEvents() {
		const bind = (f) =>
			f?.$input && f.$input.on("input change awesomplete-selectcomplete", debouncedLoad);
		bind(fSOPhysicalCell);
		bind(fSOSO);
		bind(fWOPhysicalCell);
		bind(fWOWO);
		fSODateRange.$input?.on("change", debouncedLoad);
		fWODateRange.$input?.on("change", debouncedLoad);
	}

	// ========== UTIL: percentage ==========
	function pct(completed, total) {
		const c = Number(completed) || 0;
		const t = Number(total) || 0;
		return t > 0 ? ((c / t) * 100).toFixed(1) + "%" : "0%";
	}

	// ========== DATA ==========
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
				args: { report_name: "SO WO Status by Physical Cell", filters },
			});

			const map = {};
			(resp?.message?.report_summary || []).forEach((it) => {
				if (it?.name) map[it.name] = it.data;
			});

			if (tab === "so") loadSOTab(map.summary_so || [], map.detail_so || {});
			else loadWOTab(map.summary_wo || [], map.detail_wo || {});
		} catch (e) {
			console.error("❌ loadData:", e);
			frappe.show_alert({ message: "Failed to load data", indicator: "red" }, 5);
		}
	}

	function loadSOTab(summary, detail) {
		const $sumTbody = $mount.find("#so-summary-table tbody").empty();
		if (!summary.length) {
			$sumTbody.append(`<tr><td colspan="6">No data found</td></tr>`);
		} else {
			summary.forEach((row) => {
				const total = Number(row.so_quantity || 0);
				const comp = Number(row.completed_units || 0);
				$sumTbody.append(`
          <tr>
            <td>${row.so_number || "-"}</td>
            <td>${total}</td>
            <td class="completed">${comp}</td>
            <td class="pending">${row.pending_units || 0}</td>
            <td class="rejected">${row.rejected_units || 0}</td>
            <td>${pct(comp, total)}</td>
          </tr>`);
			});
		}

		const $detTbody = $mount.find("#so-details-table tbody").empty();
		const $opTbody = $mount.find("#so-op-metrics-table tbody").empty();

		if (!detail || !Object.keys(detail).length) {
			$detTbody.append(`<tr><td colspan="2">Select a Sales Order to view details</td></tr>`);
			$opTbody.append(`<tr><td colspan="8">Select a Sales Order to view metrics</td></tr>`); // ✅ 8 columns
			const ctx = document.getElementById("so-chart")?.getContext("2d");
			if (ctx?.chart) ctx.chart.destroy();
			return;
		}

		[
			"so_quantity",
			"ex_factory_date",
			"fty_client",
			"product_family",
			"fty_prod_id",
			"style",
			"color",
			"material",
		].forEach((k) => {
			const label = k === "so_quantity" ? "SO Quantity" : frappe.unscrub(k);
			const val = detail.details?.[k] || "-";
			$detTbody.append(`<tr><td>${label}</td><td>${val}</td></tr>`);
		});

		const metrics = detail.metrics_by_cell || [];
		if (!metrics.length) {
			$opTbody.append(`<tr><td colspan="8">No physical cell data found</td></tr>`);
		} else {
			metrics.forEach((r) => {
				const tot = Number(r.size_qty || 0);
				const cmp = Number(r.completed_units || 0);
				const wip = Number(r.wip || 0); // ✅
				$opTbody.append(`
          <tr>
            <td>${r.physical_cell || "-"}</td>
            <td>${r.size || "-"}</td>
            <td>${tot}</td>
            <td class="completed">${cmp}</td>
            <td class="pending">${r.pending_units || 0}</td>
            <td class="rejected">${r.rejected_units || 0}</td>
            <td>${pct(cmp, tot)}</td>
            <td class="wip">${wip}</td> <!-- ✅ class="wip", LAST column -->
          </tr>`);
			});
		}
		renderChart("so-chart", metrics, "Sales Order");
	}

	function loadWOTab(summary, detail) {
		const $sumTbody = $mount.find("#wo-summary-table tbody").empty();
		if (!summary.length) {
			$sumTbody.append(`<tr><td colspan="6">No data found</td></tr>`);
		} else {
			summary.forEach((row) => {
				const total = Number(row.wo_quantity ?? 0);
				const comp = Number(row.completed_units ?? 0);
				$sumTbody.append(`
          <tr>
            <td>${row.wo_number || "-"}</td>
            <td>${total}</td>
            <td class="completed">${comp}</td>
            <td class="pending">${row.pending_units ?? 0}</td>
            <td class="rejected">${row.rejected_units ?? 0}</td>
            <td>${pct(comp, total)}</td>
          </tr>`);
			});
		}

		const $detTbody = $mount.find("#wo-details-table tbody").empty();
		const $opTbody = $mount.find("#wo-op-metrics-table tbody").empty();

		if (!detail || !Object.keys(detail).length) {
			$detTbody.append(`<tr><td colspan="2">Select a Work Order to view details</td></tr>`);
			$opTbody.append(`<tr><td colspan="8">Select a Work Order to view metrics</td></tr>`);
			const ctx = document.getElementById("wo-chart")?.getContext("2d");
			if (ctx?.chart) ctx.chart.destroy();
			return;
		}

		[
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
		].forEach((k) => {
			let label = frappe.unscrub(k);
			if (k === "wo_quantity") label = "WO Quantity";
			else if (k === "wo_allocated_qty") label = "WO Allocated Quantity";
			const val = detail.details?.[k] || "-";
			$detTbody.append(`<tr><td>${label}</td><td>${val}</td></tr>`);
		});

		const metrics = detail.metrics_by_cell || [];
		if (!metrics.length) {
			$opTbody.append(`<tr><td colspan="8">No physical cell data found</td></tr>`);
		} else {
			metrics.forEach((r) => {
				const tot = Number(r.size_qty ?? 0);
				const cmp = Number(r.completed_units ?? 0);
				const wip = Number(r.wip ?? 0); // ✅
				$opTbody.append(`
          <tr>
            <td>${r.physical_cell || "-"}</td>
            <td>${r.size || "-"}</td>
            <td>${tot}</td>
            <td class="completed">${cmp}</td>
            <td class="pending">${r.pending_units ?? 0}</td>
            <td class="rejected">${r.rejected_units ?? 0}</td>
            <td>${pct(cmp, tot)}</td>
            <td class="wip">${wip}</td> <!-- ✅ -->
          </tr>`);
			});
		}
		renderChart("wo-chart", metrics, "Work Order");
	}

	// chart
	function renderChart(canvasId, metrics, title) {
		if (!metrics || !metrics.length) return;
		const labels = [...new Set(metrics.map((r) => r.physical_cell))];
		const sum = (cell, key) =>
			metrics.filter((r) => r.physical_cell === cell).reduce((s, r) => s + (r[key] || 0), 0);
		const completed = labels.map((c) => sum(c, "completed_units"));
		const pending = labels.map((c) => sum(c, "pending_units"));
		const rejected = labels.map((c) => sum(c, "rejected_units"));
		const wip = labels.map((c) => sum(c, "wip")); // ✅

		loadChartJs().then(() => {
			const canvas = document.getElementById(canvasId);
			if (!canvas) return;
			const ctx = canvas.getContext("2d");
			if (ctx.chart) ctx.chart.destroy();
			ctx.chart = new Chart(ctx, {
				type: "bar",
				data: {
					labels,
					datasets: [
						{ label: "Completed",  completed, backgroundColor: "#96BE37" },
						{ label: "Pending",  pending, backgroundColor: "#ECAD4B" },
						{ label: "Rejected",  rejected, backgroundColor: "#EF4444" },
						{ label: "WIP",  wip, backgroundColor: "#3B82F6" }, // ✅
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
	const $tabs = $mount.find(".kpi-tabs");
	const $panes = $mount.find(".kpi-tab-pane");

	$tabs.on("click", ".kpi-tab", function () {
		const tab = $(this).data("tab");
		$tabs.find(".kpi-tab").removeClass("active");
		$(this).addClass("active");
		$panes.hide().filter(`[data-tab="${tab}"]`).show();
		updateTabFilters(tab);
		loadData(tab);
	});

	function updateTabFilters(tab) {
		[fSODateRange, fSOPhysicalCell, fSOSO, fWODateRange, fWOPhysicalCell, fWOWO].forEach((f) =>
			f?.$wrapper.hide()
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

	// expose cleanup for next remount
	wrapper.__pc_cleanup = () => {
		try {
			[fSODateRange, fSOPhysicalCell, fSOSO, fWODateRange, fWOPhysicalCell, fWOWO].forEach(
				(f) => f?._kpiClearObserver && f._kpiClearObserver.disconnect()
			);
		} catch {}
		$tabs.off();
		$mount.remove();
	};
};