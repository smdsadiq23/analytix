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

	// ── CHANGE 1: reload when the user picks a different date ──────────────
	$("#pd-date-input").on("change", function() { _load(); });

	// Refresh button
	$("#pd-refresh-btn").on("click", function() { _load(); });

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
};

var _timer = null;

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

// ── CHANGE 2: pass selected date + today to the backend ───────────────────
function _load() {
	var selectedDate = $("#pd-date-input").val() || frappe.datetime.get_today();
	var today = frappe.datetime.get_today();

	$("#pd-refresh-btn").addClass("loading");
	frappe.call({
		method: "analytix.analytix.page.shopfloor_performance.shopfloor_performance.get_dashboard_data",
		args: {
			date:  selectedDate,   // daily input/output filtered to this date only
			today: today,          // MTD/YTD always anchored to real today
		},
		freeze: false,
		callback: function (r) {
			$("#pd-refresh-btn").removeClass("loading");
			if (r.exc) {
				_setError("Failed to load data. Check server logs.");
				return;
			}
			// ── CHANGE 3: destructure the new response shape ──────────────
			var msg = r.message || {};
			_render(
				msg.daily      || [],
				msg.mtd_output || {},
				msg.ytd_output || {}
			);
			var n = new Date(), h = n.getHours(), m = String(n.getMinutes()).padStart(2, "0");
			var ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
			$("#pd-updated").text("Last updated: " + h + ":" + m + " " + ap);
		},
	});
}

// ── CHANGE 4: _render now accepts mtdOutput and ytdOutput ─────────────────
function _render(data, mtdOutput, ytdOutput) {
	var $grid = $("#pd-grid");

	if (!data || (Array.isArray(data) && !data.length)) {
		$grid.html('<div class="pd-empty">No production data available for selected date.</div>');
		return;
	}

	var totals = _aggregateTotals(data);
	var html = "";

	SECTIONS.forEach(function(section) {
		var key = SECTION_KEY_MAP[section];
		var t = totals[key] || {};

		// ── CHANGE 5: pass per-section MTD/YTD into each card builder ────
		var mtd = (mtdOutput[key] || 0);
		var ytd = (ytdOutput[key] || 0);

		if (section === "KNITTING") {
			html += _buildKnittingCard(section, t, mtd, ytd);
		} else {
			html += _buildSectionCard(section, key, t, mtd, ytd);
		}
	});

	$grid.html(html);
}

function _aggregateTotals(rows) {
	// Unchanged — aggregates only the daily rows passed in
	var totals = {};
	SECTIONS.forEach(function(section) {
		var key = SECTION_KEY_MAP[section];
		totals[key] = { input: 0, output: 0, wip: 0, rejection: 0 };
	});

	rows.forEach(function(r) {
		var cells = r.cells || {};
		SECTIONS.forEach(function(section) {
			var key = SECTION_KEY_MAP[section];
			var c = cells[key] || {};
			totals[key].input  += (c["in"]  || 0);
			totals[key].output += (c["out"] || 0);
		});
	});

	// Knitting shifts
	totals["KNITTING"].shift1  = 0;
	totals["KNITTING"].shift2  = 0;
	totals["KNITTING"].wastage = 0;

	rows.forEach(function(r) {
		totals["KNITTING"].shift1  += (r.knitting_shift1  || 0);
		totals["KNITTING"].shift2  += (r.knitting_shift2  || 0);
		totals["KNITTING"].wastage += (r.knitting_wastage || 0);
	});

	// WIP = prev section output − current section output (daily only)
	SECTIONS.forEach(function (section, i) {
		var key = SECTION_KEY_MAP[section];
		if (i === 0) { totals[key].wip = 0; return; }

		var prev_key = SECTION_KEY_MAP[SECTIONS[i - 1]];
		var prev_out = (prev_key === "KNITTING")
			? (totals["KNITTING"].shift1 || 0) + (totals["KNITTING"].shift2 || 0)
			: totals[prev_key].output || 0;

		var wip = prev_out - (totals[key].output || 0);
		totals[key].wip = wip < 0 ? 0 : wip;
	});

	return totals;
}

// ── CHANGE 6: card builders now receive mtd/ytd as plain args ─────────────
function _buildKnittingCard(section, t, mtd, ytd) {
	var shift1    = t.shift1    || 0;
	var shift2    = t.shift2    || 0;
	var wastage   = t.wastage   || 0;
	var rejection = t.rejection || 0;

	return `
		<div class="pd-card">
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

function _buildSectionCard(section, key, t, mtd, ytd) {
	var input     = t.input     || 0;
	var output    = t.output    || 0;
	var wip       = t.wip       || 0;
	var rejection = t.rejection || 0;

	return `
		<div class="pd-card">
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