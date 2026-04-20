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

var _ppd_timer = null;

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
		// Dedicated endpoint — both filters (packing started, not fully packed)
		// and outsourced flags are handled server-side in packing_progress.py.
		method: "analytix.analytix.page.packing_progress.packing_progress.get_packing_progress_data",
		freeze: false,
		callback: function (r) {
			if (r.exc) { _ppd_setState("&#9888; Failed to load data. Check server logs."); return; }
			_ppd_render(r.message || []);
			var n = new Date(), h = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#ppd-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

function _ppd_render(rows) {
	if (!rows.length) { _ppd_setState("No styles currently in packing."); return; }

	var html = "";
	rows.forEach(function (r) {
		var cellData   = r.cells || {};
		var orderQty   = parseInt(r.order_qty)  || 0;
		var plannedQty = parseInt(r.planned_qty) || 0;

		// ── Pending qty per cell ──────────────────────────────────────────
		//
		// Three states per cell:
		//
		//   null    — not applicable for this style (in=0 AND out=0 AND NOT outsourced)
		//             → dim "—", NOT counted in totalPending
		//
		//   "OS"    — outsourced cell (is_outsourced = true)
		//             → muted "OS" badge, NOT counted in totalPending
		//             Checked BEFORE the in=0/out=0 guard because an outsourced
		//             cell may have no scans and would otherwise be misread as
		//             non-applicable.
		//
		//   number  — in-house applicable cell
		//             → pending = prev_cell_out - this_cell_out
		//                (first cell uses plannedQty as the starting stock)
		//             → counted in totalPending
		//
		var totalPending = 0;
		var opPendings = PPD_OPS.map(function (op, idx) {
			var c   = cellData[op.key] || {};
			var inn = parseInt(c["in"]  || 0);
			var out = parseInt(c["out"] || 0);

			if (c["is_outsourced"]) {
				return "OS";
			}

			if (inn === 0 && out === 0) {
				return null;
			}

			// pending = previous cell's OUT minus this cell's OUT
			// For the first cell (KNITTING) there is no predecessor,
			// so plannedQty is used as the upstream quantity.
			var prevOut;
			if (idx === 0) {
				prevOut = plannedQty;
			} else {
				var prevKey  = PPD_OPS[idx - 1].key;
				var prevCell = cellData[prevKey] || {};
				prevOut = parseInt(prevCell["out"] || 0);
			}

			var pending = Math.max(0, prevOut - out);
			totalPending += pending;
			return pending;
		});

		// ── REJ QTY ──────────────────────────────────────────────────────
		var rejQty = parseInt(r.rej_qty || 0);

		// ── Packed progress: PACKING OUT / order_qty × 100 ───────────────
		var packingOut = parseInt(((cellData["PACKING"] || {})["out"]) || 0);
		var packedPct  = orderQty ? Math.round((packingOut / orderQty) * 100) : 0;
		packedPct = Math.min(packedPct, 100);
		var pkClass = packedPct >= 100 ? "pk-done" : packedPct >= 50 ? "pk-mid" : "pk-low";

		// SVG circle r=18, circumference = 2π×18 ≈ 113.1
		var circ   = 113.1;
		var offset = (circ - (packedPct / 100) * circ).toFixed(1);

		html += '<tr class="ppd-row">';
		html += '<td class="td-buyer">'    + _ppd_e(r.buyer) + "</td>";
		html += '<td class="td-season"><span class="szn ' + _ppd_seasonClass(r.season) + '">' + _ppd_e(r.season) + "</span></td>";
		html += '<td class="td-style">'    + _ppd_e(r.style) + "</td>";
		html += '<td class="td-colour"><span class="colour-badge">' + _ppd_e(r.colour) + "</span></td>";
		html += '<td class="td-delivery">' + _ppd_e(r.delivery_date) + "</td>";
		html += '<td class="td-qty">'      + _ppd_n(r.order_qty)   + "</td>";
		html += '<td class="td-qty">'      + _ppd_n(r.planned_qty) + "</td>";

		// ── 11 pending columns ────────────────────────────────────────────
		opPendings.forEach(function (pending) {
			if (pending === null) {
				// Not applicable for this style — dim dash
				html += '<td class="td-op"><span class="op-na">&#8212;</span></td>';
			} else if (pending === "OS") {
				// Outsourced process — muted badge, excluded from total
				html += '<td class="td-op"><span class="op-outsourced" title="Outsourced process">OS</span></td>';
			} else if (pending === 0) {
				// In-house, fully complete — green dash
				html += '<td class="td-op"><span class="op-pending op-zero">&#8212;</span></td>';
			} else {
				html += '<td class="td-op"><span class="op-pending">' + _ppd_n(pending) + "</span></td>";
			}
		});

		// ── TOTAL pending (in-house cells only) ───────────────────────────
		html += '<td class="td-total"><span class="total-val">'
			+ (totalPending === 0 ? "&#8212;" : _ppd_n(totalPending))
			+ "</span></td>";

		// ── REJ QTY ──────────────────────────────────────────────────────
		var rejCls = rejQty === 0 ? "rej-val rej-zero" : "rej-val";
		html += '<td class="td-rej"><span class="' + rejCls + '">'
			+ (rejQty === 0 ? "&#8212;" : _ppd_n(rejQty))
			+ "</span></td>";

		// ── Packed progress circle ────────────────────────────────────────
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
		html += '</div></div></td>';

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