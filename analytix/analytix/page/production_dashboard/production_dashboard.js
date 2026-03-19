frappe.pages["production-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Production Dashboard",
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
		<div class="tvd-root">
			<div class="tvd-topbar">
				<div class="tvd-brand">
					<svg class="tvd-brand-icon" width="38" height="38" viewBox="0 0 38 38" fill="none">
						<rect width="38" height="38" rx="9" fill="#00d4aa" fill-opacity="0.12"/>
						<path d="M8 22 L13 15 L18 20 L23 13 L30 22" stroke="#00d4aa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
						<circle cx="30" cy="22" r="2.5" fill="#00d4aa"/>
					</svg>
					<div>
						<div class="tvd-brand-title">Production Dashboard</div>
						<div class="tvd-brand-sub">Real-time Manufacturing Overview</div>
					</div>
				</div>
				<div class="tvd-clock">
					<div id="tvd-time">--:-- --</div>
					<div id="tvd-date">---</div>
				</div>
			</div>
			<div class="tvd-scroll">
				<table class="tvd-table">
					<thead>
						<tr class="tvd-head">
							<th class="th-buyer">BUYER</th>
							<th class="th-season">SEASON</th>
							<th class="th-style">STYLE</th>
							<th class="th-colour">COLOUR</th>
							<th class="th-delivery">DELIVERY</th>
							<th class="th-qty">ORDER<br>QTY</th>
							<th class="th-qty">PLANNED<br>QTY</th>
							<th class="th-cell">KNITTING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">MENDING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">WASHING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">CUTTING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">LINKING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">SEWING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">EMBROIDERY<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">PRODUCTION<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">PRESSING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">FINISHING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">PACKING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-completion">COMPLETION</th>
						</tr>
					</thead>
					<tbody id="tvd-tbody">
						<tr><td colspan="19" class="tvd-state"><span class="tvd-spinner"></span> Loading data&hellip;</td></tr>
					</tbody>
				</table>
			</div>
			<div class="tvd-footer">
				<span id="tvd-updated">Last updated: --</span>
				<span class="tvd-refresh-note">
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
	_load();
	_resetAutoScroll();
	_timer = setInterval(function() { _load(); _resetAutoScroll(); }, 60000);
};

frappe.pages["production-dashboard"].on_page_show = function (wrapper) {
	$("header.navbar").hide();
	$(".page-body").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section-wrapper").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section").css({ "padding": "0", "margin": "0", "max-width": "100%" });
};

frappe.pages["production-dashboard"].on_page_hide = function () {
	$("header.navbar").show();
	$(".page-body").css({ "padding": "", "margin": "" });
	$(".layout-main-section-wrapper").css({ "padding": "", "margin": "" });
	$(".layout-main-section").css({ "padding": "", "margin": "", "max-width": "" });
	if (_timer) { clearInterval(_timer); _timer = null; }
	_stopAutoScroll();
};

var _timer = null;

const CELLS = ["KNITTING","MENDING","WASHING","CUTTING","LINKING","SEWING","EMBROIDERY","PRODUCTION","PRESSING","FINISHING","PACKING"];

const SCROLL_CONFIG = { step: 66, interval: 5000, pauseOnHover: true, edgePause: 2000 };
var _scrollTimer = null;
var _scrollDirection = 1;
var _edgePauseTimer = null;

function _startClock() { _tick(); setInterval(_tick, 1000); }
function _tick() {
	var d = new Date();
	var h = d.getHours(), m = String(d.getMinutes()).padStart(2, "0");
	var ampm = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
	var days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
	var months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
	$("#tvd-time").text(h + ":" + m + " " + ampm);
	$("#tvd-date").text(days[d.getDay()] + ", " + months[d.getMonth()] + " " + d.getDate());
}

function _load() {
	frappe.call({
		method: "analytix.analytix.page.production_dashboard.production_dashboard.get_dashboard_data",
		freeze: false,
		callback: function (r) {
			if (r.exc) { _setState("&#9888; Failed to load data. Check server logs."); return; }
			_render(r.message || []);
			var n = new Date(), h = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#tvd-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

function _render(rows) {
	if (!rows.length) { _setState("No production data found."); return; }
	var html = "";
	rows.forEach(function (r) {
		html += '<tr class="tvd-row">';
		html += '<td class="td-buyer">' + _e(r.buyer) + "</td>";
		html += '<td class="td-season"><span class="szn ' + _seasonClass(r.season) + '">' + _e(r.season) + "</span></td>";
		html += '<td class="td-style">' + _e(r.style) + "</td>";
		html += '<td class="td-colour"><span class="colour-badge">' + _e(r.colour) + "</span></td>";
		html += '<td class="td-delivery">' + _e(r.delivery_date) + "</td>";
		html += '<td class="td-qty">' + _n(r.order_qty) + "</td>";
		html += '<td class="td-qty">' + _n(r.planned_qty) + "</td>";
		var cellData = r.cells || {};
		CELLS.forEach(function (cell) {
			var c = cellData[cell] || {}, pct = c["pct"] || 0;
			var pClass = pct >= 100 ? "pct-green" : pct >= 95 ? "pct-yellow" : "pct-red";
			html += '<td class="td-cell">';
			html += '<div class="cell-in">' + _n(c["in"]) + "</div>";
			html += '<div class="cell-line"></div>';
			html += '<div class="cell-out">' + _n(c["out"]) + "</div>";
			html += '<div class="cell-pct ' + pClass + '">' + pct + "%</div>";
			html += "</td>";
		});
		var cp = parseFloat(r.completion_pct) || 0;
		var cpStr = cp.toFixed(cp % 1 === 0 ? 0 : 1) + "%";
		var circ = 113.1, offset = (circ - (cp / 100) * circ).toFixed(1);
		var cc = cp >= 100 ? "cc-done" : cp >= 95 ? "cc-mid" : "cc-low";
		html += '<td class="td-completion"><div class="comp-wrap">';
		html += '<svg class="comp-svg" viewBox="0 0 44 44">';
		html += '<circle class="comp-bg" cx="22" cy="22" r="18"/>';
		html += '<circle class="comp-ring ' + cc + '" cx="22" cy="22" r="18" stroke-dasharray="' + circ + '" stroke-dashoffset="' + offset + '"/>';
		html += "</svg>";
		html += '<span class="comp-label ' + cc + '">' + cpStr + "</span>";
		html += "</div></td></tr>";
	});
	$("#tvd-tbody").html(html);
	_resetAutoScroll();
}

function _setState(msg) { $("#tvd-tbody").html('<tr><td colspan="19" class="tvd-state">' + msg + "</td></tr>"); }
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

function _startAutoScroll() {
	_stopAutoScroll();
	var $container = $(".tvd-scroll");
	if (!$container.length) return;
	var maxScroll = $container[0].scrollHeight - $container[0].clientHeight;
	if (maxScroll <= 0) return;
	if (SCROLL_CONFIG.pauseOnHover) {
		$container.off("mouseenter.tvdScroll mouseleave.tvdScroll")
		          .on("mouseenter.tvdScroll", _stopAutoScroll)
		          .on("mouseleave.tvdScroll", _startAutoScroll);
	}
	_scrollTimer = setInterval(function() {
		var current = $container.scrollTop();
		var target = current + (_scrollDirection * SCROLL_CONFIG.step);
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
	if (_scrollTimer) { clearInterval(_scrollTimer); _scrollTimer = null; }
	if (_edgePauseTimer) { clearTimeout(_edgePauseTimer); _edgePauseTimer = null; }
	$(".tvd-scroll").off("mouseenter.tvdScroll mouseleave.tvdScroll");
}

function _resetAutoScroll() {
	_stopAutoScroll(); _scrollDirection = 1;
	var $container = $(".tvd-scroll");
	if ($container.length) { $container.scrollTop(0); setTimeout(_startAutoScroll, 300); }
}