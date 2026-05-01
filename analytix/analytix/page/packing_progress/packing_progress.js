frappe.pages["packing-progress"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Packing Progress",
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

	// colspan = 7 identity cols + 11 op cols + 1 total + 1 rej + 1 packed = 21
	$(wrapper).find(".page-content").append(`
		<div class="ppd-root">
			<div class="ppd-topbar">
				<div class="ppd-brand">
					<svg class="ppd-brand-icon" width="38" height="38" viewBox="0 0 38 38" fill="none">
						<rect width="38" height="38" rx="9" fill="#00d4aa" fill-opacity="0.12"/>
						<rect x="9" y="14" width="20" height="16" rx="2" stroke="#00d4aa" stroke-width="2.2" fill="none"/>
						<path d="M14 14v-2a5 5 0 0 1 10 0v2" stroke="#00d4aa" stroke-width="2.2" stroke-linecap="round" fill="none"/>
						<path d="M14 21h10M14 25h6" stroke="#00d4aa" stroke-width="1.8" stroke-linecap="round"/>
					</svg>
					<div>
						<div class="ppd-brand-title">Packing Progress</div>
						<div class="ppd-brand-sub">Real-time Packing Status Overview</div>
					</div>
				</div>
				<div class="ppd-clock">
					<div id="ppd-time">--:-- --</div>
					<div id="ppd-date">---</div>
				</div>
			</div>

			<div class="ppd-filters">
				<div class="ppd-filter-group">
					<label class="ppd-filter-label">BUYER</label>
					<select class="ppd-filter-select" id="ppd-filter-buyer">
						<option value="">All Buyers</option>
					</select>
				</div>
				<div class="ppd-filter-group">
					<label class="ppd-filter-label">SEASON</label>
					<select class="ppd-filter-select" id="ppd-filter-season">
						<option value="">All Seasons</option>
					</select>
				</div>
				<div class="ppd-filter-group">
					<label class="ppd-filter-label">STYLE</label>
					<select class="ppd-filter-select" id="ppd-filter-style">
						<option value="">All Styles</option>
					</select>
				</div>
				<div class="ppd-filter-group">
					<label class="ppd-filter-label">DELIVERY DATE</label>
					<input type="date" class="ppd-filter-date" id="ppd-filter-delivery">
				</div>
				<button class="ppd-filter-clear" id="ppd-filter-clear" title="Clear all filters">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
					</svg>
					Clear
				</button>
				<span class="ppd-filter-count" id="ppd-filter-count"></span>
			</div>

			<div class="ppd-scroll">
				<table class="ppd-table">
					<thead>
						<tr class="ppd-head">
							<th class="th-buyer">BUYER</th>
							<th class="th-season">SEASON</th>
							<th class="th-style">STYLE</th>
							<th class="th-colour">COLOUR</th>
							<th class="th-delivery">DELIVERY</th>
							<th class="th-qty">ORDER<br>QTY</th>
							<th class="th-qty">PLANNED<br>QTY</th>
							<th class="th-op">KNITTING<br><span class="th-sub">Pending</span></th>
							<th class="th-op">MENDING<br><span class="th-sub">Pending</span></th>
							<th class="th-op">WASHING<br><span class="th-sub">Pending</span></th>
							<th class="th-op">CUTTING<br><span class="th-sub">Pending</span></th>
							<th class="th-op">LINKING<br><span class="th-sub">Pending</span></th>
							<th class="th-op">SEWING<br><span class="th-sub">Pending</span></th>
							<th class="th-op">EMBROID.<br><span class="th-sub">Pending</span></th>
							<th class="th-op">PRODUC.<br><span class="th-sub">Pending</span></th>
							<th class="th-op">PRESSING<br><span class="th-sub">Pending</span></th>
							<th class="th-op">FINAL CHK<br><span class="th-sub">Pending</span></th>
							<th class="th-op">PACKING<br><span class="th-sub">Pending</span></th>
							<th class="th-total">TOTAL<br><span class="th-sub">Pending</span></th>
							<th class="th-rej">REJ<br>QTY</th>
							<th class="th-packed">PACKED<br><span class="th-sub">Progress</span></th>
						</tr>
					</thead>
					<tbody id="ppd-tbody">
						<tr><td colspan="21" class="ppd-state"><span class="ppd-spinner"></span> Loading data&hellip;</td></tr>
					</tbody>
				</table>
			</div>
			<div class="ppd-footer">
				<span id="ppd-updated">Last updated: --</span>
				<span class="ppd-refresh-note">
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
	$(wrapper).on("change", "#ppd-filter-buyer, #ppd-filter-season, #ppd-filter-style, #ppd-filter-delivery", function () {
		_ppd_applyFilters();
	});
	$(wrapper).on("click", "#ppd-filter-clear", function () {
		_ppd_clearFilters();
	});

	_ppd_startClock();
	_ppd_load();
	_ppd_timer = setInterval(function () { _ppd_load(); }, 60000);
};

frappe.pages["packing-progress"].on_page_show = function (wrapper) {
	$("header.navbar").hide();
	$(".page-body").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section-wrapper").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section").css({ "padding": "0", "margin": "0", "max-width": "100%" });
};

frappe.pages["packing-progress"].on_page_hide = function () {
	$("header.navbar").show();
	$(".page-body").css({ "padding": "", "margin": "" });
	$(".layout-main-section-wrapper").css({ "padding": "", "margin": "" });
	$(".layout-main-section").css({ "padding": "", "margin": "", "max-width": "" });
	if (_ppd_timer) { clearInterval(_ppd_timer); _ppd_timer = null; }
};

var _ppd_timer   = null;
var _ppd_allRows = [];   // master copy of all rows from last server response

// Full cell list in pipeline order
const PPD_OPS = [
	{ label: "KNITTING",    key: "KNITTING"    },
	{ label: "MENDING",     key: "MENDING"     },
	{ label: "WASHING",     key: "WASHING"     },
	{ label: "CUTTING",     key: "CUTTING"     },
	{ label: "LINKING",     key: "LINKING"     },
	{ label: "SEWING",      key: "SEWING"      },
	{ label: "EMBROIDERY",  key: "EMBROIDERY"  },
	{ label: "PRODUCTION",  key: "PRODUCTION"  },
	{ label: "PRESSING",    key: "PRESSING"    },
	{ label: "FINAL CHECK", key: "FINAL CHECK" },
	{ label: "PACKING",     key: "PACKING"     },
];

function _ppd_startClock() { _ppd_tick(); setInterval(_ppd_tick, 1000); }
function _ppd_tick() {
	var d = new Date();
	var h = d.getHours(), m = String(d.getMinutes()).padStart(2, "0");
	var ampm = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
	var days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
	var months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
	$("#ppd-time").text(h + ":" + m + " " + ampm);
	$("#ppd-date").text(days[d.getDay()] + ", " + months[d.getMonth()] + " " + d.getDate());
}

function _ppd_load() {
	frappe.call({
		method: "analytix.analytix.page.packing_progress.packing_progress.get_packing_progress_data",
		freeze: false,
		callback: function (r) {
			if (r.exc) { _ppd_setState("&#9888; Failed to load data. Check server logs."); return; }
			_ppd_allRows = r.message || [];
			_ppd_populateFilters();
			_ppd_applyFilters();
			var n = new Date(), h = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#ppd-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

// ── Filter helpers ────────────────────────────────────────────────────────────

function _ppd_populateFilters() {
	var buyers  = _ppd_uniqueSorted(_ppd_allRows.map(function (r) { return r.buyer  || ""; }));
	var seasons = _ppd_uniqueSorted(_ppd_allRows.map(function (r) { return r.season || ""; }));
	var styles  = _ppd_uniqueSorted(_ppd_allRows.map(function (r) { return r.style  || ""; }));

	_ppd_repopulateSelect("#ppd-filter-buyer",  buyers,  "All Buyers");
	_ppd_repopulateSelect("#ppd-filter-season", seasons, "All Seasons");
	_ppd_repopulateSelect("#ppd-filter-style",  styles,  "All Styles");
}

function _ppd_repopulateSelect(selector, values, placeholder) {
	var $sel    = $(selector);
	var current = $sel.val();
	var html    = '<option value="">' + placeholder + '</option>';
	values.forEach(function (v) {
		if (!v) return;
		var sel = (v === current) ? ' selected' : '';
		html += '<option value="' + _ppd_e(v) + '"' + sel + '>' + _ppd_e(v) + '</option>';
	});
	$sel.html(html);
}

function _ppd_applyFilters() {
	var buyer    = $("#ppd-filter-buyer").val()    || "";
	var season   = $("#ppd-filter-season").val()   || "";
	var style    = $("#ppd-filter-style").val()    || "";
	var delivery = $("#ppd-filter-delivery").val() || "";   // yyyy-mm-dd from input

	var filtered = _ppd_allRows.filter(function (r) {
		if (buyer    && (r.buyer  || "") !== buyer)  return false;
		if (season   && (r.season || "") !== season) return false;
		if (style    && (r.style  || "") !== style)  return false;
		if (delivery && _ppd_isoToDisplay(delivery) !== (r.delivery_date || "")) return false;
		return true;
	});

	var total = _ppd_allRows.length;
	var shown = filtered.length;
	if (buyer || season || style || delivery) {
		$("#ppd-filter-count").text(shown + " of " + total + " rows").addClass("ppd-filter-count-active");
		$("#ppd-filter-clear").addClass("ppd-filter-clear-active");
	} else {
		$("#ppd-filter-count").text(total + " rows").removeClass("ppd-filter-count-active");
		$("#ppd-filter-clear").removeClass("ppd-filter-clear-active");
	}

	_ppd_render(filtered);
}

function _ppd_clearFilters() {
	$("#ppd-filter-buyer").val("");
	$("#ppd-filter-season").val("");
	$("#ppd-filter-style").val("");
	$("#ppd-filter-delivery").val("");
	_ppd_applyFilters();
}

// Convert input value "yyyy-mm-dd" → display format "dd-mm-yyyy" used by the server
function _ppd_isoToDisplay(iso) {
	if (!iso) return "";
	var p = iso.split("-");
	if (p.length !== 3) return iso;
	return p[2] + "-" + p[1] + "-" + p[0];
}

function _ppd_uniqueSorted(arr) {
	var seen = {}, out = [];
	arr.forEach(function (v) {
		if (v && !seen[v]) { seen[v] = true; out.push(v); }
	});
	return out.sort(function (a, b) { return a.localeCompare(b); });
}

// ── Cell helpers ──────────────────────────────────────────────────────────────

function _ppd_isNullCell(c) {
	if (c["is_outsourced"]) return false;
	var out = parseInt(c["out"] || 0);
	var inn = parseInt(c["in"]  || 0);
	if (c["no_in"]) return out === 0;
	return inn === 0 && out === 0;
}

function _ppd_getPrevOut(cellData, idx, plannedQty) {
	if (idx === 0) return plannedQty;
	for (var i = idx - 1; i >= 0; i--) {
		var prevCell = cellData[PPD_OPS[i].key] || {};
		if (prevCell["is_outsourced"]) continue;
		if (_ppd_isNullCell(prevCell)) continue;
		return parseInt(prevCell["out"] || 0);
	}
	return plannedQty;
}

// ── Render ────────────────────────────────────────────────────────────────────

function _ppd_render(rows) {
	if (!rows.length) {
		var hasFilter = $("#ppd-filter-buyer").val() || $("#ppd-filter-season").val() || $("#ppd-filter-style").val();
		_ppd_setState(hasFilter ? "No rows match the selected filters." : "No styles currently in packing.");
		return;
	}

	var html = "";
	rows.forEach(function (r) {
		var cellData   = r.cells || {};
		var orderQty   = parseInt(r.order_qty)  || 0;
		var plannedQty = parseInt(r.planned_qty) || 0;

		var totalPending = 0;
		var opPendings = PPD_OPS.map(function (op, idx) {
			var c = cellData[op.key] || {};

			if (c["is_outsourced"]) return "OS";
			if (_ppd_isNullCell(c)) return null;

			var prevOut = _ppd_getPrevOut(cellData, idx, plannedQty);
			var out     = parseInt(c["out"] || 0);
			var pending = Math.max(0, prevOut - out);
			totalPending += pending;
			return pending;
		});

		var rejQty     = parseInt(r.rej_qty || 0);
		var packingOut = parseInt(((cellData["PACKING"] || {})["out"]) || 0);
		var packedPct  = orderQty ? Math.round((packingOut / orderQty) * 100) : 0;
		var pkClass    = packedPct >= 100 ? "pk-done" : packedPct >= 50 ? "pk-mid" : "pk-low";

		var circ    = 113.1;
		var ringPct = Math.min(packedPct, 100);
		var offset  = (circ - (ringPct / 100) * circ).toFixed(1);

		html += '<tr class="ppd-row">';
		html += '<td class="td-buyer">'    + _ppd_e(r.buyer) + "</td>";
		html += '<td class="td-season"><span class="szn ' + _ppd_seasonClass(r.season) + '">' + _ppd_e(r.season) + "</span></td>";
		html += '<td class="td-style">'    + _ppd_e(r.style) + "</td>";
		html += '<td class="td-colour"><span class="colour-badge">' + _ppd_e(r.colour) + "</span></td>";
		html += '<td class="td-delivery">' + _ppd_e(r.delivery_date) + "</td>";
		html += '<td class="td-qty">'      + _ppd_n(r.order_qty)   + "</td>";
		html += '<td class="td-qty">'      + _ppd_n(r.planned_qty) + "</td>";

		opPendings.forEach(function (pending) {
			if (pending === null) {
				html += '<td class="td-op"><span class="op-na">&#8212;</span></td>';
			} else if (pending === "OS") {
				html += '<td class="td-op"><span class="op-outsourced" title="Outsourced process">OS</span></td>';
			} else if (pending === 0) {
				html += '<td class="td-op"><span class="op-pending op-zero">&#8212;</span></td>';
			} else {
				html += '<td class="td-op"><span class="op-pending">' + _ppd_n(pending) + "</span></td>";
			}
		});

		html += '<td class="td-total"><span class="total-val">'
			+ (totalPending === 0 ? "&#8212;" : _ppd_n(totalPending))
			+ "</span></td>";

		var rejCls = rejQty === 0 ? "rej-val rej-zero" : "rej-val";
		html += '<td class="td-rej"><span class="' + rejCls + '">'
			+ (rejQty === 0 ? "&#8212;" : _ppd_n(rejQty))
			+ "</span></td>";

		html += '<td class="td-packed">';
		html += '<div class="packed-wrap">';
		html += '<svg class="packed-svg" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">';
		html += '<circle class="packed-bg"   cx="22" cy="22" r="18"/>';
		html += '<circle class="packed-ring ' + pkClass + '" cx="22" cy="22" r="18"'
			+   ' stroke-dasharray="' + circ + '"'
			+   ' stroke-dashoffset="' + offset + '"/>';
		html += '</svg>';
		html += '<div class="packed-label">';
		html += '<span class="packed-pct ' + pkClass + '">' + packedPct + "%</span>";
		html += '<span class="packed-counts">' + _ppd_n(packingOut) + "</span>";
		html += '</div></div>';
		var fsd = r.first_scan_date || "";
		html += '<div class="packed-scan-date">' + _ppd_e(fsd) + "</div>";
		html += '</td>';

		html += "</tr>";
	});

	$("#ppd-tbody").html(html);
}

function _ppd_setState(msg) {
	$("#ppd-tbody").html('<tr><td colspan="21" class="ppd-state">' + msg + "</td></tr>");
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _ppd_e(v) {
	if (v === null || v === undefined) return "";
	return String(v)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;");
}

function _ppd_n(v) {
	var n = parseInt(v);
	if (isNaN(n)) return "&#8212;";
	return n.toLocaleString();
}

function _ppd_seasonClass(season) {
	if (!season) return "szn-default";
	var s = season.toLowerCase();
	if (s.indexOf("spring") !== -1) return "szn-spring";
	if (s.indexOf("summer") !== -1) return "szn-summer";
	if (s.indexOf("winter") !== -1) return "szn-winter";
	if (s.indexOf("fall") !== -1 || s.indexOf("autumn") !== -1) return "szn-fall";
	return "szn-default";
}