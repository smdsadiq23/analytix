frappe.pages['production-dashboard-by-size'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Production Dashboard by Size",
		single_column: true,
	});

	$(wrapper).find(".page-head").hide();

	// Full-viewport takeover
	$("header.navbar").hide();
	$(".page-body").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section-wrapper").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section").css({ "padding": "0", "margin": "0", "max-width": "100%" });
	$(wrapper).css({ "padding": "0", "margin": "0" });
	$(wrapper).find(".page-content").css({ "padding": "0", "margin": "0" });

	$(wrapper).find(".page-content").append(`
		<div class="lkd-root">
			<div class="lkd-topbar">
				<div class="lkd-brand">
					<svg class="lkd-brand-icon" width="38" height="38" viewBox="0 0 38 38" fill="none">
						<rect width="38" height="38" rx="9" fill="#00d4aa" fill-opacity="0.12"/>
						<path d="M10 19 Q14 12 19 19 Q24 26 28 19" stroke="#00d4aa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
						<circle cx="10" cy="19" r="2.5" fill="#00d4aa"/>
						<circle cx="28" cy="19" r="2.5" fill="#00d4aa"/>
					</svg>
					<div>
						<div class="lkd-brand-title" id="lkd-title">Production Dashboard by Size</div>
						<div class="lkd-brand-sub" id="lkd-sub">Real-time Cell Overview</div>
					</div>
				</div>
				<div class="lkd-clock">
					<div id="lkd-time">--:-- --</div>
					<div id="lkd-date">---</div>
				</div>
			</div>
			<div class="lkd-scroll">
				<table class="lkd-table">
					<thead>
						<tr class="lkd-head">
							<th class="th-buyer">BUYER</th>
							<th class="th-season">SEASON</th>
							<th class="th-style">STYLE</th>
							<th class="th-colour">COLOUR</th>
							<th class="th-delivery">DELIVERY</th>
							<th class="th-qty">ORDER<br>QTY</th>
							<th class="th-qty">PLANNED<br>QTY</th>
							<th class="th-sizes" id="lkd-sizes-header">CELL<br><span class="th-inout">IN / OUT per size</span></th>
							<th class="th-total">TOTAL<br>COMPLETION</th>
							<th class="th-completion">COMPLETION<br>%</th>
						</tr>
					</thead>
					<tbody id="lkd-tbody">
						<tr><td colspan="10" class="lkd-state"><span class="lkd-spinner"></span> Loading data&hellip;</td></tr>
					</tbody>
				</table>
			</div>
			<div class="lkd-footer">
				<span id="lkd-updated">Last updated: --</span>
				<span class="lkd-refresh-note">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
						<polyline points="23 4 23 10 17 10"/>
						<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
					</svg>
					Auto-refresh every 60s
				</span>
			</div>
		</div>
	`);

	_startClock();
};

frappe.pages["production-dashboard-by-size"].on_page_show = function (wrapper) {
	$("header.navbar").hide();
	$(".page-body").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section-wrapper").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section").css({ "padding": "0", "margin": "0", "max-width": "100%" });

	// ── Detect cell on every show ─────────────────────────────────────────
	// frappe.route_options is populated by Frappe's router on internal link
	// clicks (e.g. KPI Hub). Falls back to URL query string for direct/new-tab
	// loads, then defaults to KNITTING.
	var cellName = "KNITTING";
	if (frappe.route_options && frappe.route_options.cell) {
		cellName = frappe.route_options.cell.toString().toUpperCase();
		frappe.route_options = {};   // consume so it doesn't bleed into next nav
	} else {
		cellName = _getCellFromUrl() || "KNITTING";
	}

	_activeCell = cellName;
	_applyCell(cellName);

	if (_timer) { clearInterval(_timer); _timer = null; }
	_load(cellName);
	_resetAutoScroll();
	_timer = setInterval(function() { _load(_activeCell); /* _resetAutoScroll(); */ }, 60000);
};

frappe.pages["production-dashboard-by-size"].on_page_hide = function () {
	$("header.navbar").show();
	$(".page-body").css({ "padding": "", "margin": "" });
	$(".layout-main-section-wrapper").css({ "padding": "", "margin": "" });
	$(".layout-main-section").css({ "padding": "", "margin": "", "max-width": "" });
	if (_timer) { clearInterval(_timer); _timer = null; }
	_stopAutoScroll();
};

var _timer      = null;
var _activeCell = "KNITTING";   // tracks current cell across timer ticks

// Cells with only one operation — IN has no meaning, display "NA" instead
const SINGLE_OP_CELLS = ["KNITTING", "FINAL CHECK"];

const SCROLL_CONFIG = { step: 90, interval: 30000, pauseOnHover: true, edgePause: 2000 };
var _scrollTimer     = null;
var _scrollDirection = 1;
var _edgePauseTimer  = null;

// ── URL helper ────────────────────────────────────────────────────────────────
function _getCellFromUrl() {
	var search = window.location.search || "";
	var hash   = window.location.hash   || "";

	var m = search.match(/[?&]cell=([^&]+)/i);
	if (m) return decodeURIComponent(m[1]).toUpperCase();

	m = hash.match(/[?&]cell=([^&]+)/i);
	if (m) return decodeURIComponent(m[1]).toUpperCase();

	return null;
}

// ── Apply cell name to dynamic UI elements ────────────────────────────────────
function _applyCell(cellName) {
	$("#lkd-sub").text("Real-time " + _toTitleCase(cellName) + " Cell Overview");

	var isSingleOp = SINGLE_OP_CELLS.indexOf(cellName) !== -1;
	var subLabel   = isSingleOp ? "OUT per size" : "IN / OUT per size";
	$("#lkd-sizes-header").html(
		_e(cellName) + "<br><span class='th-inout'>" + subLabel + "</span>"
	);
}

function _toTitleCase(str) {
	return (str || "").toLowerCase().replace(/\b\w/g, function(c) { return c.toUpperCase(); });
}

// ── Clock ─────────────────────────────────────────────────────────────────────
function _startClock() { _tick(); setInterval(_tick, 1000); }
function _tick() {
	var d = new Date();
	var h = d.getHours(), m = String(d.getMinutes()).padStart(2, "0");
	var ampm = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
	var days   = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
	var months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
	$("#lkd-time").text(h + ":" + m + " " + ampm);
	$("#lkd-date").text(days[d.getDay()] + ", " + months[d.getMonth()] + " " + d.getDate());
}

// ── Data load ─────────────────────────────────────────────────────────────────
function _load(cellName) {
	frappe.call({
		method: "analytix.analytix.page.production_dashboard_by_size.production_dashboard_by_size.get_dashboard_data",
		args: { cell_name: cellName },
		freeze: false,
		callback: function (r) {
			if (r.exc) { _setState("&#9888; Failed to load data. Check server logs."); return; }
			_render(r.message || [], cellName);
			var n = new Date(), h = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#lkd-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

// ── Render ────────────────────────────────────────────────────────────────────
function _render(rows, cellName) {
	if (!rows.length) { _setState("No data found for this cell."); return; }

	var isSingleOp = SINGLE_OP_CELLS.indexOf(cellName) !== -1;
	var html = "";

	rows.forEach(function (r) {
		html += '<tr class="lkd-row">';
		html += '<td class="td-buyer">'    + _e(r.buyer)   + "</td>";
		html += '<td class="td-season"><span class="szn ' + _seasonClass(r.season) + '">' + _e(r.season) + "</span></td>";
		html += '<td class="td-style">'    + _e(r.style)   + "</td>";
		html += '<td class="td-colour"><span class="colour-badge">' + _e(r.colour) + "</span></td>";
		html += '<td class="td-delivery">' + _e(r.delivery_date) + "</td>";
		html += '<td class="td-qty">'      + _n(r.order_qty)   + "</td>";
		html += '<td class="td-qty">'      + _n(r.planned_qty) + "</td>";

		// ── Per-size grid ─────────────────────────────────────────────────
		html += '<td class="td-sizes"><div class="sz-grid">';
		(r.sizes || []).forEach(function (s) {
			var pct    = s.order_qty ? Math.round((s.out / s.order_qty) * 100) : 0;
			var pClass = pct >= 100 ? "pct-green" : pct >= 95 ? "pct-yellow" : "pct-red";
			html += '<div class="sz-col">';
			html += '<div class="sz-name">' + _e(s.size) + "</div>";
			if (isSingleOp) {
				html += '<div class="sz-in sz-in-na">NA</div>';
			} else {
				html += '<div class="sz-in">' + _n(s["in"]) + "</div>";
			}
			html += '<div class="sz-line"></div>';
			html += '<div class="sz-out">'              + _n(s.out) + "</div>";
			html += '<div class="sz-pct ' + pClass + '">' + pct    + "%</div>";
			html += "</div>";
		});
		html += "</div></td>";

		// ── Total Completion ──────────────────────────────────────────────
		html += '<td class="td-total">' + _n(r.total_cell_out) + "</td>";

		// ── Completion % gauge ────────────────────────────────────────────
		var cp    = parseFloat(r.completion_pct) || 0;
		var cpStr = Math.round(cp) + "%";
		var circ  = 113.1, offset = (circ - (cp / 100) * circ).toFixed(1);
		var cc    = cp >= 100 ? "cc-done" : cp >= 95 ? "cc-mid" : "cc-low";
		html += '<td class="td-completion"><div class="comp-wrap">';
		html += '<svg class="comp-svg" viewBox="0 0 44 44">';
		html += '<circle class="comp-bg" cx="22" cy="22" r="18"/>';
		html += '<circle class="comp-ring ' + cc + '" cx="22" cy="22" r="18" stroke-dasharray="' + circ + '" stroke-dashoffset="' + offset + '"/>';
		html += "</svg>";
		html += '<span class="comp-label ' + cc + '">' + cpStr + "</span>";
		html += "</div></td></tr>";
	});
	$("#lkd-tbody").html(html);
	_resetAutoScroll();
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function _setState(msg) { $("#lkd-tbody").html('<tr><td colspan="10" class="lkd-state">' + msg + "</td></tr>"); }
function _e(s) { return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function _n(v) { if (v === null || v === undefined || v === "") return "0"; return Number(v).toLocaleString("en-IN"); }
function _seasonClass(s) {
	var l = (s || "").toLowerCase();
	if (l.includes("spring")) return "szn-spring";
	if (l.includes("summer")) return "szn-summer";
	if (l.includes("winter")) return "szn-winter";
	if (l.includes("fall") || l.includes("autumn")) return "szn-fall";
	return "szn-default";
}

// ── Auto-scroll ───────────────────────────────────────────────────────────────
function _startAutoScroll() {
	_stopAutoScroll();
	var $container = $(".lkd-scroll");
	if (!$container.length) return;
	var maxScroll = $container[0].scrollHeight - $container[0].clientHeight;
	if (maxScroll <= 0) return;
	if (SCROLL_CONFIG.pauseOnHover) {
		$container.off("mouseenter.lkdScroll mouseleave.lkdScroll")
		          .on("mouseenter.lkdScroll", _stopAutoScroll)
		          .on("mouseleave.lkdScroll", _startAutoScroll);
	}
	_scrollTimer = setInterval(function() {
		var current = $container.scrollTop();
		var target  = current + (_scrollDirection * SCROLL_CONFIG.step);
		if (target >= maxScroll) {
			$container.scrollTop(maxScroll); _scrollDirection = -1;
			clearInterval(_scrollTimer); _scrollTimer = null;
			_edgePauseTimer = setTimeout(_startAutoScroll, SCROLL_CONFIG.edgePause); return;
		} else if (target <= 0) {
			$container.scrollTop(0); _scrollDirection = 1;
			clearInterval(_scrollTimer); _scrollTimer = null;
			_edgePauseTimer = setTimeout(_startAutoScroll, SCROLL_CONFIG.edgePause); return;
		}
		$container.scrollTop(target);
	}, SCROLL_CONFIG.interval);
}

function _stopAutoScroll() {
	if (_scrollTimer)    { clearInterval(_scrollTimer);    _scrollTimer    = null; }
	if (_edgePauseTimer) { clearTimeout(_edgePauseTimer);  _edgePauseTimer = null; }
	$(".lkd-scroll").off("mouseenter.lkdScroll mouseleave.lkdScroll");
}

function _resetAutoScroll() {
	_stopAutoScroll(); _scrollDirection = 1;
	var $container = $(".lkd-scroll");
	if ($container.length) { $container.scrollTop(0); setTimeout(_startAutoScroll, 300); }
}