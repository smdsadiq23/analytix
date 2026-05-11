/* ═══════════════════════════════════════════════════════════════════
   Hourly Output Tracker  —  analytix / hourly_output_tracker
   ═══════════════════════════════════════════════════════════════════ */

frappe.pages["hourly-output-tracker"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Hourly Output Tracker",
		single_column: true,
	});

	$(wrapper).find(".page-head").hide();

	// Full-viewport takeover
	$("header.navbar").hide();
	$(".page-body").css({ padding: "0", margin: "0" });
	$(".layout-main-section-wrapper").css({ padding: "0", margin: "0" });
	$(".layout-main-section").css({ padding: "0", margin: "0", "max-width": "100%" });
	$(wrapper).css({ padding: "0", margin: "0" });
	$(wrapper).find(".page-content").css({ padding: "0", margin: "0" });

	$(wrapper).find(".page-content").append(_buildShell());

	// Nav button handlers
	$(wrapper).on("click", "#hot-prev-day", function () { _shiftDay(-1); });
	$(wrapper).on("click", "#hot-next-day", function () { _shiftDay(+1); });
	$(wrapper).on("click", "#hot-today-btn", function () { _goToday(); });

	_startClock();
	_load();
	_timer = setInterval(function () { _load(); }, 60000);
};

frappe.pages["hourly-output-tracker"].on_page_show = function (wrapper) {
	$("header.navbar").hide();
	$(".page-body").css({ padding: "0", margin: "0" });
	$(".layout-main-section-wrapper").css({ padding: "0", margin: "0" });
	$(".layout-main-section").css({ padding: "0", margin: "0", "max-width": "100%" });
};

frappe.pages["hourly-output-tracker"].on_page_hide = function () {
	$("header.navbar").show();
	$(".page-body").css({ padding: "", margin: "" });
	$(".layout-main-section-wrapper").css({ padding: "", margin: "" });
	$(".layout-main-section").css({ padding: "", margin: "", "max-width": "" });
	if (_timer) { clearInterval(_timer); _timer = null; }
};

// ── State ─────────────────────────────────────────────────────────────────────
var _timer        = null;
var _currentDate  = _todayStr();   // "YYYY-MM-DD"

// Section display names (must match Physical Cell cell_name values in DB)
var SECTIONS = [
	"Knitting", "Mending", "Washing", "Cutting", "Linking",
	"Sewing", "Production Out", "Embroidery", "Pressing",
	"Final Checking", "Packing"
];

// Regular time slots (hour strings) — 1 PM is skipped (lunch)
// Slot keys match Python TIME_SLOTS — each key = end of the 1-hour window
// e.g. "09:00" slot = scans from 08:00-08:59
var TIME_SLOTS = [
	"09:00", "10:00", "11:00", "12:00", "13:00",
	"15:00", "16:00", "17:00", "18:00", "19:00"
];

var SLOT_LABELS = {
	"09:00": "9:00 AM",   // 8:00 AM - 9:00 AM
	"10:00": "10:00 AM",  // 9:00 AM - 10:00 AM
	"11:00": "11:00 AM",  // 10:00 AM - 11:00 AM
	"12:00": "12:00 PM",  // 11:00 AM - 12:00 PM
	"13:00": "1:00 PM",   // 12:00 PM - 1:00 PM
	"15:00": "3:00 PM",   // 2:00 PM - 3:00 PM
	"16:00": "4:00 PM",   // 3:00 PM - 4:00 PM
	"17:00": "5:00 PM",   // 4:00 PM - 5:00 PM
	"18:00": "6:00 PM",   // 5:00 PM - 6:00 PM
	"19:00": "7:00 PM",   // 6:00 PM - 7:00 PM
	"overtime": "Overtime"
};

// ── Utility ───────────────────────────────────────────────────────────────────
function _todayStr() {
	var d = new Date();
	return d.getFullYear() + "-" +
		String(d.getMonth() + 1).padStart(2, "0") + "-" +
		String(d.getDate()).padStart(2, "0");
}

function _fmtDisplayDate(ymd) {
	var parts = ymd.split("-");
	var d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
	var days   = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
	var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
	return days[d.getDay()] + ", " + String(d.getDate()).padStart(2, "0") + " " + months[d.getMonth()] + " " + d.getFullYear();
}

function _shiftDay(delta) {
	var parts = _currentDate.split("-");
	var d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
	d.setDate(d.getDate() + delta);
	_currentDate = d.getFullYear() + "-" +
		String(d.getMonth() + 1).padStart(2, "0") + "-" +
		String(d.getDate()).padStart(2, "0");
	_updateDateDisplay();
	_load();
}

function _goToday() {
	_currentDate = _todayStr();
	_updateDateDisplay();
	_load();
}

function _updateDateDisplay() {
	$("#hot-date-label").text(_fmtDisplayDate(_currentDate));
}

// ── Clock ─────────────────────────────────────────────────────────────────────
function _startClock() { _tick(); setInterval(_tick, 1000); }
function _tick() {
	var d = new Date();
	var h = d.getHours(), m = String(d.getMinutes()).padStart(2, "0");
	var ampm = h >= 12 ? "PM" : "AM";
	h = h % 12 || 12;
	$("#hot-live-time").text(h + ":" + m + " " + ampm);
}

// ── Data load ─────────────────────────────────────────────────────────────────
function _load() {
	frappe.call({
		method: "analytix.analytix.page.hourly_output_tracker.hourly_output_tracker.get_hourly_data",
		args: { work_date: _currentDate },
		freeze: false,
		callback: function (r) {
			if (r.exc) {
				_setTableState("&#9888; Failed to load data. Check server logs.");
				return;
			}
			var msg = r.message || {};
			_render(msg);
			$("#hot-last-updated").text("Last updated: " + new Date().toLocaleTimeString());
		},
	});
}

// ── HTML shell ────────────────────────────────────────────────────────────────
function _buildShell() {
	var colHeaders = SECTIONS.map(function (s) {
		return '<th class="hot-th-section">' + s + "</th>";
	}).join("");

	return `
<div class="hot-root">
  <!-- Top bar -->
  <div class="hot-topbar">
    <div class="hot-brand">
      <svg class="hot-brand-icon" width="38" height="38" viewBox="0 0 38 38" fill="none">
        <rect width="38" height="38" rx="9" fill="#00d4aa" fill-opacity="0.12"/>
        <path d="M8 22 L13 15 L18 20 L23 13 L30 22" stroke="#00d4aa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
        <circle cx="30" cy="22" r="2.5" fill="#00d4aa"/>
      </svg>
      <div>
        <div class="hot-brand-title">Production Dashboard</div>
        <div class="hot-brand-sub">Hourly Output Tracker</div>
      </div>
    </div>
    <div class="hot-date-nav">
      <button class="hot-nav-btn" id="hot-prev-day" title="Previous day">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <div class="hot-date-pill">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        <span id="hot-date-label">---</span>
      </div>
      <button class="hot-nav-btn" id="hot-next-day" title="Next day">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      </button>
      <button class="hot-today-btn" id="hot-today-btn">Today</button>
    </div>
    <div class="hot-clock">
      <div id="hot-live-time">--:-- --</div>
      <div class="hot-total-badge">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        <span id="hot-total-units">0</span> total units
      </div>
    </div>
  </div>

  <!-- Table -->
  <div class="hot-scroll">
    <table class="hot-table">
      <thead>
        <tr class="hot-head-row">
          <th class="hot-th-timeslot">Time Slot</th>
          ${colHeaders}
        </tr>
      </thead>
      <tbody id="hot-tbody">
        <tr><td colspan="${SECTIONS.length + 1}" class="hot-state">Loading&hellip;</td></tr>
      </tbody>
    </table>
  </div>

  <!-- Footer tiles -->
  <div class="hot-tiles" id="hot-tiles"></div>

  <div class="hot-footer-bar">
    <span id="hot-last-updated">Last updated: --</span>
    <span class="hot-refresh-note">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"/>
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
      </svg>
      Auto-refresh every 60s
    </span>
  </div>
</div>`;
}

// ── Render ────────────────────────────────────────────────────────────────────
function _setTableState(msg) {
	$("#hot-tbody").html(
		'<tr><td colspan="' + (SECTIONS.length + 1) + '" class="hot-state">' + msg + "</td></tr>"
	);
}

function _render(msg) {
	var data          = msg.data          || {};
	var section_totals = msg.section_totals || {};
	var targets       = msg.targets       || {};
	var allSlots      = TIME_SLOTS.concat(["overtime"]);

	// ── Table body ────────────────────────────────────────────────────────
	var tbody = "";

	allSlots.forEach(function (slot) {
		var slotData = data[slot] || {};
		var isOvertime = slot === "overtime";
		var rowClass = isOvertime ? "hot-row hot-row-overtime" : "hot-row";

		var cells = SECTIONS.map(function (sec) {
			var val = slotData[sec] || 0;
			var display = val > 0 ? '<span class="hot-cell-val">' + val + "</span>" : '<span class="hot-cell-empty">—</span>';
			return '<td class="hot-td">' + display + "</td>";
		}).join("");

		var label = isOvertime
			? '<span class="hot-overtime-label">Overtime</span>'
			: SLOT_LABELS[slot] || slot;

		tbody += '<tr class="' + rowClass + '"><td class="hot-td-timeslot">' + label + "</td>" + cells + "</tr>";
	});

	$("#hot-tbody").html(tbody);

	// Overall total
	var grandTotal = Object.values(section_totals).reduce(function (s, v) { return s + (v || 0); }, 0);
	$("#hot-total-units").text(grandTotal);

	// ── Footer tiles ──────────────────────────────────────────────────────
	var tilesHtml = SECTIONS.map(function (sec) {
		var actual   = section_totals[sec] || 0;
		var target   = targets[sec] || 0;
		var variance = actual - target;
		var varClass = variance > 0 ? "hot-var-pos" : variance < 0 ? "hot-var-neg" : "hot-var-zero";
		var varSign  = variance > 0 ? "+" : "";
		var varLabel = "Variance: " + varSign + variance;

		return `<div class="hot-tile">
  <div class="hot-tile-name">${sec}</div>
  <div class="hot-tile-actual">${actual}</div>
  <div class="hot-tile-meta">
    <span class="hot-tile-target">Target: ${target}</span>
    <span class="hot-tile-variance ${varClass}">${varLabel}</span>
  </div>
</div>`;
	}).join("");

	$("#hot-tiles").html(tilesHtml);

	// Update date label in case it wasn't set yet
	_updateDateDisplay();
}

// Initialise date display immediately
_updateDateDisplay();