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
	$(".layout-main-section-wrapper").css({ "padding": "0", "margin": "" });
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

			<div class="tvd-filters">
				<div class="tvd-filter-group">
					<label class="tvd-filter-label">BUYER</label>
					<select class="tvd-filter-select" id="tvd-filter-buyer">
						<option value="">All Buyers</option>
					</select>
				</div>
				<div class="tvd-filter-group">
					<label class="tvd-filter-label">SEASON</label>
					<select class="tvd-filter-select" id="tvd-filter-season">
						<option value="">All Seasons</option>
					</select>
				</div>
				<div class="tvd-filter-group">
					<label class="tvd-filter-label">STYLE</label>
					<select class="tvd-filter-select" id="tvd-filter-style">
						<option value="">All Styles</option>
					</select>
				</div>
				<button class="tvd-filter-clear" id="tvd-filter-clear" title="Clear all filters">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
					</svg>
					Clear
				</button>
				<span class="tvd-filter-count" id="tvd-filter-count"></span>
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
							<th class="th-cell">KNITTING<br><span class="th-inout">OUT</span></th>
							<th class="th-cell">MENDING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">WASHING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">CUTTING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">LINKING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">SEWING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">EMBROIDERY<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">PRODUCTION<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">PRESSING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-cell">FINAL CHECK<br><span class="th-inout">OUT</span></th>
							<th class="th-cell">PACKING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-completion">COMP<br>%</th>
							<th class="th-lead">LEAD<br>DAYS</th>
						</tr>
					</thead>
					<tbody id="tvd-tbody">
						<tr><td colspan="20" class="tvd-state"><span class="tvd-spinner"></span> Loading data&hellip;</td></tr>
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

	// Filter change listeners
	$(wrapper).on("change", "#tvd-filter-buyer, #tvd-filter-season, #tvd-filter-style", function () {
		_applyFilters();
	});
	$(wrapper).on("click", "#tvd-filter-clear", function () {
		_clearFilters();
	});

	_startClock();
	_load();
	_timer = setInterval(function() { _load(); }, 60000);
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
};

var _timer   = null;
var _allRows = [];   // master copy of all rows from last server response

const CELLS = ["KNITTING","MENDING","WASHING","CUTTING","LINKING","SEWING","EMBROIDERY","PRODUCTION","PRESSING","FINAL CHECK","PACKING"];

// Cells that have only one operation — IN is meaningless, show "NA" instead
const SINGLE_OP_CELLS = ["KNITTING", "FINAL CHECK"];

const SCROLL_CONFIG = { step: 68, interval: 8000, pauseOnHover: true, edgePause: 2000 };
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
			_allRows = r.message || [];
			_populateFilters();
			_applyFilters();
			var n = new Date(), h = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#tvd-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

// ── Filter helpers ────────────────────────────────────────────────────────────

function _populateFilters() {
	var buyers   = _uniqueSorted(_allRows.map(function (r) { return r.buyer  || ""; }));
	var seasons  = _uniqueSorted(_allRows.map(function (r) { return r.season || ""; }));
	var styles   = _uniqueSorted(_allRows.map(function (r) { return r.style  || ""; }));

	_repopulateSelect("#tvd-filter-buyer",  buyers,  "All Buyers");
	_repopulateSelect("#tvd-filter-season", seasons, "All Seasons");
	_repopulateSelect("#tvd-filter-style",  styles,  "All Styles");
}

function _repopulateSelect(selector, values, placeholder) {
	var $sel   = $(selector);
	var current = $sel.val();
	var html   = '<option value="">' + placeholder + '</option>';
	values.forEach(function (v) {
		if (!v) return;
		var sel = (v === current) ? ' selected' : '';
		html += '<option value="' + _e(v) + '"' + sel + '>' + _e(v) + '</option>';
	});
	$sel.html(html);
}

function _applyFilters() {
	var buyer  = $("#tvd-filter-buyer").val()  || "";
	var season = $("#tvd-filter-season").val() || "";
	var style  = $("#tvd-filter-style").val()  || "";

	var filtered = _allRows.filter(function (r) {
		if (buyer  && (r.buyer  || "") !== buyer)  return false;
		if (season && (r.season || "") !== season) return false;
		if (style  && (r.style  || "") !== style)  return false;
		return true;
	});

	// Update the row count badge
	var total = _allRows.length;
	var shown = filtered.length;
	if (buyer || season || style) {
		$("#tvd-filter-count").text(shown + " of " + total + " rows").addClass("tvd-filter-count-active");
		$("#tvd-filter-clear").addClass("tvd-filter-clear-active");
	} else {
		$("#tvd-filter-count").text(total + " rows").removeClass("tvd-filter-count-active");
		$("#tvd-filter-clear").removeClass("tvd-filter-clear-active");
	}

	_render(filtered);
}

function _clearFilters() {
	$("#tvd-filter-buyer").val("");
	$("#tvd-filter-season").val("");
	$("#tvd-filter-style").val("");
	_applyFilters();
}

function _uniqueSorted(arr) {
	var seen = {}, out = [];
	arr.forEach(function (v) {
		if (v && !seen[v]) { seen[v] = true; out.push(v); }
	});
	return out.sort(function (a, b) { return a.localeCompare(b); });
}

// ── Render ────────────────────────────────────────────────────────────────────

function _render(rows) {
	if (!rows.length) {
		var hasFilter = $("#tvd-filter-buyer").val() || $("#tvd-filter-season").val() || $("#tvd-filter-style").val();
		_setState(hasFilter ? "No rows match the selected filters." : "No production data found.");
		return;
	}
	var html = "";
	rows.forEach(function (r) {
		html += '<tr class="tvd-row">';
		html += '<td class="td-buyer">' + _e(r.buyer) + "</td>";
		html += '<td class="td-season"><span class="szn ' + _seasonClass(r.season) + '">' + _e(r.season) + "</span></td>";
		html += '<td class="td-style td-style-clickable" data-style="' + _e(r.style) + '" data-colour="' + _e(r.colour) + '" title="Click for size-wise breakdown">' + _e(r.style) + "</td>";
		html += '<td class="td-colour"><span class="colour-badge">' + _e(r.colour) + "</span></td>";
		html += '<td class="td-delivery">' + _e(r.delivery_date) + "</td>";
		html += '<td class="td-qty">' + _n(r.order_qty) + "</td>";
		html += '<td class="td-qty">' + _n(r.planned_qty) + "</td>";
		var cellData = r.cells || {};
		CELLS.forEach(function (cell) {
			var c = cellData[cell] || {}, pct = c["pct"] || 0;
			var pClass = pct >= 100 ? "pct-green" : pct >= 95 ? "pct-yellow" : "pct-red";
			var isSingleOp = SINGLE_OP_CELLS.indexOf(cell) !== -1;
			html += '<td class="td-cell">';
			html += '<div class="cell-in cell-in-na">' + (isSingleOp ? "NA" : _n(c["in"])) + "</div>";
			html += '<div class="cell-line"></div>';
			html += '<div class="cell-out">' + _n(c["out"]) + "</div>";
			html += '<div class="cell-pct ' + pClass + '">' + pct + "%</div>";
			var daysVal = (c["days"] !== undefined && c["days"] !== null) ? "Days: " + c["days"] : "";
			html += '<div class="cell-days">' + daysVal + "</div>";
			html += "</td>";
		});
		var cp = parseFloat(r.completion_pct) || 0;
		var cpStr = Math.round(cp) + "%";
		var circ = 113.1, offset = (circ - (cp / 100) * circ).toFixed(1);
		var cc = cp >= 100 ? "cc-done" : cp >= 95 ? "cc-mid" : "cc-low";
		html += '<td class="td-completion"><div class="comp-wrap">';
		html += '<svg class="comp-svg" viewBox="0 0 44 44">';
		html += '<circle class="comp-bg" cx="22" cy="22" r="18"/>';
		html += '<circle class="comp-ring ' + cc + '" cx="22" cy="22" r="18" stroke-dasharray="' + circ + '" stroke-dashoffset="' + offset + '"/>';
		html += "</svg>";
		html += '<span class="comp-label ' + cc + '">' + cpStr + "</span>";
		html += "</div></td>";
		var ldVal = (r.lead_days !== undefined && r.lead_days !== null) ? r.lead_days : "-";
		html += '<td class="td-lead">' + ldVal + "</td></tr>";
	});
	$("#tvd-tbody").html(html);

	// Style cell click → size-wise popup
	$("#tvd-tbody").off("click.tvdStyle").on("click.tvdStyle", ".td-style-clickable", function () {
		var style  = $(this).data("style");
		var colour = $(this).data("colour");
		_showStyleSizewise(style, colour);
	});
}

function _setState(msg) { $("#tvd-tbody").html('<tr><td colspan="20" class="tvd-state">' + msg + "</td></tr>"); }
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

// ── Size-wise style popup ─────────────────────────────────────────────────────

function _closeSizewiseModal() {
	$("#tvd-sizewise-overlay").remove();
	$(document).off("keydown.tvdsizewise");
}

function _showStyleSizewise(style, colour) {
	_closeSizewiseModal();

	var $overlay = $(`
		<div id="tvd-sizewise-overlay" class="pd-sizewise-overlay">
			<div class="pd-sizewise-box">
				<div class="pd-sizewise-header">
					<div class="pd-sizewise-title-wrap">
						<span class="pd-popup-section-badge">${_e(style)}</span>
						<span class="pd-popup-title">Size-Wise Breakdown</span>
					</div>
					<button class="pd-popup-close" id="tvd-sizewise-close">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
							<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
						</svg>
					</button>
				</div>
				<div class="pd-sizewise-meta pd-sizewise-meta-loading">
					<span style="color:#64748b;font-size:12px;">Loading&hellip;</span>
				</div>
				<div class="pd-sizewise-body pd-sizewise-loading">
					<div class="tvd-spinner"></div> Loading&hellip;
				</div>
			</div>
		</div>
	`);
	$("body").append($overlay);

	$overlay.on("click", function (e) {
		if ($(e.target).is("#tvd-sizewise-overlay")) { _closeSizewiseModal(); }
	});
	$("#tvd-sizewise-close").on("click", function () { _closeSizewiseModal(); });
	$(document).off("keydown.tvdsizewise").on("keydown.tvdsizewise", function (e) {
		if (e.key === "Escape") { _closeSizewiseModal(); }
	});

	frappe.call({
		method: "analytix.analytix.page.production_dashboard.production_dashboard.get_style_sizewise_data",
		args: { style: style, colour: colour },
		freeze: false,
		callback: function (r) {
			var d = r.message;
			if (!d) {
				$("#tvd-sizewise-overlay .pd-sizewise-meta").html('<span style="color:#64748b;font-size:12px;">No data found.</span>');
				$("#tvd-sizewise-overlay .pd-sizewise-body").removeClass("pd-sizewise-loading").html('<p class="pd-detail-empty">No data found.</p>');
				return;
			}
			_renderSizewisePopup(d);
		},
	});
}

function _renderSizewisePopup(d) {
	var sizes = d.sizes || [];
	var cells = d.cells || [];

	var metaHtml = `
		<span class="pd-sw-meta-item"><span class="pd-sw-meta-lbl">BUYER</span><span class="pd-sw-meta-val">${_e(d.buyer)}</span></span>
		<span class="pd-sw-meta-item"><span class="pd-sw-meta-lbl">SEASON</span><span class="pd-sw-meta-val">${_e(d.season)}</span></span>
		<span class="pd-sw-meta-item"><span class="pd-sw-meta-lbl">STYLE</span><span class="pd-sw-meta-val">${_e(d.style)}</span></span>
		<span class="pd-sw-meta-item"><span class="pd-sw-meta-lbl">DELIVERY DATE</span><span class="pd-sw-meta-val">${_e(d.delivery_date)}</span></span>
		<span class="pd-sw-meta-item"><span class="pd-sw-meta-lbl">ORDER QTY</span><span class="pd-sw-meta-val">${_n(d.order_qty)}</span></span>
		<span class="pd-sw-meta-item"><span class="pd-sw-meta-lbl">PLANNED QTY</span><span class="pd-sw-meta-val">${_n(d.planned_qty)}</span></span>`;

	var thead = '<tr class="pd-sw-thead-row"><th class="pd-sw-th pd-sw-th-section">SECTION</th>';
	sizes.forEach(function (sz) { thead += '<th class="pd-sw-th pd-sw-th-size">' + _e(sz) + "</th>"; });
	thead += '<th class="pd-sw-th pd-sw-th-wip">WIP</th>';
	thead += '<th class="pd-sw-th pd-sw-th-completed">COMPLETED QTY</th>';
	thead += '<th class="pd-sw-th pd-sw-th-balance">COMPLETED %</th></tr>';

	var tbody = "";
	cells.forEach(function (cell) {
		var isOutsourced = !!cell.is_outsourced;

		var inTotDeviation = cell.total_in - d.order_qty;
		var inDevStr  = inTotDeviation >= 0 ? "+" + _n(inTotDeviation) : _n(inTotDeviation);
		var inBalCls  = cell.in_balance_pct >= 100 ? "pd-sw-bal-green" : cell.in_balance_pct >= 95 ? "pd-sw-bal-yellow" : "pd-sw-bal-red";
		tbody += '<tr class="pd-sw-row pd-sw-row-in' + (isOutsourced ? " pd-sw-row-outsourced" : "") + '">';
		tbody += '<td class="pd-sw-td pd-sw-section">' + _e(cell.cell) + ' <span class="pd-sw-dir">IN</span>';
		if (isOutsourced) { tbody += ' <span class="pd-sw-outsourced-badge" title="Outsourced — WIP not tracked">OS</span>'; }
		tbody += '</td>';
		sizes.forEach(function (sz) {
			var s  = (cell.in_by_size || {})[sz] || { qty: 0, pct: 0 };
			var pc = s.pct >= 100 ? "pd-sw-pct-green" : s.pct >= 95 ? "pd-sw-pct-yellow" : "pd-sw-pct-red";
			tbody += '<td class="pd-sw-td"><div class="pd-sw-size-cell"><span class="pd-sw-qty">' + _n(s.qty) + '</span><span class="pd-sw-pct ' + pc + '">' + s.pct + "%</span></div></td>";
		});
		if (isOutsourced) {
			tbody += '<td class="pd-sw-td pd-sw-wip"><span class="pd-sw-wip-zero pd-sw-outsourced-wip" title="Outsourced process — WIP not tracked">—</span></td>';
		} else {
			tbody += '<td class="pd-sw-td pd-sw-wip">' + (cell.wip_pending > 0 ? '<span class="pd-sw-wip-val pd-sw-wip-pending">' + _n(cell.wip_pending) + "</span>" : '<span class="pd-sw-wip-zero">—</span>') + "</td>";
		}
		tbody += '<td class="pd-sw-td pd-sw-completed"><span class="pd-sw-total">' + _n(cell.total_in) + '</span><span class="pd-sw-deviation">' + inDevStr + "</span></td>";
		tbody += '<td class="pd-sw-td pd-sw-balance"><span class="pd-sw-bal ' + inBalCls + '">' + cell.in_balance_pct + "%</span></td>";
		tbody += "</tr>";

		var outTotDeviation = cell.total_out - d.order_qty;
		var outDevStr  = outTotDeviation >= 0 ? "+" + _n(outTotDeviation) : _n(outTotDeviation);
		var outBalCls  = cell.out_balance_pct >= 100 ? "pd-sw-bal-green" : cell.out_balance_pct >= 95 ? "pd-sw-bal-yellow" : "pd-sw-bal-red";
		tbody += '<tr class="pd-sw-row pd-sw-row-out' + (isOutsourced ? " pd-sw-row-outsourced" : "") + '">';
		tbody += '<td class="pd-sw-td pd-sw-section">' + _e(cell.cell) + ' <span class="pd-sw-dir">OUT</span>';
		if (isOutsourced) { tbody += ' <span class="pd-sw-outsourced-badge" title="Outsourced — WIP not tracked">OS</span>'; }
		tbody += '</td>';
		sizes.forEach(function (sz) {
			var s  = (cell.out_by_size || {})[sz] || { qty: 0, pct: 0 };
			var pc = s.pct >= 100 ? "pd-sw-pct-green" : s.pct >= 95 ? "pd-sw-pct-yellow" : "pd-sw-pct-red";
			tbody += '<td class="pd-sw-td"><div class="pd-sw-size-cell"><span class="pd-sw-qty">' + _n(s.qty) + '</span><span class="pd-sw-pct ' + pc + '">' + s.pct + "%</span></div></td>";
		});
		if (isOutsourced) {
			tbody += '<td class="pd-sw-td pd-sw-wip"><span class="pd-sw-wip-zero pd-sw-outsourced-wip" title="Outsourced process — WIP not tracked">—</span></td>';
		} else {
			tbody += '<td class="pd-sw-td pd-sw-wip">' + (cell.wip_actual > 0 ? '<span class="pd-sw-wip-val pd-sw-wip-actual">' + _n(cell.wip_actual) + "</span>" : '<span class="pd-sw-wip-zero">—</span>') + "</td>";
		}
		tbody += '<td class="pd-sw-td pd-sw-completed"><span class="pd-sw-total">' + _n(cell.total_out) + '</span><span class="pd-sw-deviation">' + outDevStr + "</span></td>";
		tbody += '<td class="pd-sw-td pd-sw-balance"><span class="pd-sw-bal ' + outBalCls + '">' + cell.out_balance_pct + "%</span></td>";
		tbody += "</tr>";
	});

	$("#tvd-sizewise-overlay .pd-popup-title").text("Size-Wise: " + d.style);
	$("#tvd-sizewise-overlay .pd-sizewise-meta")
		.removeClass("pd-sizewise-meta-loading")
		.html(metaHtml);

	var tableHtml = `
		<div class="pd-sw-table-wrap">
			<table class="pd-sw-table">
				<thead>${thead}</thead>
				<tbody>${tbody}</tbody>
			</table>
		</div>`;

	$("#tvd-sizewise-overlay .pd-sizewise-body")
		.removeClass("pd-sizewise-loading")
		.html(tableHtml);
}