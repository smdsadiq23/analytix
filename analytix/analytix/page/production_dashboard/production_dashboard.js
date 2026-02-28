frappe.pages["production-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Production Dashboard",
		single_column: true,
	});

	$(wrapper).find(".page-head").hide();

	$(wrapper).find(".page-content").append(`
		<div class="tvd-root">

			<div class="tvd-topbar">
				<div class="tvd-brand">
					<svg class="tvd-brand-icon" width="38" height="38" viewBox="0 0 38 38" fill="none">
						<rect width="38" height="38" rx="9" fill="#00d4aa" fill-opacity="0.12"/>
						<path d="M8 22 L13 15 L18 20 L23 13 L30 22" stroke="#00d4aa" stroke-width="2.5"
							stroke-linecap="round" stroke-linejoin="round" fill="none"/>
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
							<th class="th-style">STYLE</th>
							<th class="th-buyer">BUYER</th>
							<th class="th-colour">COLOUR</th>
							<th class="th-season">SEASON</th>
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
							<th class="th-cell">PACKING<br><span class="th-inout">IN / OUT</span></th>
							<th class="th-completion">COMPLETION</th>
						</tr>
					</thead>
					<tbody id="tvd-tbody">
						<tr>
							<td colspan="18" class="tvd-state">
								<span class="tvd-spinner"></span> Loading data&hellip;
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div class="tvd-footer">
				<span id="tvd-updated">Last updated: --</span>
				<span class="tvd-refresh-note">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
						stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
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
	_timer = setInterval(_load, 60000);
};

frappe.pages["production-dashboard"].on_page_hide = function () {
	if (_timer) { clearInterval(_timer); _timer = null; }
};

var _timer = null;

const CELLS = [
    "KNITTING",
    "MENDING",
    "WASHING",
    "CUTTING",
    "LINKING",
    "SEWING",
    "EMBROIDERY",
    "PRODUCTION",
    "PRESSING",
    "PACKING"
];

// ── Clock ─────────────────────────────────────────────────────────────────────
function _startClock() {
	_tick();
	setInterval(_tick, 1000);
}
function _tick() {
	var d    = new Date();
	var h    = d.getHours(), m = String(d.getMinutes()).padStart(2, "0");
	var ampm = h >= 12 ? "PM" : "AM";
	h = h % 12 || 12;
	var days   = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
	var months = ["January","February","March","April","May","June",
	              "July","August","September","October","November","December"];
	$("#tvd-time").text(h + ":" + m + " " + ampm);
	$("#tvd-date").text(days[d.getDay()] + ", " + months[d.getMonth()] + " " + d.getDate());
}

// ── Data ──────────────────────────────────────────────────────────────────────
function _load() {
	frappe.call({
		method: "analytix.analytix.page.production_dashboard.production_dashboard.get_dashboard_data",
		freeze: false,
		callback: function (r) {
			if (r.exc) {
				_setState("&#9888; Failed to load data. Check server logs.");
				return;
			}
			_render(r.message || []);
			var n  = new Date();
			var h  = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#tvd-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

// ── Render ────────────────────────────────────────────────────────────────────
function _render(rows) {
	if (!rows.length) {
		_setState("No production data found.");
		return;
	}

	var html = "";
	rows.forEach(function (r) {

		html += '<tr class="tvd-row">';

		// Style
		html += '<td class="td-style">' + _e(r.style) + "</td>";

		// Buyer
		html += '<td class="td-buyer">' + _e(r.buyer) + "</td>";

		// Colour — dark pill badge
		html += '<td class="td-colour"><span class="colour-badge">' + _e(r.colour) + "</span></td>";

		// Season — coloured pill badge
		html += '<td class="td-season"><span class="szn ' + _seasonClass(r.season) + '">' + _e(r.season) + "</span></td>";

		// Delivery
		html += '<td class="td-delivery">' + _e(r.delivery_date) + "</td>";

		// Order Qty
		html += '<td class="td-qty">' + _n(r.order_qty) + "</td>";

		// Planned Qty
		html += '<td class="td-qty">' + _n(r.planned_qty) + "</td>";

		// Per-cell columns
		var cellData = r.cells || {};
		CELLS.forEach(function (cell) {
			var c   = cellData[cell] || {};
			var pct = c["pct"] || 0;

			// % colour: ≥90 green, ≥75 teal, ≥50 yellow, else red
			var pClass = pct >= 90 ? "pct-green"
			           : pct >= 75 ? "pct-teal"
			           : pct >= 50 ? "pct-yellow"
			           : "pct-red";

			html += '<td class="td-cell">';
			html += '<div class="cell-in">'  + _n(c["in"])  + "</div>";
			html += '<div class="cell-line"></div>';
			html += '<div class="cell-out">' + _n(c["out"]) + "</div>";
			html += '<div class="cell-pct ' + pClass + '">' + pct + "%</div>";
			html += "</td>";
		});

		// Completion circle
		var cp     = parseFloat(r.completion_pct) || 0;
		var cpStr  = cp.toFixed(cp % 1 === 0 ? 0 : 1) + "%";
		var circ   = 113.1;
		var offset = (circ - (cp / 100) * circ).toFixed(1);
		var cc     = cp >= 100 ? "cc-done" : cp >= 75 ? "cc-good" : cp >= 40 ? "cc-mid" : "cc-low";

		html += '<td class="td-completion">';
		html += '<div class="comp-wrap">';
		html += '<svg class="comp-svg" viewBox="0 0 44 44">';
		html += '<circle class="comp-bg"   cx="22" cy="22" r="18"/>';
		html += '<circle class="comp-ring ' + cc + '" cx="22" cy="22" r="18"';
		html +=   ' stroke-dasharray="' + circ + '" stroke-dashoffset="' + offset + '"/>';
		html += "</svg>";
		html += '<span class="comp-label ' + cc + '">' + cpStr + "</span>";
		html += "</div></td>";

		html += "</tr>";
	});

	$("#tvd-tbody").html(html);
}

function _setState(msg) {
	$("#tvd-tbody").html('<tr><td colspan="18" class="tvd-state">' + msg + "</td></tr>");
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function _e(s) {
	return String(s || "")
		.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function _n(v) {
	if (v === null || v === undefined || v === "") return "0";
	return Number(v).toLocaleString("en-IN");
}
function _seasonClass(s) {
	var l = (s || "").toLowerCase();
	if (l.includes("spring")) return "szn-spring";
	if (l.includes("summer")) return "szn-summer";
	if (l.includes("winter")) return "szn-winter";
	if (l.includes("fall") || l.includes("autumn")) return "szn-fall";
	return "szn-default";
}