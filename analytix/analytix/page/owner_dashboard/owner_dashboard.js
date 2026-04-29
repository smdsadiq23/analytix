// ═══════════════════════════════════════════════════════════════════
//  Owner Dashboard  —  analytix / owner_dashboard
//  Grouped bar chart: Input vs Output vs Pending In (Ready for Input) vs WIP
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
						<span class="od-legend-hint">
							<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
							Click Input or Output bar for style breakdown
						</span>
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
		_startTimer();
	});
};

frappe.pages["owner-dashboard"].on_page_show = function (wrapper) {
	$("header.navbar").hide();
	$(".page-body").css({ padding: "0", margin: "0" });
	$(".layout-main-section-wrapper").css({ padding: "0", margin: "0" });
	$(".layout-main-section").css({ padding: "0", margin: "0", "max-width": "100%" });
	// Restart timer on every page show — prevents stacked intervals on re-navigation
	_startTimer();
};

frappe.pages["owner-dashboard"].on_page_hide = function () {
	$("header.navbar").show();
	$(".page-body").css({ padding: "", margin: "" });
	$(".layout-main-section-wrapper").css({ padding: "", margin: "" });
	$(".layout-main-section").css({ padding: "", margin: "", "max-width": "" });
	_stopTimer();
	_closeOdModal();
};

function _closeOdModal() {
	$("#od-modal-overlay").remove();
	$(document).off("keydown.oddetail");
}

// ── State ─────────────────────────────────────────────────────────────────────
var _timer       = null;
var _chartInst   = null;
var _lastData    = null;   // raw API response — kept for drilldown popups
var _sectionKeys = [];     // maps bar index → { key, label } for click drilldown

// ── Timer helpers ─────────────────────────────────────────────────────────────
// Always clear before setting so re-navigation never stacks two intervals.
function _startTimer() {
	_stopTimer();
	_timer = setInterval(function () { _load(); }, 60000);
}
function _stopTimer() {
	if (_timer) { clearInterval(_timer); _timer = null; }
}

// ── Section pipeline ──────────────────────────────────────────────────────────
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
	if (window.Chart && Chart.register) { cb(); return; }
	var s1 = document.createElement("script");
	s1.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js";
	s1.onload = function () {
		var s2 = document.createElement("script");
		s2.src = "https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js";
		s2.onload = function () {
			if (window.ChartDataLabels) { Chart.register(ChartDataLabels); }
			cb();
		};
		s2.onerror = function () { cb(); };
		document.head.appendChild(s2);
	};
	s1.onerror = function () {
		$("#od-loading").html('<span style="color:#ef4444">Failed to load Chart.js. Check network.</span>');
	};
	document.head.appendChild(s1);
}

// ── Data load ─────────────────────────────────────────────────────────────────
function _load() {
	var selectedDate = $("#od-date-input").val() || frappe.datetime.get_today();

	// Close any open modal on reload
	_closeOdModal();

	$("#od-refresh-btn").addClass("loading");

	// Only show the loading spinner on the very first load (no chart yet).
	// On auto-refresh the chart stays visible and updates silently in-place.
	if (!_chartInst) {
		$("#od-loading").show();
		$("#od-chart").hide();
	}

	frappe.call({
		method: "analytix.analytix.page.owner_dashboard.owner_dashboard.get_owner_dashboard_data",
		args: { date: selectedDate },
		freeze: false,
		callback: function (r) {
			$("#od-refresh-btn").removeClass("loading");
			if (r.exc) {
				if (!_chartInst) {
					$("#od-loading").html('<span style="color:#ef4444">&#9888; Failed to load data. Check server logs.</span>');
				}
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
	if (!data || Object.keys(data).length === 0) {
		if (!_chartInst) {
			$("#od-loading").html('<span>No production data available for selected date.</span>');
		}
		return;
	}

	_lastData = data;   // store for drilldown popups

	var d = new Date(selectedDate + "T00:00:00");
	var dayStr = d.getDate() + _ordinal(d.getDate()) + " " + _monthName(d.getMonth()) + " Production";
	$("#od-chart-title").text(dayStr + " \u2014 Input vs Output and Pending Qty");

	var prevDate = new Date(selectedDate + "T00:00:00");
	prevDate.setDate(prevDate.getDate() - 1);
	var prevLabel = prevDate.getDate().toString().padStart(2, "0") + "-" +
		(prevDate.getMonth() + 1).toString().padStart(2, "0") + "-" +
		prevDate.getFullYear();
	var selDay = d.getDate().toString().padStart(2, "0") + "-" +
		(d.getMonth() + 1).toString().padStart(2, "0") + "-" +
		d.getFullYear();

	// Labels are arrays — Chart.js renders each element on its own line,
	// giving horizontal wrapped text without any rotation.
	var labels = [], inputVals = [], outputVals = [], pendingVals = [], wipVals = [];

	// KNITTING — two separate bar groups, one per shift
	var kn = data["KNITTING"] || {};
	labels.push(["KNITTING", "(1st Shift)", selDay]);
	inputVals.push(null); outputVals.push(kn.shift1 || 0); pendingVals.push(null); wipVals.push(null);

	labels.push(["KNITTING", "(2nd Shift)", prevLabel]);
	inputVals.push(null); outputVals.push(kn.shift2 || 0); pendingVals.push(null); wipVals.push(null);

	// All other sections
	OD_SECTIONS.forEach(function (section) {
		if (section === "KNITTING") return;
		var key = OD_SECTION_KEY_MAP[section];
		var t = data[key] || {};

		// Split multi-word names onto two lines for compactness
		var parts = section.split(" ");
		var labelArr = parts.length > 1
			? [parts.slice(0, Math.ceil(parts.length / 2)).join(" "),
			   parts.slice(Math.ceil(parts.length / 2)).join(" ")]
			: [section];

		labels.push(labelArr);
		inputVals.push(t.input        != null ? t.input        : 0);
		outputVals.push(t.output      != null ? t.output       : 0);
		pendingVals.push(t.pending_in != null ? t.pending_in   : 0);
		wipVals.push(t.wip            != null ? t.wip          : 0);
	});

	_drawChart(labels, inputVals, outputVals, pendingVals, wipVals);
}

// ── Draw / update chart ───────────────────────────────────────────────────────
function _drawChart(labels, inputVals, outputVals, pendingVals, wipVals) {
	// Only toggle visibility on first draw; subsequent updates keep chart visible
	if (!_chartInst) {
		$("#od-loading").hide();
		$("#od-chart").show();
	}

	var ctx      = document.getElementById("od-chart").getContext("2d");
	var barThick = 28;
	var fontSize = 10;

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
			onClick: function (evt, elements) {
				if (!elements || !elements.length) return;
				var el         = elements[0];
				var barIdx     = el.index;
				var datasetIdx = el.datasetIndex;
				// Dataset 0=Input, 1=Output, 2=Ready for Input, 3=WIP
				var metricMap  = { 0: "input", 1: "output", 2: "pending_in", 3: "wip" };
				var metricType = metricMap[datasetIdx];
				if (!metricType) return;
				var info = _sectionKeys[barIdx];
				if (!info || !info.key) return;
				_showOdDrilldown(info.label, info.key, metricType);
			},
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
						// Join array labels back into a single string for the tooltip title
						title: function (items) {
							var lbl = items[0].label;
							return Array.isArray(lbl) ? lbl.join(" ") : lbl;
						},
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
						// Horizontal wrapped labels: maxRotation 0 keeps text upright;
						// Chart.js natively renders label arrays as multi-line text.
						maxRotation: 0,
						minRotation: 0,
						autoSkip: false,
						color: "#374151",
						font: { size: 10.5, weight: "600", family: "'Segoe UI', system-ui, sans-serif" },
					},
					border: { display: false },
				},
				y: {
					beginAtZero: true,
					grid: { color: "rgba(0,0,0,0.06)", drawTicks: false },
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

	// Build _sectionKeys after creating chart — mirrors label array order
	// KNITTING Shift 1, KNITTING Shift 2, then each other section
	_sectionKeys = [];
	_sectionKeys.push({ key: null, label: "KNITTING" });  // Shift 1 — no input drilldown
	_sectionKeys.push({ key: null, label: "KNITTING" });  // Shift 2 — no input drilldown
	OD_SECTIONS.forEach(function (section) {
		if (section === "KNITTING") return;
		_sectionKeys.push({ key: OD_SECTION_KEY_MAP[section], label: section });
	});
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
function _odE(s) {
	return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function _odN(v) {
	if (v === null || v === undefined || v === "") return "0";
	return Number(v).toLocaleString("en-IN");
}

// ── Drilldown popup ───────────────────────────────────────────────────────────
function _showOdDrilldown(sectionLabel, sectionKey, metricType) {
	if (!_lastData || !sectionKey) return;

	// Toggle: clicking same metric+section closes the popup
	var $existing = $("#od-modal-overlay");
	if ($existing.length &&
		$existing.data("active-key") === sectionKey &&
		$existing.data("active-metric") === metricType) {
		_closeOdModal();
		return;
	}
	$existing.remove();

	var cellData  = _lastData[sectionKey] || {};
	var drilldown = cellData.drilldown    || [];

	// ── Per-metric config ─────────────────────────────────────────────────
	var METRIC = {
		"input":      { label: "Input",          qtyField: "input_qty",   thBadge: "od-popup-th-cyan",   valCls: "od-popup-val-cyan",   sumCls: "od-popup-summary-cyan",   sumTotal: cellData.input      || 0 },
		"output":     { label: "Output",          qtyField: "output_qty",  thBadge: "od-popup-th-green",  valCls: "od-popup-val-green",  sumCls: "od-popup-summary-green",  sumTotal: cellData.output     || 0 },
		"pending_in": { label: "Ready for Input", qtyField: "pending_qty", thBadge: "od-popup-th-red",    valCls: "od-popup-val-red",    sumCls: "od-popup-summary-red",    sumTotal: cellData.pending_in || 0 },
		"wip":        { label: "WIP",             qtyField: "wip_qty",     thBadge: "od-popup-th-purple", valCls: "od-popup-val-purple", sumCls: "od-popup-summary-purple", sumTotal: cellData.wip        || 0 },
	};

	var cfg = METRIC[metricType];
	if (!cfg) return;

	// For pending_in / wip the drilldown data comes from the Python
	// per-style breakdown — for now show input breakdown as the closest proxy
	// (same style list that contributed to those totals).
	var rows = drilldown.filter(function(r) { return r[cfg.qtyField] > 0; });
	rows.sort(function(a, b) { return b[cfg.qtyField] - a[cfg.qtyField]; });

	var tableHtml;
	if (!rows.length) {
		tableHtml = '<p class="od-detail-empty">No data for this section today.</p>';
	} else {
		var tbody = rows.map(function(r) {
			var qty = r[cfg.qtyField];
			var valCls = qty > 0 ? cfg.valCls : "od-popup-val-zero";
			return '<tr>' +
				'<td class="od-popup-td od-popup-style">'  + _odE(r.style)  + '</td>' +
				'<td class="od-popup-td od-popup-colour">' + _odE(r.colour) + '</td>' +
				'<td class="od-popup-td od-popup-buyer">'  + _odE(r.buyer)  + '</td>' +
				'<td class="od-popup-td od-popup-num ' + valCls + '">' + _odN(qty) + '</td>' +
			'</tr>';
		}).join("");

		tableHtml =
			'<div class="od-popup-table-wrap">' +
				'<table class="od-popup-table">' +
					'<thead><tr>' +
						'<th class="od-popup-th">Style</th>' +
						'<th class="od-popup-th">Colour</th>' +
						'<th class="od-popup-th">Buyer</th>' +
						'<th class="od-popup-th od-popup-num">' +
							'<span class="od-popup-th-badge ' + cfg.thBadge + '">' + cfg.label + ' Qty</span>' +
						'</th>' +
					'</tr></thead>' +
					'<tbody>' + tbody + '</tbody>' +
				'</table>' +
			'</div>';
	}

	var summaryHtml =
		'<div class="od-popup-summary">' +
			'<div class="od-popup-summary-item ' + cfg.sumCls + '">' +
				'<div class="od-popup-summary-val">' + _odN(cfg.sumTotal) + '</div>' +
				'<div class="od-popup-summary-lbl">Total ' + cfg.label + '</div>' +
			'</div>' +
		'</div>';

	var $overlay = $('<div id="od-modal-overlay" class="od-modal-overlay">' +
		'<div class="od-modal-box">' +
			'<div class="od-detail-header">' +
				'<div class="od-detail-title-wrap">' +
					'<span class="od-popup-section-badge">' + _odE(sectionLabel) + '</span>' +
					'<span class="od-popup-title">' + cfg.label + ' — Style-wise Breakdown</span>' +
				'</div>' +
				summaryHtml +
				'<button class="od-popup-close" id="od-detail-close" title="Close">' +
					'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">' +
						'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>' +
					'</svg>' +
				'</button>' +
			'</div>' +
			'<div class="od-detail-body">' + tableHtml + '</div>' +
		'</div>' +
	'</div>');

	$overlay.data("active-key",    sectionKey);
	$overlay.data("active-metric", metricType);
	$("body").append($overlay);

	$overlay.on("click", function(e) {
		if ($(e.target).is("#od-modal-overlay")) { _closeOdModal(); }
	});
	$("#od-detail-close").on("click", function() { _closeOdModal(); });
	$(document).off("keydown.oddetail").on("keydown.oddetail", function(e) {
		if (e.key === "Escape") { _closeOdModal(); }
	});
}