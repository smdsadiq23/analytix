frappe.pages['shopfloor-performance'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Shopfloor Performance Dashboard",
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
		<div class="pd-root">
			<div class="pd-header">
				<div class="pd-header-left">
					<div class="pd-logo">
						<svg width="36" height="36" viewBox="0 0 36 36" fill="none">
							<rect width="36" height="36" rx="8" fill="#1a2744"/>
							<path d="M7 21 L12 14 L17 19 L22 12 L29 21" stroke="#3b82f6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
							<circle cx="29" cy="21" r="2.2" fill="#3b82f6"/>
						</svg>
					</div>
					<div class="pd-header-text">
						<div class="pd-title">Shopfloor Performance Dashboard</div>
						<div class="pd-subtitle">Real-time production tracking across all sections</div>
					</div>
				</div>
				<div class="pd-header-right">
					<div class="pd-date-picker-wrap">
						<label class="pd-date-label">
							<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
							</svg>
							Select Date
						</label>
						<input type="date" id="pd-date-input" class="pd-date-input"/>
					</div>
					<button class="pd-refresh-btn" id="pd-refresh-btn">
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
						</svg>
						Refresh
					</button>
				</div>
			</div>

			<div class="pd-grid" id="pd-grid">
				<div class="pd-loading">
					<div class="pd-spinner"></div>
					<span>Loading production data…</span>
				</div>
			</div>

			<div class="pd-footer">
				<span id="pd-updated">Last updated: --</span>
				<span class="pd-auto-note">
					<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
						<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
					</svg>
					Auto-refresh every 60s
				</span>
			</div>
		</div>
	`);

	// Set default date to today
	var today = frappe.datetime.get_today();
	$("#pd-date-input").val(today);

	// Reload when date changes
	$("#pd-date-input").on("change", function() {
		_load();
	});

	// Refresh button
	$("#pd-refresh-btn").on("click", function() {
		_load();
	});

	_load();
	_timer = setInterval(function() { _load(); }, 60000);
};

frappe.pages["shopfloor-performance"].on_page_show = function (wrapper) {
	$("header.navbar").hide();
	$(".page-body").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section-wrapper").css({ "padding": "0", "margin": "0" });
	$(".layout-main-section").css({ "padding": "0", "margin": "0", "max-width": "100%" });
};

frappe.pages["shopfloor-performance"].on_page_hide = function () {
	$("header.navbar").show();
	$(".page-body").css({ "padding": "", "margin": "" });
	$(".layout-main-section-wrapper").css({ "padding": "", "margin": "" });
	$(".layout-main-section").css({ "padding": "", "margin": "", "max-width": "" });
	if (_timer) { clearInterval(_timer); _timer = null; }
	_closeModal();
};

var _timer    = null;
var _lastData = [];   // raw rows — kept for drill-down

// All sections in pipeline order
const SECTIONS = [
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

// Map from display section names to API cell keys
const SECTION_KEY_MAP = {
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

function _closeModal() {
	$("#pd-modal-overlay").remove();
	$("#pd-grid .pd-card").removeClass("pd-card-active");
	$(document).off("keydown.pddetail");
}

function _load() {
	var selectedDate = $("#pd-date-input").val() || frappe.datetime.get_today();

	// Close modal on reload
	_closeModal();

	$("#pd-refresh-btn").addClass("loading");
	frappe.call({
		method: "analytix.analytix.page.shopfloor_performance.shopfloor_performance.get_dashboard_data",
		args: { date: selectedDate },
		freeze: false,
		callback: function (r) {
			$("#pd-refresh-btn").removeClass("loading");
			if (r.exc) {
				_setError("Failed to load data. Check server logs.");
				return;
			}
			_render(r.message || {});
			var n = new Date(), h = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#pd-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

function _render(data) {
	var $grid = $("#pd-grid");

	if (!data || (Array.isArray(data) && !data.length)) {
		$grid.html('<div class="pd-empty">No production data available for selected date.</div>');
		return;
	}

	_lastData = data;

	var totals = _aggregateTotals(data);
	var html = "";

	SECTIONS.forEach(function(section) {
		var key = SECTION_KEY_MAP[section];
		var t = totals[key] || {};

		if (section === "KNITTING") {
			html += _buildKnittingCard(section, t, data);
		} else {
			html += _buildSectionCard(section, key, t);
		}
	});

	$grid.html(html);

	// Wire card clicks → modal popup drill-down
	$grid.find(".pd-card").on("click", function() {
		var sectionKey   = $(this).data("section-key");
		var sectionLabel = $(this).data("section-label");
		_showDrilldown(sectionLabel, sectionKey);
	});
}

function _aggregateTotals(rows) {
	var totals = {};
	SECTIONS.forEach(function(section) {
		var key = SECTION_KEY_MAP[section];
		totals[key] = { input: 0, output: 0, cum_out: 0, wip: 0, rejection: 0, mtd: 0, ytd: 0 };
	});

	rows.forEach(function(r) {
		var cells = r.cells || {};
		SECTIONS.forEach(function(section) {
			var key = SECTION_KEY_MAP[section];
			var c = cells[key] || {};
			totals[key].input   += (c["in"]      || 0);
			totals[key].output  += (c["out"]     || 0);
			totals[key].cum_out += (c["cum_out"] || 0);
			totals[key].mtd     += (c["mtd"]     || 0);
			totals[key].ytd     += (c["ytd"]     || 0);
		});
	});

	// Knitting: aggregate shifts (daily, MTD, YTD)
	totals["KNITTING"].shift1     = 0;
	totals["KNITTING"].shift2     = 0;
	totals["KNITTING"].shift1_mtd = 0;
	totals["KNITTING"].shift2_mtd = 0;
	totals["KNITTING"].shift1_ytd = 0;
	totals["KNITTING"].shift2_ytd = 0;
	totals["KNITTING"].shift1_cum = 0;
	totals["KNITTING"].shift2_cum = 0;
	totals["KNITTING"].wastage    = 0;

	rows.forEach(function(r) {
		totals["KNITTING"].shift1     += (r.knitting_shift1     || 0);
		totals["KNITTING"].shift2     += (r.knitting_shift2     || 0);
		totals["KNITTING"].shift1_mtd += (r.knitting_shift1_mtd || 0);
		totals["KNITTING"].shift2_mtd += (r.knitting_shift2_mtd || 0);
		totals["KNITTING"].shift1_ytd += (r.knitting_shift1_ytd || 0);
		totals["KNITTING"].shift2_ytd += (r.knitting_shift2_ytd || 0);
		totals["KNITTING"].shift1_cum += (r.knitting_shift1_cum || 0);
		totals["KNITTING"].shift2_cum += (r.knitting_shift2_cum || 0);
		totals["KNITTING"].wastage    += (r.knitting_wastage    || 0);
	});

	totals["KNITTING"].output  = totals["KNITTING"].shift1 + totals["KNITTING"].shift2;
	totals["KNITTING"].cum_out = totals["KNITTING"].shift1_cum + totals["KNITTING"].shift2_cum;
	totals["KNITTING"].mtd     = totals["KNITTING"].shift1_mtd + totals["KNITTING"].shift2_mtd;
	totals["KNITTING"].ytd     = totals["KNITTING"].shift1_ytd + totals["KNITTING"].shift2_ytd;

	// WIP = prev cumulative OUT − current cumulative OUT
	SECTIONS.forEach(function (section, i) {
		var key = SECTION_KEY_MAP[section];
		if (i === 0) { totals[key].wip = 0; return; }
		var prev_key = SECTION_KEY_MAP[SECTIONS[i - 1]];
		var wip = (totals[prev_key].cum_out || 0) - (totals[key].cum_out || 0);
		totals[key].wip = wip < 0 ? 0 : wip;
	});

	return totals;
}

function _buildKnittingCard(section, t, rows) {
	var shift1    = t.shift1    || 0;
	var shift2    = t.shift2    || 0;
	var wastage   = t.wastage   || 0;
	var rejection = t.rejection || 0;
	var mtd       = t.mtd       || 0;
	var ytd       = t.ytd       || 0;

	return `
		<div class="pd-card pd-card-clickable" data-section-key="KNITTING" data-section-label="KNITTING">
			<div class="pd-card-header">
				<span class="pd-card-title">${_e(section)}</span>
				<span class="pd-card-badge">2 Shifts</span>
			</div>
			<div class="pd-card-body">
				<div class="pd-row">
					<div class="pd-row-label">
						<span class="pd-icon pd-icon-output"></span>
						Shift 1 Output
					</div>
					<div class="pd-row-val pd-val-green">${_n(shift1)}</div>
				</div>
				<div class="pd-row">
					<div class="pd-row-label">
						<span class="pd-icon pd-icon-output"></span>
						Shift 2 Output
					</div>
					<div class="pd-row-val pd-val-green">${_n(shift2)}</div>
				</div>
				<div class="pd-row">
					<div class="pd-row-label">
						<span class="pd-icon pd-icon-rejection"></span>
						Rejection Qty
					</div>
					<div class="pd-row-val pd-val-red">${_n(rejection)}</div>
				</div>
				<div class="pd-row pd-row-wastage">
					<div class="pd-row-label">
						<span class="pd-icon pd-icon-wastage"></span>
						Wastage (Kg)
					</div>
					<div class="pd-row-val pd-val-orange">${_n(wastage)}</div>
				</div>
			</div>
			<div class="pd-card-footer">
				<div class="pd-footer-row">
					<span class="pd-footer-label">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
						MTD Output
					</span>
					<span class="pd-footer-val">${_n(mtd)}</span>
				</div>
				<div class="pd-footer-row">
					<span class="pd-footer-label">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
						YTD Output
					</span>
					<span class="pd-footer-val">${_n(ytd)}</span>
				</div>
			</div>
		</div>
	`;
}

function _buildSectionCard(section, key, t) {
	var input     = t.input     || 0;
	var output    = t.output    || 0;
	var wip       = t.wip       || 0;
	var rejection = t.rejection || 0;
	var mtd       = t.mtd       || 0;
	var ytd       = t.ytd       || 0;

	return `
		<div class="pd-card pd-card-clickable" data-section-key="${_e(key)}" data-section-label="${_e(section)}">
			<div class="pd-card-header">
				<span class="pd-card-title">${_e(section)}</span>
			</div>
			<div class="pd-card-body">
				<div class="pd-row">
					<div class="pd-row-label">
						<span class="pd-icon pd-icon-input"></span>
						Input
					</div>
					<div class="pd-row-val pd-val-blue">${_n(input)}</div>
				</div>
				<div class="pd-row">
					<div class="pd-row-label">
						<span class="pd-icon pd-icon-output"></span>
						Output
					</div>
					<div class="pd-row-val pd-val-green">${_n(output)}</div>
				</div>
				<div class="pd-row">
					<div class="pd-row-label">
						<span class="pd-icon pd-icon-wip"></span>
						WIP
					</div>
					<div class="pd-row-val pd-val-orange">${_n(wip)}</div>
				</div>
				<div class="pd-row">
					<div class="pd-row-label">
						<span class="pd-icon pd-icon-rejection"></span>
						Rejection Qty
					</div>
					<div class="pd-row-val pd-val-red">${_n(rejection)}</div>
				</div>
			</div>
			<div class="pd-card-footer">
				<div class="pd-footer-row">
					<span class="pd-footer-label">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
						MTD Output
					</span>
					<span class="pd-footer-val">${_n(mtd)}</span>
				</div>
				<div class="pd-footer-row">
					<span class="pd-footer-label">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
						YTD Output
					</span>
					<span class="pd-footer-val">${_n(ytd)}</span>
				</div>
			</div>
		</div>
	`;
}

// ── Modal popup drill-down ────────────────────────────────────────────────────

function _showDrilldown(sectionLabel, sectionKey) {
	// If same card clicked while modal is open, close it
	var $existing = $("#pd-modal-overlay");
	if ($existing.length && $existing.data("active-key") === sectionKey) {
		_closeModal();
		return;
	}

	// KNITTING has no per-style WIP data
	if (sectionKey === "KNITTING") {
		_closeModal();
		return;
	}

	if (!_lastData || !_lastData.length) return;

	// Remove any existing modal
	$existing.remove();

	// Highlight active card
	$("#pd-grid .pd-card").removeClass("pd-card-active");
	$("#pd-grid .pd-card[data-section-key='" + sectionKey + "']").addClass("pd-card-active");

	// Build per-style rows
	var styleRows = _lastData.map(function(r) {
		var cells     = r.cells || {};
		var cell      = cells[sectionKey] || {};
		var pendingIn = cell["pending_in"] != null ? cell["pending_in"] : 0;
		var actualWip = cell["actual_wip"] != null ? cell["actual_wip"] : 0;
		return {
			style:     r.style  || "",
			colour:    r.colour || "",
			buyer:     r.buyer  || "",
			pendingIn: pendingIn,
			actualWip: actualWip,
		};
	}).filter(function(r) {
		return r.pendingIn > 0 || r.actualWip > 0;
	});

	// Sort: highest actualWip first
	styleRows.sort(function(a, b) { return (b.actualWip || 0) - (a.actualWip || 0); });

	var totalPending = styleRows.reduce(function(s, r) { return s + (r.pendingIn || 0); }, 0);
	var totalWip     = styleRows.reduce(function(s, r) { return s + (r.actualWip || 0); }, 0);

	// Build table
	var tableHtml;
	if (!styleRows.length) {
		tableHtml = '<p class="pd-detail-empty">No pending or WIP data for this section.</p>';
	} else {
		var tbody = styleRows.map(function(r) {
			var piCls  = r.pendingIn > 0 ? "pd-popup-val-amber"  : "pd-popup-val-zero";
			var wipCls = r.actualWip > 0 ? "pd-popup-val-orange" : "pd-popup-val-zero";
			return `<tr>
				<td class="pd-popup-td pd-popup-style">${_e(r.style)}</td>
				<td class="pd-popup-td pd-popup-colour">${_e(r.colour)}</td>
				<td class="pd-popup-td pd-popup-buyer">${_e(r.buyer)}</td>
				<td class="pd-popup-td pd-popup-num ${piCls}">${_n(r.pendingIn)}</td>
				<td class="pd-popup-td pd-popup-num ${wipCls}">${_n(r.actualWip)}</td>
			</tr>`;
		}).join("");

		tableHtml = `
			<div class="pd-popup-table-wrap">
				<table class="pd-popup-table">
					<thead>
						<tr>
							<th class="pd-popup-th">Style</th>
							<th class="pd-popup-th">Colour</th>
							<th class="pd-popup-th">Buyer</th>
							<th class="pd-popup-th pd-popup-num">
								<span class="pd-popup-th-badge pd-popup-th-amber">Pending In</span>
								<div class="pd-popup-th-sub">Prev OUT − Curr IN</div>
							</th>
							<th class="pd-popup-th pd-popup-num">
								<span class="pd-popup-th-badge pd-popup-th-orange">Actual WIP</span>
								<div class="pd-popup-th-sub">Curr IN − Curr OUT</div>
							</th>
						</tr>
					</thead>
					<tbody>${tbody}</tbody>
				</table>
			</div>`;
	}

	var $overlay = $(`
		<div id="pd-modal-overlay" class="pd-modal-overlay">
			<div class="pd-modal-box">
				<div class="pd-detail-header">
					<div class="pd-detail-title-wrap">
						<span class="pd-popup-section-badge">${_e(sectionLabel)}</span>
						<span class="pd-popup-title">Style-wise Breakdown</span>
					</div>
					<div class="pd-popup-summary">
						<div class="pd-popup-summary-item pd-popup-summary-amber">
							<div class="pd-popup-summary-val">${_n(totalPending)}</div>
							<div class="pd-popup-summary-lbl">Total Pending In</div>
						</div>
						<div class="pd-popup-summary-item pd-popup-summary-orange">
							<div class="pd-popup-summary-val">${_n(totalWip)}</div>
							<div class="pd-popup-summary-lbl">Total Actual WIP</div>
						</div>
					</div>
					<button class="pd-popup-close" id="pd-detail-close" title="Close">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
							<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
						</svg>
					</button>
				</div>
				<div class="pd-detail-body">
					${tableHtml}
				</div>
			</div>
		</div>
	`);

	$overlay.data("active-key", sectionKey);
	$("body").append($overlay);

	// Close on backdrop click
	$overlay.on("click", function(e) {
		if ($(e.target).is("#pd-modal-overlay")) { _closeModal(); }
	});

	// Close button
	$("#pd-detail-close").on("click", function() { _closeModal(); });

	// ESC key
	$(document).off("keydown.pddetail").on("keydown.pddetail", function(e) {
		if (e.key === "Escape") { _closeModal(); }
	});
}

function _setError(msg) {
	$("#pd-grid").html('<div class="pd-empty pd-error">&#9888; ' + msg + '</div>');
}

function _e(s) {
	return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function _n(v) {
	if (v === null || v === undefined || v === "") return "0";
	return Number(v).toLocaleString("en-IN");
}
