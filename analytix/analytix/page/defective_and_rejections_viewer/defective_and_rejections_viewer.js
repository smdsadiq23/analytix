frappe.pages["defective-and-rejections-viewer"].on_page_load = function (wrapper) {
	// ---- idempotent remount: clean up previous mount on navigation back/forward ----
	if (wrapper.__dr_cleanup) {
		try {
			wrapper.__dr_cleanup();
		} catch {}
	}

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Defective and Rejections",
		single_column: true,
	});

	const $root = $(wrapper).find(".layout-main-section");
	const MOUNT_ID = "def-rej-viewer-mount";

	// fresh mount container
	$root.empty().append(`<div id="${MOUNT_ID}"></div>`);
	const $mount = $root.find("#" + MOUNT_ID);

	// ===== STYLES =====
	$("#kpi-ms-overflow-fix").remove();
	$(`<style id="kpi-ms-overflow-fix">
    #${MOUNT_ID}.page-form .frappe-control { min-width: 0; }
    .kpi-section { margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; }
    .kpi-section h5 { margin: 0 0 16px 0; color: #333; font-size: 16px; }
    .kpi-filter-row { display: flex; gap: 16px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
    .kpi-filter-row .frappe-control { min-width: 200px; }
    .frappe-control[data-fieldname="date_range"] { min-width: 280px !important; }
    .kpi-card { border:1px solid var(--border-color,#e5e7eb); border-radius:8px; padding:12px; background:#fff; margin-bottom:16px; }
    .kpi-card h6 { margin:0 0 6px 0; color:var(--text-muted,#6b7280); font-weight:600; }
    .kpi-card canvas { width:100%; height:420px; max-height:420px; }
    .kpi-scrollable-table { max-height: 300px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; background: white; }
    .kpi-scrollable-table table { width: 100%; border-collapse: collapse; }
    .kpi-scrollable-table th { position: sticky; top: 0; background: #f9fafb; z-index: 10; padding: 8px; border: 1px solid #e5e7eb; text-align: left; font-weight: 600; }
    .kpi-scrollable-table td { padding: 8px; border: 1px solid #e5e7eb; text-align: left; }
    .kpi-clear-host { position: relative !important; }
    .kpi-clear-btn { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); line-height: 1; padding: 0 8px; border: 0; background: transparent; color: var(--gray-600); cursor: pointer; border-radius: 6px; z-index: 2; }
    .kpi-clear-btn:hover { background: var(--gray-100); }
    .defective { background: #EF4444; color: white; }
    .rejected { background: #F97316; color: white; }
    @media (max-width: 1100px) { .kpi-filter-row { flex-direction: column; align-items: stretch; } }
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
    <div class="breadcrumb-bar" style="padding: 8px 16px; background: #f9fafb; border-bottom: 1px solid #e5e7eb; font-size: 14px; margin-bottom: 16px;">
      <a href="/app/kpi-hub" style="color: #1f2937; text-decoration: none;">KPI Hub</a>
      <span style="margin: 0 8px;">></span>
      <span style="color: #6b7280;">Defective and Rejections</span>
    </div>

    <div class="kpi-section">
      <h5>Filters</h5>
      <div class="kpi-filter-row" id="filters-row"></div>
    </div>

    <div class="kpi-section">
      <h5>Defective Units</h5>
      <div class="kpi-card">
        <div class="kpi-scrollable-table">
          <table class="kpi-table" id="defective-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Physical Cell</th>
                <th>Operation</th>
                <th>Sales Order</th>
                <th>Work Order</th>
                <th>Style</th>
                <th>Defective Units</th>
                <th>Scanned Units</th>
                <th>Defective %</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="kpi-section">
      <h5>Rejected Units</h5>
      <div class="kpi-card">
        <div class="kpi-scrollable-table">
          <table class="kpi-table" id="rejected-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Physical Cell</th>
                <th>Operation</th>
                <th>Sales Order</th>
                <th>Work Order</th>
                <th>Style</th>
                <th>Rejected Units</th>
                <th>Scanned Units</th>
                <th>Rejected %</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="kpi-section">
      <h5>Defective and Rejected Units Trend</h5>
      <div class="kpi-card">
        <canvas id="def-rej-chart"></canvas>
      </div>
    </div>
  `);

	// ========== FILTERS ==========
	let fDateRange, fPhysicalCell, fOperation, fWorkstation, fStyle, fSalesOrder, fWorkOrder;

	function createFilters() {
		// Get current month start and end dates
		const today = new Date();
		const currentYear = today.getFullYear();
		const currentMonth = today.getMonth(); // 0-indexed (0 = Jan, 11 = Dec)
		
		const monthStart = new Date(currentYear, currentMonth, 1);
		const monthEnd = new Date(currentYear, currentMonth + 1, 0); // Last day of current month
		
		// Format as YYYY-MM-DD
		const formatDate = (date) => {
			const year = date.getFullYear();
			const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
			const day = String(date.getDate()).padStart(2, '0');
			return `${year}-${month}-${day}`;
		};
		
		const defaultDateRange = [
			formatDate(monthStart),
			formatDate(monthEnd)
		];

		fDateRange = page.add_field({
			fieldtype: "DateRange",
			fieldname: "date_range",
			label: "Date Range",
			reqd: 1,
			default: defaultDateRange, // 👈 Set default to current month
		});

		fPhysicalCell = page.add_field({
			fieldtype: "Link",
			fieldname: "physical_cell",
			label: "Physical Cell",
			options: "Physical Cell",
		});
		fOperation = page.add_field({
			fieldtype: "Link",
			fieldname: "operation",
			label: "Operation",
			options: "Operation",
		});
		fWorkstation = page.add_field({
			fieldtype: "Data",
			fieldname: "workstation",
			label: "Workstation",
		});
		fStyle = page.add_field({
			fieldtype: "Link",
			fieldname: "style",
			label: "Style",
			options: "Item",
		});
		fSalesOrder = page.add_field({
			fieldtype: "Link",
			fieldname: "sales_order",
			label: "Sales Order",
			options: "Sales Order",
			filters: { docstatus: 1 },
		});
		fWorkOrder = page.add_field({
			fieldtype: "Link",
			fieldname: "work_order",
			label: "Work Order",
			options: "Work Order",
			filters: { docstatus: 1 },
		});

		// Append to DOM
		const $filtersRow = $mount.find("#filters-row");
		$filtersRow.append($("<div>").append(fDateRange.$wrapper));
		$filtersRow.append($("<div>").append(fPhysicalCell.$wrapper));
		$filtersRow.append($("<div>").append(fOperation.$wrapper));
		$filtersRow.append($("<div>").append(fWorkstation.$wrapper));
		$filtersRow.append($("<div>").append(fStyle.$wrapper));
		$filtersRow.append($("<div>").append(fSalesOrder.$wrapper));
		$filtersRow.append($("<div>").append(fWorkOrder.$wrapper));

		// Clear buttons
		attachClearButton(fDateRange, debouncedLoad);
		attachClearButton(fPhysicalCell, debouncedLoad);
		attachClearButton(fOperation, debouncedLoad);
		attachClearButton(fWorkstation, debouncedLoad);
		attachClearButton(fStyle, debouncedLoad);
		attachClearButton(fSalesOrder, debouncedLoad);
		attachClearButton(fWorkOrder, debouncedLoad);

		bindFilterEvents();
	}

	function bindFilterEvents() {
		const bind = (f) =>
			f?.$input && f.$input.on("input change awesomplete-selectcomplete", debouncedLoad);
		bind(fPhysicalCell);
		bind(fOperation);
		bind(fWorkstation);
		bind(fStyle);
		bind(fSalesOrder);
		bind(fWorkOrder);
		fDateRange.$input?.on("change", debouncedLoad);
	}

	// ========== UTIL ==========
	function pct(value, total) {
		const v = Number(value) || 0;
		const t = Number(total) || 0;
		return t > 0 ? ((v / t) * 100).toFixed(2) + "%" : "0.00%";
	}

	// ========== DATA ==========
	async function loadData() {
		if (!fDateRange.get_value()) {
			frappe.msgprint("Please select a Date Range");
			return;
		}

		try {
			const filters = {
				date_range: fDateRange.get_value(),
				physical_cell: fPhysicalCell.get_value(),
				operation: fOperation.get_value(),
				workstation: fWorkstation.get_value(),
				style: fStyle.get_value(),
				sales_order: fSalesOrder.get_value(),
				work_order: fWorkOrder.get_value(),
			};

			const resp = await frappe.call({
				method: "frappe.desk.query_report.run",
				args: { report_name: "Defective and Rejections", filters },
			});

			const map = {};
			(resp?.message?.report_summary || []).forEach((it) => {
				if (it?.name) map[it.name] = it.data;
			});

			loadDefectiveTable(map.defective_table || []);
			loadRejectedTable(map.rejected_table || []);
			renderDefectiveRejectedChart(map.defective_table || []);
		} catch (e) {
			console.error("❌ loadData:", e);
			frappe.show_alert({ message: "Failed to load data", indicator: "red" }, 5);
		}
	}

	// ========== RENDER TABLES ==========
	function loadDefectiveTable(data) {
		const $tbody = $mount.find("#defective-table tbody").empty();
		if (!data.length) {
			$tbody.append(`<tr><td colspan="9">No defective data found</td></tr>`);
			return;
		}

		data.forEach((row) => {
			$tbody.append(`
        <tr>
          <td>${row.date || "-"}</td>
          <td>${row.physical_cell || "-"}</td>
          <td>${row.operation || "-"}</td>
          <td>${row.sales_order || "-"}</td>
          <td>${row.work_order || "-"}</td>
          <td>${row.fty_prod_id || "-"}</td>
          <td class="defective">${row.defective_units || 0}</td>
          <td>${row.scanned_units || 0}</td>
          <td>${pct(row.defective_units, row.scanned_units)}</td>
        </tr>`);
		});
	}

	function loadRejectedTable(data) {
		const $tbody = $mount.find("#rejected-table tbody").empty();
		if (!data.length) {
			$tbody.append(`<tr><td colspan="9">No rejected data found</td></tr>`);
			return;
		}

		data.forEach((row) => {
			$tbody.append(`
        <tr>
          <td>${row.date || "-"}</td>
          <td>${row.physical_cell || "-"}</td>
          <td>${row.operation || "-"}</td>
          <td>${row.sales_order || "-"}</td>
          <td>${row.work_order || "-"}</td>
          <td>${row.fty_prod_id || "-"}</td>
          <td class="rejected">${row.rejected_units || 0}</td>
          <td>${row.scanned_units || 0}</td>
          <td>${pct(row.rejected_units, row.scanned_units)}</td>
        </tr>`);
		});
	}

	// ========== CHART ==========
	function renderDefectiveRejectedChart(defectiveData, rejectedData) {
		// If either dataset is empty, clear the chart
		if (!defectiveData || !defectiveData.length || !rejectedData || !rejectedData.length) {
			const ctx = document.getElementById("def-rej-chart")?.getContext("2d");
			if (ctx?.chart) ctx.chart.destroy();
			return;
		}

		// Create a map of all dates from both datasets
		const allDatesSet = new Set();
		defectiveData.forEach(row => allDatesSet.add(row.date));
		rejectedData.forEach(row => allDatesSet.add(row.date));
		const sortedDates = Array.from(allDatesSet).sort();

		// Create maps for quick lookup
		const defectiveMap = {};
		defectiveData.forEach(row => {
			defectiveMap[row.date] = {
				defective: row.defective_units || 0,
				scanned: row.scanned_units || 0
			};
		});

		const rejectedMap = {};
		rejectedData.forEach(row => {
			rejectedMap[row.date] = {
				rejected: row.rejected_units || 0,
				scanned: row.scanned_units || 0
			};
		});

		// Calculate percentages for each date
		const defectivePercentages = sortedDates.map(date => {
			const d = defectiveMap[date] || {defective: 0, scanned: 0};
			return d.scanned > 0 ? parseFloat(((d.defective / d.scanned) * 100).toFixed(2)) : 0;
		});

		const rejectedPercentages = sortedDates.map(date => {
			const r = rejectedMap[date] || {rejected: 0, scanned: 0};
			return r.scanned > 0 ? parseFloat(((r.rejected / r.scanned) * 100).toFixed(2)) : 0;
		});

		loadChartJs().then(() => {
			const canvas = document.getElementById("def-rej-chart");
			if (!canvas) return;
			const ctx = canvas.getContext("2d");
			if (ctx.chart) ctx.chart.destroy();

			ctx.chart = new Chart(ctx, {
				type: "bar",
				data: {
					labels: sortedDates,
					datasets: [
						{
							label: "Defective Unit %",
							data: defectivePercentages,
							backgroundColor: "#F97316", // Orange for defective
							borderColor: "#EA580C",							
							borderWidth: 1
						},
						{
							label: "Rejected Unit %",
							data: rejectedPercentages,
							backgroundColor: "#EF4444", // Red for rejected
							borderColor: "#DC2626",
							borderWidth: 1
						}
					]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: {
						title: { 
							display: true, 
							text: "Defective and Rejected Units Percentage Over Time"
						},
						legend: { position: "top" }
					},
					scales: {
						y: {
							beginAtZero: true,
							title: { display: true, text: "Percentage (%)" },
							ticks: {
								callback: function(value) {
									return value + '%';
								}
							}
						},
						x: {
							title: { display: true, text: "Date" }
						}
					}
				}
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
	const debouncedLoad = frappe.utils.debounce(() => {
		loadData();
	}, 400);

	// Initialize
	frappe.after_ajax(() => {
		createFilters();
		loadData(); // Load with default date range
	});

	// ---- expose cleanup for next remount ----
	wrapper.__dr_cleanup = () => {
		try {
			[fDateRange, fPhysicalCell, fOperation, fWorkstation, fStyle, fSalesOrder, fWorkOrder].forEach(
				(f) => f?._kpiClearObserver && f._kpiClearObserver.disconnect()
			);
		} catch {}
		$mount.find("#filters-row").off();
		$mount.remove();
	};
};