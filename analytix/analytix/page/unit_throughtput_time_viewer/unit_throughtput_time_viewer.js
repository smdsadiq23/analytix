// Viewer: Unit Throughput KPI
// Route: /app/unit-throughtput-time-viewer

frappe.pages["unit-throughtput-time-viewer"].on_page_load = function (wrapper) {
  if (wrapper.__ut_cleanup) { try { wrapper.__ut_cleanup(); } catch {} }

  if (window.CX && typeof CX.mountBreadcrumb === "function") {
    CX.mountBreadcrumb({
      wrapper,
      trail: [
        { label: "KPI Hub", href: "/app/kpi-hub" },
        { label: "Unit Throughput Time" }
      ]
    });
  }

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Unit Throughput Time",
    single_column: true,
  });

  const $root = $(wrapper).find(".layout-main-section");
  const MOUNT_ID = "ut-kpi-mount";
  $root.empty().append(`<div id="${MOUNT_ID}"></div>`);
  const $mount = $root.find("#" + MOUNT_ID);

  const REPORT_NAME = "Unit Throughput Time";
  const MAX_DAYS = 60;
  let chartCell = null, chartDate = null;

  // ===== Styles =====
  $("#ut-kpi-styles").remove();
  $(`<style id="ut-kpi-styles">
    #${MOUNT_ID} .page-form .frappe-control { min-width: 0; }
    .kpi-filter-row { display:flex; flex-wrap:wrap; gap:16px; margin-bottom:12px; align-items:center; }
    .kpi-filter-row .frappe-control { min-width:220px; }
    .kpi-row { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    @media (max-width:1100px){ .kpi-row { grid-template-columns:1fr; } }
    .kpi-card { border:1px solid var(--border-color,#e5e7eb); border-radius:8px; padding:12px; background:#fff; margin-bottom:16px; }
    .kpi-card h6 { margin:0 0 6px 0; color:var(--text-muted,#6b7280); font-weight:600; }
    .kpi-value { font-size:28px; font-weight:700; }
    .kpi-sub { color:#6b7280; font-size:12px; }
    .kpi-card canvas { width:100%; height:420px; max-height:420px; }
    .kpi-ms .form-control.input-xs { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .kpi-ms .control-input, .kpi-ms .control-input-wrapper { display:flex; flex-wrap:wrap; gap:4px; overflow:hidden; }
    .kpi-ms input.input-with-feedback { min-width:140px; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .kpi-clear-host { position:relative !important; }
    .kpi-clear-btn { position:absolute; right:12px; top:50%; transform:translateY(-50%);
      line-height:1; padding:0 8px; border:0; background:transparent; color:var(--gray-600);
      cursor:pointer; border-radius:6px; z-index:2; }
    .kpi-clear-btn:hover { background:var(--gray-100); }
    .awesomplete { z-index:10000 !important; }
    .awesomplete > ul { z-index:10000 !important; position:absolute !important; top:auto !important; bottom:auto !important; }
  </style>`).appendTo(document.head);

  // ===== Layout =====
  $mount.html(`
    <div class="kpi-filter-row" id="ut-filters"></div>

    <div class="kpi-row" style="margin-bottom:16px;">
      <div class="kpi-card">
        <h6>Average TPT</h6>
        <div class="kpi-value" id="ut-avg-tpt">-- min</div>
        <div class="kpi-sub" id="ut-avg-summary"></div>
      </div>
      <div class="kpi-card">
        <h6>Notes</h6>
        <div class="kpi-sub">
          Includes only units that reached the last process. All filters across the top
          are applied server-side for every fetch.
        </div>
      </div>
    </div>

    <div class="kpi-row">
      <div class="kpi-card">
        <h6>Average TPT by Cell</h6>
        <canvas id="ut-chart-cell"></canvas>
      </div>
      <div class="kpi-card">
        <h6>Average TPT by Date</h6>
        <canvas id="ut-chart-date"></canvas>
      </div>
    </div>
  `);

  // ===== Controls =====
  const fRange = page.add_field({
    fieldtype: "DateRange",
    fieldname: "date_range",
    label: "Last Operation Scan Date",
    default: [frappe.datetime.month_start(), frappe.datetime.get_today()],
    reqd: 1,
  });

  const fStyle = page.add_field({
    fieldtype: "Link",
    fieldname: "style",
    label: "Style",
    options: "Item",
  });

  const fSO = page.add_field({
    fieldtype: "Link",
    fieldname: "sales_order",
    label: "Sales Order",
    options: "Sales Order",
  });

  const fWO = page.add_field({
    fieldtype: "Link",
    fieldname: "work_order",
    label: "Work Order",
    options: "Work Order",
  });

  const fCell = page.add_field({
    fieldtype: "MultiSelectList",
    fieldname: "physical_cell_list",
    label: "Physical Cell",
    get_data: async (txt) => frappe.db.get_link_options("Physical Cell", txt),
  });

  // requested order (Physical Cell last)
  const $filters = $mount.find("#ut-filters");
  [fRange, fStyle, fSO, fWO, fCell].forEach(f => $filters.append($("<div>").append(f.$wrapper)));
  fCell.$wrapper.addClass("kpi-ms");

  // ===== Helpers =====
  function attachClearButton(field, onClear) {
    if (!field || !field.$wrapper) return;
    const fname = field.df.fieldname;
    const $host = field.$wrapper.find(".control-input, .control-input-wrapper").first().length
      ? field.$wrapper.find(".control-input, .control-input-wrapper").first()
      : field.$wrapper;
    $host.addClass("kpi-clear-host");

    const ensure = () => {
      let $btn = $host.find(`.kpi-clear-btn[data-for="${fname}"]`);
      if (!$btn.length) {
        $btn = $(`<button type="button" class="kpi-clear-btn" data-for="${fname}" title="Clear">×</button>`).appendTo($host);
        $btn.on("mousedown", async (e) => {
          e.preventDefault();
          try {
            if (field.df.fieldtype === "DateRange") { await field.set_value([]); }
            else if (field.df.fieldtype === "MultiSelectList") { await field.set_value([]); }
            else { await field.set_value(""); }
          } catch {}
          $host.find("input").val("").trigger("input").trigger("change").trigger("awesomplete-selectcomplete");
          try { field.on_change && field.on_change(); } catch {}
          try { onClear && onClear(); } catch {}
          toggle();
        });
      }
      const hasVal = () => {
        try {
          const v = field.get_value ? field.get_value() : null;
          if (field.df.fieldtype === "DateRange") return Array.isArray(v) && (v[0] || v[1]);
          if (field.df.fieldtype === "MultiSelectList") return Array.isArray(v) && v.length > 0;
          return typeof v === "string" ? v.trim().length > 0 : !!v;
        } catch { return false; }
      };
      const toggle = () => $btn.toggle(!!hasVal());
      $host.find("input").off(".utClear")
        .on("input.utClear change.utClear awesomplete-selectcomplete.utClear", toggle);
      if (!field._utPatched) {
        const orig = field.on_change;
        field.on_change = function(){ toggle(); orig && orig.call(this); };
        field._utPatched = true;
      }
      toggle();
    };
    ensure();
    if (field._utObs) field._utObs.disconnect();
    const obs = new MutationObserver(() => ensure());
    obs.observe($host[0], { childList: true, subtree: true });
    field._utObs = obs;
  }

  function msNormalize(val) {
    if (!val) return [];
    if (!Array.isArray(val)) return [];
    return val
      .map(x => (typeof x === "string" ? x : (x && (x.value || x.label || x.name || x.id)) || ""))
      .filter(Boolean);
  }

  function enumerateDates(from, to) {
    const out = [];
    if (!from || !to) return out;
    const a = new Date(from + "T00:00:00");
    const b = new Date(to + "T00:00:00");
    if (isNaN(a) || isNaN(b)) return out;
    for (let d = new Date(a); d <= b; d.setDate(d.getDate() + 1)) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const dd = String(d.getDate()).padStart(2, "0");
      out.push(`${y}-${m}-${dd}`);
    }
    return out;
  }

  function fmtHMS(sec) {
    if (sec == null || !isFinite(sec)) return "--:--:--";
    sec = Math.max(0, Math.round(sec));
    const h = Math.floor(sec/3600);
    const m = Math.floor((sec%3600)/60);
    const s = sec%60;
    return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  }

  function fmtMin(num) {
    if (num == null || !isFinite(num)) return "-- min";
    return `${Number(num).toFixed(1)} min`;
  }

  function toDDMMYYYY(iso) {
    if (!iso) return "";
    const [y,m,d] = iso.split("-");
    return `${d}-${m}-${y}`;
  }

  function mean(nums) {
    const arr = (nums || []).filter(x => x != null && isFinite(x));
    if (!arr.length) return null;
    return arr.reduce((a,b)=>a+b,0)/arr.length;
  }

  async function loadChartJs() {
    if (window.Chart) return;
    await new Promise((resolve) => frappe.require("https://cdn.jsdelivr.net/npm/chart.js", resolve));
  }

  function destroyCharts(){
    try{ chartCell?.destroy(); }catch{}
    try{ chartDate?.destroy(); }catch{}
    chartCell=null; chartDate=null;
  }

  // Build ONE payload object that mirrors backend expectations
  function getPayload() {
    const dr = fRange.get_value() || [];
    const date_range = Array.isArray(dr) ? dr : [];
    const cells = msNormalize(fCell.get_value && fCell.get_value());
    const payload = {
      date_range,                                 // backend uses this
      style:       fStyle.get_value && fStyle.get_value(),
      sales_order: fSO.get_value && fSO.get_value(),
      work_order:  fWO.get_value && fWO.get_value(),
      physical_cell_csv: (cells || []).join(",")
    };
    // [DBG]
    try {
      console.groupCollapsed("[UT-KPI] getPayload");
      console.log("payload", payload);
      console.groupEnd();
    } catch {}
    return payload;
  }

  // Call the report for a single day, but ALWAYS include the other filters too
  async function callReportSingle(dateISO, sharedFilters) {
    const filters = {
      date: dateISO,
      style: sharedFilters.style || "",
      sales_order: sharedFilters.sales_order || "",
      work_order: sharedFilters.work_order || "",
      physical_cell_csv: sharedFilters.physical_cell_csv || ""
    };

    // [DBG] pre-call
    try {
      console.groupCollapsed(`[UT-KPI] callReportSingle ${dateISO}`);
      console.log("filters", filters);
      console.groupEnd();
    } catch {}

    const resp = await frappe.call({
      method: "frappe.desk.query_report.run",
      args: { report_name: REPORT_NAME, filters },
    });

    const list = resp?.message?.report_summary || [];
    const map = {}; list.forEach(it => { if (it?.name) map[it.name] = it.data; });

    // [DBG] expose + log
    try {
      window.__UTKPI_DEBUG = window.__UTKPI_DEBUG || {};
      window.__UTKPI_DEBUG[dateISO] = { filters, raw: resp?.message, map };
      console.groupCollapsed(`[UT-KPI] resp ${dateISO}`);
      console.log("raw.message keys", Object.keys(resp?.message || {}));
      console.log("report_summary length:", Array.isArray(resp?.message?.report_summary) ? resp.message.report_summary.length : null);
      if (map.by_cell) console.table(map.by_cell);
      if (map.overall) console.table(map.overall);
      console.groupEnd();
    } catch {}

    return { by_cell: map.by_cell || [], overall: map.overall || [] };
  }

  async function loadAll() {
    destroyCharts();

    const payload = getPayload();
    const [from_date, to_date] = payload.date_range || [];

    // [DBG]
    try {
      console.groupCollapsed("[UT-KPI] loadAll");
      console.log("date_range", payload.date_range);
      console.log("style", payload.style, "sales_order", payload.sales_order, "work_order", payload.work_order);
      console.log("physical_cell_csv", payload.physical_cell_csv);
      console.groupEnd();
    } catch {}

    if (!from_date || !to_date) {
      frappe.show_alert({ message: "Select a Last Operation Scan Date range", indicator: "orange" }, 5);
      $("#ut-avg-tpt").text("-- min"); $("#ut-avg-summary").text("");
      return;
    }

    const diff = frappe.datetime.get_day_diff(to_date, from_date) + 1;
    if (diff > MAX_DAYS) {
      frappe.msgprint(`Please select a date range ≤ ${MAX_DAYS} days for the 'By Date' chart.`);
    }

    const dates = enumerateDates(from_date, to_date).slice(0, MAX_DAYS);

    let perDay = [];
    try {
      perDay = await Promise.all(dates.map(d => callReportSingle(d, payload)));
    } catch (e) {
      console.error("Unit TPT report error:", e);
      frappe.show_alert({ message: "Failed to load data", indicator: "red" }, 5);
      return;
    }

    const allOverall = [], allByCell = [];
    dates.forEach((d, i) => {
      const one = perDay[i] || { overall: [], by_cell: [] };
      (one.overall || []).forEach(r => allOverall.push({ ...r, _date: d }));
      (one.by_cell || []).forEach(r => allByCell.push({ ...r, _date: d }));
    });

    // KPI value in MINUTES (overall)
    const kpiSeconds = mean(allOverall.map(r => Number(r.tpt_seconds || 0)));
    const kpiMinutes = (kpiSeconds != null) ? (kpiSeconds / 60) : null;
    $("#ut-avg-tpt").text(fmtMin(kpiMinutes));
    $("#ut-avg-summary").text(`${(allOverall || []).length} completed unit(s) across ${dates.length} day(s)`);

    // By Cell (minutes)
    const byCell = new Map();
    (allByCell || []).forEach(r => {
      const k = r.physical_cell || "(Unspecified)";
      const arr = byCell.get(k) || [];
      if (r.tpt_seconds != null) arr.push(Number(r.tpt_seconds));
      byCell.set(k, arr);
    });
    const cellLabels = Array.from(byCell.keys()).sort((a,b)=>a.localeCompare(b));
    const cellMinutes = cellLabels.map(k => {
      const avgSec = mean(byCell.get(k) || []);
      return avgSec != null ? avgSec / 60 : 0;
    });

    await loadChartJs();
    chartCell = new Chart(document.getElementById("ut-chart-cell").getContext("2d"), {
      type: "bar",
      data: {
        labels: cellLabels,
        datasets: [{ label: "Avg TPT (minutes)", data: cellMinutes, backgroundColor: "#96BE37", borderColor: "#96BE37", borderWidth: 1 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const mins = Number(ctx.raw || 0);
                const secs = mins * 60;
                return `Avg TPT: ${mins.toFixed(1)} min (${fmtHMS(secs)})`;
              }
            }
          },
        },
        scales: { x: { title: { display: true, text: "Physical Cell" } }, y: { title: { display: true, text: "Minutes" }, beginAtZero: true } }
      }
    });

    // By Date (minutes) — from overall rows
    const byDate = new Map();
    (allOverall || []).forEach(r => {
      const k = r._date || "";
      const arr = byDate.get(k) || [];
      if (r.tpt_seconds != null) arr.push(Number(r.tpt_seconds));
      byDate.set(k, arr);
    });
    const dateISO = Array.from(byDate.keys()).sort();
    const dateLabels = dateISO.map(toDDMMYYYY);
    const dateMinutes = dateISO.map(k => {
      const avgSec = mean(byDate.get(k) || []);
      return avgSec != null ? avgSec / 60 : 0;
    });

    chartDate = new Chart(document.getElementById("ut-chart-date").getContext("2d"), {
      type: "bar",
      data: {
        labels: dateLabels,
        datasets: [{ label: "Avg TPT (minutes)", data: dateMinutes, backgroundColor: "#ECAD4B", borderColor: "#ECAD4B", borderWidth: 1 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const mins = Number(ctx.raw || 0);
                const secs = mins * 60;
                return `Avg TPT: ${mins.toFixed(1)} min (${fmtHMS(secs)})`;
              }
            }
          },
        },
        scales: { x: { title: { display: true, text: "Date (dd-mm-yyyy)" } }, y: { title: { display: true, text: "Minutes" }, beginAtZero: true } }
      }
    });
  }

  const triggerReload = frappe.utils.debounce(loadAll, 350);

  [fRange, fStyle, fSO, fWO, fCell].forEach(f => attachClearButton(f, triggerReload));

  // ===== Stronger bindings for the Physical Cell MultiSelect =====
  function bindMultiSelect(ms) {
    if (!ms) return;
    try { console.log("[UT-KPI] Binding MultiSelectList:", ms.df?.fieldname); } catch {}

    if (ms.$input) {
      ms.$input.on("input change awesomplete-selectcomplete", () => {
        try { console.log("[UT-KPI] MS input event", ms.df?.fieldname, "value=", ms.get_value && ms.get_value()); } catch {}
        triggerReload();
      });
    }

    $(ms.$wrapper).on("click", ".amp-token-remove,.awesomplete .remove", () => {
      try { console.log("[UT-KPI] MS token removed", ms.df?.fieldname, "value=", ms.get_value && ms.get_value()); } catch {}
      triggerReload();
    });

    const host = ms.$wrapper.find(".control-input, .control-input-wrapper")[0] || ms.$wrapper[0];
    if (host) {
      const obs = new MutationObserver(() => {
        try { console.log("[UT-KPI] MS DOM mutated", ms.df?.fieldname, "value=", ms.get_value && ms.get_value()); } catch {}
        triggerReload();
      });
      obs.observe(host, { childList: true, subtree: true });
      ms._obs = obs;
    }

    if (typeof ms.on_change === "function") {
      const prev = ms.on_change.bind(ms);
      ms.on_change = (...a) => {
        try { console.log("[UT-KPI] MS on_change", ms.df?.fieldname, "value=", ms.get_value && ms.get_value()); } catch {}
        try { prev(...a); } catch {}
        triggerReload();
      };
    } else {
      ms.on_change = () => {
        try { console.log("[UT-KPI] MS on_change(new)", ms.df?.fieldname, "value=", ms.get_value && ms.get_value()); } catch {}
        triggerReload();
      };
    }
  }
  bindMultiSelect(fCell);

  // Bindings
  fRange.$input && fRange.$input.on("change", () => {
    try { console.log("[UT-KPI] date_range change ->", fRange.get_value && fRange.get_value()); } catch {}
    triggerReload();
  });
  [fStyle, fSO, fWO].forEach(f => f?.$input && f.$input.on("awesomplete-selectcomplete change", () => {
    try { console.log("[UT-KPI] field change", f.df?.fieldname, "->", f.get_value && f.get_value()); } catch {}
    triggerReload();
  }));
  if (fCell?.$input) {
    // keep light bindings too
    fCell.$input.on("input change awesomplete-selectcomplete", triggerReload);
    $(fCell.$wrapper).on("click", ".amp-token-remove,.awesomplete .remove", triggerReload);
  }

  // Initial load
  frappe.after_ajax(() => {
    try { console.log("[UT-KPI] initial triggerReload"); } catch {}
    triggerReload();
  });

  // Cleanup
  wrapper.__ut_cleanup = () => {
    try { fRange._utObs && fRange._utObs.disconnect(); } catch {}
    try { fCell._utObs && fCell._utObs.disconnect(); } catch {}
    try { fCell._obs && fCell._obs.disconnect(); } catch {}
    [fStyle, fSO, fWO].forEach(f => { try { f._utObs && f._utObs.disconnect(); } catch {} });
    try { chartCell && chartCell.destroy(); } catch {}
    try { chartDate && chartDate.destroy(); } catch {}
    $mount.remove();
  };
};
