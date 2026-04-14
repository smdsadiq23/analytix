// ═══════════════════════════════════════════════════════════════════
//  Owner Dashboard  —  analytix / owner_dashboard
//  Grouped bar chart: Input vs Output vs Pending In (Ready for Input) vs WIP
//  Reuses shopfloor_performance.get_dashboard_data on the backend.
// ═══════════════════════════════════════════════════════════════════

frappe.pages["owner-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Owner Dashboard",
		single_column: true,
	});

	$(wrapper).find(".page-head").hide();
	$("header.navbar").hide();
	$(".page-body").css({ padding: "0", margin: "0" });
	$(".layout-main-section-wrapper").css({ padding: "0", margin: "0" });
	$(".layout-main-section").css({ padding: "0", margin: "0", "max-width": "100%" });
	$(wrapper).css({ padding: "0", margin: "0" });
	$(wrapper).find(".page-content").css({ padding: "0", margin: "0" });

	$(wrapper).find(".page-content").append(`
		<div class="od-root">
			<div class="od-header">
				<div class="od-header-left">
					<div class="od-logo">
						<svg width="38" height="38" viewBox="0 0 38 38" fill="none">
							<rect width="38" height="38" rx="9" fill="#1a2744"/>
							<rect x="7" y="24" width="5" height="8" rx="1.5" fill="#3b82f6" opacity="0.5"/>
							<rect x="14" y="18" width="5" height="14" rx="1.5" fill="#22c55e" opacity="0.7"/>
							<rect x="21" y="13" width="5" height="19" rx="1.5" fill="#ef4444" opacity="0.7"/>
							<rect x="28" y="8" width="5" height="24" rx="1.5" fill="#8b5cf6" opacity="0.7"/>
							<polyline points="9.5,20 16.5,14 23.5,10 30.5,6" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.8"/>
						</svg>
					</div>
					<div class="od-header-text">
						<div class="od-title">Owner Dashboard</div>
						<div class="od-subtitle">Daily production overview — Input · Output · Pending In · WIP</div>
					</div>
				</div>
				<div class="od-header-right">
					<div class="od-date-picker-wrap">
						<label class="od-date-label">
							<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
							</svg>
							Select Date
						</label>
						<input type="date" id="od-date-input" class="od-date-input"/>
					</div>
					<button class="od-refresh-btn" id="od-refresh-btn">
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
						</svg>
						Refresh
					</button>
				</div>
			</div>

			<div class="od-chart-card" id="od-chart-card">
				<div class="od-chart-card-header">
					<div class="od-chart-card-title" id="od-chart-title">Production — Input vs Output and Pending Qty</div>
					<div class="od-legend">
						<span class="od-legend-item"><span class="od-legend-dot" style="background:#06b6d4"></span>Input</span>
						<span class="od-legend-item"><span class="od-legend-dot" style="background:#22c55e"></span>Output</span>
						<span class="od-legend-item"><span class="od-legend-dot" style="background:#ef4444"></span>Ready for Input</span>
						<span class="od-legend-item"><span class="od-legend-dot" style="background:#8b5cf6"></span>WIP</span>
					</div>
				</div>
				<div class="od-canvas-wrap" id="od-canvas-wrap">
					<div class="od-loading" id="od-loading">
						<div class="od-spinner"></div>
						<span>Loading production data…</span>
					</div>
					<canvas id="od-chart" style="display:none;"></canvas>
				</div>
			</div>

			<div class="od-footer-bar">
				<span id="od-updated">Last updated: --</span>
				<span class="od-auto-note">
					<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
						<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
					</svg>
					Auto-refresh every 60s
				</span>
			</div>
		</div>
	`);

	var today = frappe.datetime.get_today();
	$("#od-date-input").val(today);

	$("#od-date-input").on("change", function () { _load(); });
	$("#od-refresh-btn").on("click", function () { _load(); });

	_ensureChartJS(function () {
		_load();
		_timer = setInterval(function () { _load(); }, 60000);
	});
};

frappe.pages["owner-dashboard"].on_page_show = function (wrapper) {
	$("header.navbar").hide();
	$(".page-body").css({ padding: "0", margin: "0" });
	$(".layout-main-section-wrapper").css({ padding: "0", margin: "0" });
	$(".layout-main-section").css({ padding: "0", margin: "0", "max-width": "100%" });
};

frappe.pages["owner-dashboard"].on_page_hide = function () {
	$("header.navbar").show();
	$(".page-body").css({ padding: "", margin: "" });
	$(".layout-main-section-wrapper").css({ padding: "", margin: "" });
	$(".layout-main-section").css({ padding: "", margin: "", "max-width": "" });
	if (_timer) { clearInterval(_timer); _timer = null; }
};

// ── State ─────────────────────────────────────────────────────────────────────
var _timer    = null;
var _chartInst = null;   // Chart.js instance

// ── Section pipeline (matches shopfloor_performance SECTIONS) ─────────────────
const OD_SECTIONS = [
	"KNITTING",
	"MENDING",
	"WASHING",
	"CUTTING",
	"LINKING",
	"SEWING",
	"EMBROIDERY",
	"PRODUCTION OUT",
	"PRESSING",
	"FINAL CHECKING",
	"PACKING",
];

const OD_SECTION_KEY_MAP = {
	"KNITTING":       "KNITTING",
	"MENDING":        "MENDING",
	"WASHING":        "WASHING",
	"CUTTING":        "CUTTING",
	"LINKING":        "LINKING",
	"SEWING":         "SEWING",
	"EMBROIDERY":     "EMBROIDERY",
	"PRODUCTION OUT": "PRODUCTION",
	"PRESSING":       "PRESSING",
	"FINAL CHECKING": "FINAL CHECK",
	"PACKING":        "PACKING",
};

// ── Chart.js lazy-load ────────────────────────────────────────────────────────
function _ensureChartJS(cb) {
	if (window.Chart && Chart.register) {
		cb();
		return;
	}
	// Load Chart.js + datalabels plugin from CDN
	var s1 = document.createElement("script");
	s1.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js";
	s1.onload = function () {
		var s2 = document.createElement("script");
		s2.src = "https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js";
		s2.onload = function () {
			if (window.ChartDataLabels) {
				Chart.register(ChartDataLabels);
			}
			cb();
		};
		s2.onerror = function () { cb(); };   // proceed without labels
		document.head.appendChild(s2);
	};
	s1.onerror = function () {
		$("#od-loading").html('<span style="color:#ef4444">Failed to load Chart.js. Check network.</span>');
	};
	document.head.appendChild(s1);
}

// ── Data load ────────────────────────────────────────────────────────────────
function _load() {
	var selectedDate = $("#od-date-input").val() || frappe.datetime.get_today();

	$("#od-refresh-btn").addClass("loading");
	$("#od-loading").show();
	$("#od-chart").hide();

	frappe.call({
		method: "analytix.analytix.page.shopfloor_performance.shopfloor_performance.get_dashboard_data",
		args: { date: selectedDate },
		freeze: false,
		callback: function (r) {
			$("#od-refresh-btn").removeClass("loading");
			if (r.exc) {
				$("#od-loading").html('<span style="color:#ef4444">&#9888; Failed to load data. Check server logs.</span>');
				return;
			}
			_render(r.message || [], selectedDate);
			var n = new Date(), h = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#od-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

// ── Render ────────────────────────────────────────────────────────────────────
function _render(data, selectedDate) {
	if (!data || (Array.isArray(data) && !data.length)) {
		$("#od-loading").html('<span>No production data available for selected date.</span>');
		return;
	}

	// ── Update chart title with date ──────────────────────────────────────
	var d = new Date(selectedDate + "T00:00:00");
	var dayStr = d.getDate() + _ordinal(d.getDate()) + " " + _monthName(d.getMonth()) + " Production";
	$("#od-chart-title").text(dayStr + " — Input vs Output and Pending Qty");

	// ── Aggregate totals (same logic as shopfloor_performance.js) ────────
	var totals = _aggregateTotals(data);

	// ── Previous day label for Knitting Shift 2 ───────────────────────────
	var prevDate = new Date(selectedDate + "T00:00:00");
	prevDate.setDate(prevDate.getDate() - 1);
	var prevLabel = prevDate.getDate().toString().padStart(2, "0") + "-" +
		(prevDate.getMonth() + 1).toString().padStart(2, "0") + "-" +
		prevDate.getFullYear();

	var selDay = d.getDate().toString().padStart(2, "0") + "-" +
		(d.getMonth() + 1).toString().padStart(2, "0") + "-" +
		d.getFullYear();

	// ── Build chart labels & series ───────────────────────────────────────
	var labels = [];
	var inputVals    = [];
	var outputVals   = [];
	var pendingVals  = [];  // pending_in = "ready for input"
	var wipVals      = [];

	// KNITTING: two pseudo-sections for shift 1 and shift 2
	var kn = totals["KNITTING"] || {};
	labels.push("KNITTING\n(1st Shift · " + selDay + ")");
	inputVals.push(null);
	outputVals.push(kn.shift1 || 0);
	pendingVals.push(null);
	wipVals.push(null);

	labels.push("KNITTING\n(2nd Shift · " + prevLabel + ")");
	inputVals.push(null);
	outputVals.push(kn.shift2 || 0);
	pendingVals.push(null);
	wipVals.push(null);

	// All other sections
	OD_SECTIONS.forEach(function (section) {
		if (section === "KNITTING") return;
		var key = OD_SECTION_KEY_MAP[section];
		var t = totals[key] || {};
		labels.push(section);
		inputVals.push(t.input   || 0);
		outputVals.push(t.output  || 0);
		pendingVals.push(t.pendingIn || 0);
		wipVals.push(t.wip    || 0);
	});

	// ── Draw / update chart ───────────────────────────────────────────────
	_drawChart(labels, inputVals, outputVals, pendingVals, wipVals);
}

function _drawChart(labels, inputVals, outputVals, pendingVals, wipVals) {
	$("#od-loading").hide();
	var $canvas = $("#od-chart");
	$canvas.show();

	var ctx = document.getElementById("od-chart").getContext("2d");

	var fontSize   = 10;
	var barThick   = 28;

	var datasets = [
		{
			label: "Input",
			data: inputVals,
			backgroundColor: "rgba(6,182,212,0.85)",
			borderRadius: 3,
			borderSkipped: false,
			barThickness: barThick,
		},
		{
			label: "Output",
			data: outputVals,
			backgroundColor: "rgba(34,197,94,0.85)",
			borderRadius: 3,
			borderSkipped: false,
			barThickness: barThick,
		},
		{
			label: "Ready for Input",
			data: pendingVals,
			backgroundColor: "rgba(239,68,68,0.85)",
			borderRadius: 3,
			borderSkipped: false,
			barThickness: barThick,
		},
		{
			label: "WIP",
			data: wipVals,
			backgroundColor: "rgba(139,92,246,0.85)",
			borderRadius: 3,
			borderSkipped: false,
			barThickness: barThick,
		},
	];

	var datalabelsConfig = {
		anchor: "end",
		align: "top",
		offset: 2,
		color: "#374151",
		font: { size: fontSize, weight: "600", family: "'Segoe UI', system-ui, sans-serif" },
		formatter: function (val) {
			if (val === null || val === undefined) return "";
			if (val === 0) return "0";
			return Number(val).toLocaleString("en-IN");
		},
		clip: false,
	};

	if (_chartInst) {
		_chartInst.data.labels   = labels;
		_chartInst.data.datasets = datasets;
		_chartInst.update();
		return;
	}

	_chartInst = new Chart(ctx, {
		type: "bar",
		data: { labels: labels, datasets: datasets },
		options: {
			responsive: true,
			maintainAspectRatio: false,
			animation: { duration: 600 },
			layout: { padding: { top: 24, right: 16, bottom: 0, left: 8 } },
			plugins: {
				legend: { display: false },
				tooltip: {
					backgroundColor: "rgba(15,23,42,0.92)",
					titleColor: "#e2e8f0",
					bodyColor: "#94a3b8",
					borderColor: "rgba(59,130,246,0.3)",
					borderWidth: 1,
					padding: 10,
					callbacks: {
						label: function (ctx) {
							if (ctx.raw === null) return null;
							return " " + ctx.dataset.label + ": " + Number(ctx.raw).toLocaleString("en-IN");
						},
					},
					filter: function (item) { return item.raw !== null; },
				},
				datalabels: datalabelsConfig,
			},
			scales: {
				x: {
					grid: { display: false },
					ticks: {
						color: "#374151",
						font: { size: 10.5, weight: "600", family: "'Segoe UI', system-ui, sans-serif" },
						maxRotation: 0,
						minRotation: 0,
						autoSkip: false,
					},
					border: { display: false },
				},
				y: {
					beginAtZero: true,
					grid: {
						color: "rgba(0,0,0,0.06)",
						drawTicks: false,
					},
					ticks: {
						color: "#6b7280",
						font: { size: 10, family: "'Segoe UI', system-ui, sans-serif" },
						padding: 8,
						callback: function (v) { return Number(v).toLocaleString("en-IN"); },
					},
					border: { display: false, dash: [4, 4] },
				},
			},
		},
	});
}

// ── Aggregate totals (mirrors shopfloor_performance aggregation logic) ────────
function _aggregateTotals(rows) {
	var totals = {};
	OD_SECTIONS.forEach(function (section) {
		var key = OD_SECTION_KEY_MAP[section];
		totals[key] = { input: 0, output: 0, cum_out: 0, wip: 0, pendingIn: 0, mtd: 0, ytd: 0 };
	});

	rows.forEach(function (r) {
		var cells = r.cells || {};
		OD_SECTIONS.forEach(function (section) {
			if (section === "KNITTING") return;
			var key = OD_SECTION_KEY_MAP[section];
			var c = cells[key] || {};
			totals[key].input     += (c["in"]         || 0);
			totals[key].output    += (c["out"]        || 0);
			totals[key].cum_out   += (c["cum_out"]    || 0);
			totals[key].mtd       += (c["mtd"]        || 0);
			totals[key].ytd       += (c["ytd"]        || 0);
			// pending_in from backend = "ready for input"
			if (c["pending_in"] != null && c["pending_in"] > 0) {
				totals[key].pendingIn += c["pending_in"];
			}
		});
	});

	// ── Build applicable-cell set (for WIP calc) ──────────────────────────
	var applicableCellKeys = new Set(["KNITTING"]);
	rows.forEach(function (r) {
		var cells = r.cells || {};
		OD_SECTIONS.forEach(function (section) {
			var key = OD_SECTION_KEY_MAP[section];
			if ((cells[key] || {})["applicable"]) applicableCellKeys.add(key);
		});
	});

	// ── WIP = prev applicable cum_out − current cum_out ───────────────────
	OD_SECTIONS.forEach(function (section, i) {
		if (section === "KNITTING") return;
		var key = OD_SECTION_KEY_MAP[section];
		if (!applicableCellKeys.has(key)) { totals[key].wip = 0; return; }
		var prevCumOut = 0;
		for (var j = i - 1; j >= 0; j--) {
			var prevKey = OD_SECTION_KEY_MAP[OD_SECTIONS[j]];
			if (applicableCellKeys.has(prevKey)) {
				prevCumOut = totals[prevKey].cum_out || 0;
				break;
			}
		}
		var wip = prevCumOut - (totals[key].cum_out || 0);
		totals[key].wip = wip < 0 ? 0 : wip;
	});

	// ── KNITTING: aggregate from shift fields ─────────────────────────────
	totals["KNITTING"].shift1 = 0;
	totals["KNITTING"].shift2 = 0;
	rows.forEach(function (r) {
		totals["KNITTING"].shift1 += (r.knitting_shift1 || 0);
		totals["KNITTING"].shift2 += (r.knitting_shift2 || 0);
	});

	return totals;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function _ordinal(n) {
	var s = ["th","st","nd","rd"], v = n % 100;
	return (s[(v-20)%10] || s[v] || s[0]);
}
function _monthName(m) {
	return ["January","February","March","April","May","June",
		"July","August","September","October","November","December"][m];
}
