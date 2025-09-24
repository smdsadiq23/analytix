// Viewer: Output vs Target (hourly + daily, robust filters & date range)
// Route: /app/output-target-viewer

frappe.pages["output-target-viewer"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Output vs Target",
    single_column: true,
  });
  const $root = $(wrapper).find(".layout-main-section");

  // ---------- CONFIG ----------
  const DOCTYPES = { physical_cell: "Physical Cell", operation: "Operation" };
  const APPLY_COMPANY_FILTER = true; // only if DocType has `company`
  const COLORS = { output: "#96BE37", target: "#ECAD4B" };
  const REPORT_NAME = "Output vs Target";
  const MAX_RANGE_DAYS = 45;

  // ---------- Meta: detect "company" in doctypes ----------
  const DT_META = {
    physical_cell: { doctype: DOCTYPES.physical_cell, hasCompany: false },
    operation:     { doctype: DOCTYPES.operation,     hasCompany: false },
  };
  (async () => {
    for (const key of Object.keys(DT_META)) {
      try {
        await frappe.model.with_doctype(DT_META[key].doctype);
        DT_META[key].hasCompany = !!frappe.meta.get_docfield(DT_META[key].doctype, "company", null);
      } catch {
        DT_META[key].hasCompany = false;
      }
    }
  })();

  // ---------- Controls ----------
  const fDate = page.add_field({
    fieldtype: "Date",
    fieldname: "date",
    label: "Date (Hourly)",
    default: frappe.datetime.get_today(),
    reqd: 1,
  });

  const msCell = page.add_field({
    fieldtype: "MultiSelectList",
    fieldname: "physical_cell_list",
    label: "Physical Cell",
    get_data: async (txt) => {
      const filters = {};
      if (APPLY_COMPANY_FILTER && DT_META.physical_cell.hasCompany) {
        const c = frappe.defaults.get_default("Company");
        if (c) filters.company = c;
      }
      return frappe.db.get_link_options(DOCTYPES.physical_cell, txt, filters);
    },
  });

  const msOp = page.add_field({
    fieldtype: "MultiSelectList",
    fieldname: "operation_list",
    label: "Operation",
    get_data: async (txt) => {
      const filters = {};
      if (APPLY_COMPANY_FILTER && DT_META.operation.hasCompany) {
        const c = frappe.defaults.get_default("Company");
        if (c) filters.company = c;
      }
      return frappe.db.get_link_options(DOCTYPES.operation, txt, filters);
    },
  });

  // Date range for Daily chart
  const fFrom = page.add_field({
    fieldtype: "Date",
    fieldname: "from_date",
    label: "From Date (Daily)",
    default: frappe.datetime.month_start(),
  });
  const fTo = page.add_field({
    fieldtype: "Date",
    fieldname: "to_date",
    label: "To Date (Daily)",
    default: frappe.datetime.get_today(),
  });

  // ===== Styles (overflow fix + date clear + 2-col grid) =====
  $("#kpi-ms-overflow-fix").remove();
  msCell.$wrapper.addClass("kpi-ms");
  msOp.$wrapper.addClass("kpi-ms");
  $(`<style id="kpi-ms-overflow-fix">
    .page-form .frappe-control { min-width: 0; }

    .kpi-ms .form-control.input-xs {
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .kpi-ms .control-input, .kpi-ms .control-input-wrapper {
      display: flex; flex-wrap: wrap; gap: 4px; overflow: hidden;
    }
    .kpi-ms input.input-with-feedback {
      min-width: 140px; max-width: 100%;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .kpi-ms .status-text {
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;
    }
    .kpi-ms .amp-token span, .kpi-ms .selected-pill span, .kpi-ms .selected-item span,
    .kpi-ms .awesomplete .token span, .kpi-ms .amp-token .label, .kpi-ms .selected-pill .label {
      max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-block;
    }

    /* Date clear button pin */
    .frappe-control[data-fieldname="date"] .control-input,
    .frappe-control[data-fieldname="date"] .control-input-wrapper { position: relative; }
    .frappe-control[data-fieldname="date"] input.input-with-feedback { padding-right: 26px !important; }
    .frappe-control[data-fieldname="date"] .kpi-clear-btn{
      position:absolute;right:8px;top:50%;transform:translateY(-50%);
      border:0;background:transparent;line-height:1;padding:0 6px;color:var(--gray-600);
      border-radius:6px;cursor:pointer;z-index:2;
    }
    .frappe-control[data-fieldname="date"] .kpi-clear-btn:hover{ background: var(--gray-100); }

    /* Two-column chart grid */
    .kpi-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      align-items: start;
      margin-top: 12px;
    }
    @media (max-width: 1100px) {
      .kpi-grid { grid-template-columns: 1fr; }
    }
    .kpi-card {
      border: 1px solid var(--border-color, #e5e7eb);
      border-radius: 8px;
      padding: 12px;
      background: var(--surface, #fff);
    }
    .kpi-card h6 {
      margin: 0 0 6px 0; color: var(--text-muted, #6b7280); font-weight: 600;
    }
    .kpi-card canvas { width: 100%; height: 420px; max-height: 420px; }
  </style>`).appendTo(document.head);

  // Add clear button for Date
  (function addDateClear() {
    const $host = fDate.$wrapper.find(".control-input, .control-input-wrapper").first().length
      ? fDate.$wrapper.find(".control-input, .control-input-wrapper").first()
      : fDate.$wrapper;
    if (!$host.find('.kpi-clear-btn[data-for="date"]').length) {
      $(`<button type="button" class="kpi-clear-btn" data-for="date" title="Clear">×</button>`)
        .appendTo($host)
        .on("click", (e) => {
          e.preventDefault(); e.stopPropagation();
          try { fDate.set_value(""); } catch {}
          try { fDate.set_input && fDate.set_input(""); } catch {}
          fDate.$input && fDate.$input.val("").trigger("input").trigger("change");
        });
    }
  })();

  // ---------- Prefill ----------
  const qp = frappe.utils.get_query_params();
  if (qp.date) fDate.set_value(qp.date);

  // ---------- Charts layout (two columns) ----------
  const $grid = $(
    `<div class="kpi-grid">
      <div class="kpi-card">
        <h6>Hourly — selected day</h6>
        <canvas id="chartHourly"></canvas>
      </div>
      <div class="kpi-card">
        <h6>Daily — between From/To dates</h6>
        <canvas id="chartDaily"></canvas>
      </div>
    </div>`
  ).appendTo($root);

  const $canvas1 = $grid.find("#chartHourly");
  const $canvas2 = $grid.find("#chartDaily");

  // ---------- Utils ----------
  function loadChartJs() {
    return new Promise((resolve, reject) => {
      if (window.Chart) return resolve();
      frappe.require("https://cdn.jsdelivr.net/npm/chart.js", resolve);
      setTimeout(() => !window.Chart && reject(new Error("Chart.js failed to load")), 5000);
    });
  }

  // Robust read of MultiSelect values (API + DOM fallback)
  function getMSValues(ms) {
    // 1) control API
    try {
      let v = ms && ms.get_value ? ms.get_value() : null;
      if (typeof v === "string") v = v.split(",").map(s => s.trim()).filter(Boolean);
      if (Array.isArray(v)) {
        return v
          .map(x => (typeof x === "string" ? x : (x && (x.value || x.label || x.name || x.id)) || ""))
          .filter(Boolean);
      }
    } catch { /* no-op */ }
    // 2) DOM pills fallback
    try {
      const pills = $(ms.$wrapper).find(
        ".amp-token .label, .selected-pill .label, .selected-item .label, .awesomplete .token .label"
      ).map((i, el) => $(el).text().trim()).get();
      return pills.filter(Boolean);
    } catch { /* no-op */ }
    return [];
  }

  function getSharedCsvFilters() {
    const cells = getMSValues(msCell);
    const ops   = getMSValues(msOp);
    return {
      physical_cell_csv: (cells || []).join(","),
      operation_csv:     (ops   || []).join(","),
    };
  }

  // Safe date enumerator (no Frappe mutation quirks)
  function enumerateDates(from, to) {
    const out = [];
    if (!from || !to) return out;
    const start = new Date(from + "T00:00:00");
    const end   = new Date(to   + "T00:00:00");
    if (isNaN(start) || isNaN(end)) return out;
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      // format YYYY-MM-DD
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      out.push(`${day}-${m}-${y}`);
    }
    return out;
  }

  function debounce(fn, wait = 250){ let t; return (...a)=>{clearTimeout(t); t=setTimeout(()=>fn(...a), wait);} }

  // ---------- Chart renderers ----------
  async function renderHourly() {
    const date = fDate.get_value();
    if (!date) { frappe.msgprint("Please select a Date."); return; }

    const shared = getSharedCsvFilters();
    try {
      const resp = await frappe.call({
        method: "frappe.desk.query_report.run",
        args: { report_name: REPORT_NAME, filters: { date, ...shared } },
      });
      const result = (resp.message || {}).result || [];

      const labels = result.map(r => r.hour_label || "");
      const output = result.map(r => Number(r.output || 0));
      const target = result.map(r => Number(r.target || 0));

      await loadChartJs();
      if ($canvas1[0]._chart) $canvas1[0]._chart.destroy();

      const ctx = $canvas1[0].getContext("2d");
      $canvas1[0]._chart = new Chart(ctx, {
        type: "bar",
        data: {
          labels,
          datasets: [
            { type: "bar",  label: "Output (Qty)", data: output,
              backgroundColor: COLORS.output, borderColor: COLORS.output, borderWidth: 1 },
            { type: "line", label: "Target (Qty)", data: target,
              borderColor: COLORS.target, backgroundColor: COLORS.target,
              borderWidth: 2, pointRadius: 2, tension: 0.25 },
          ]
        },
        options: {
          responsive: true,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "bottom", align: "center", labels: { boxWidth: 12, padding: 12 } },
            title:  { display: true, text: "Output vs Target (Hourly)" },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = Number(ctx.parsed.y ?? 0);
                  const txt = Number.isFinite(v) ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "0";
                  return `${ctx.dataset.label}: ${txt}`;
                }
              }
            }
          },
          scales: {
            x: { title: { display: true, text: "Time (HH:00)" }, ticks: { autoSkip: true, maxTicksLimit: 24 } },
            y: { title: { display: true, text: "Quantity" }, beginAtZero: true }
          }
        }
      });
    } catch (e) {
      frappe.msgprint({ title: "Hourly Chart", message: e.message || e, indicator: "red" });
    }
  }

  async function renderDaily() {
    const from_date = fFrom.get_value();
    const to_date   = fTo.get_value();
    if (!from_date || !to_date) return;

    const days = frappe.datetime.get_day_diff(to_date, from_date) + 1;
    if (days > MAX_RANGE_DAYS) {
      frappe.msgprint(`Please select a date range ≤ ${MAX_RANGE_DAYS} days.`);
      return;
    }

    const shared = getSharedCsvFilters();

    try {
      const dates = enumerateDates(from_date, to_date); // ← robust enumerator
      if (!dates.length) return;

      const calls = dates.map(d =>
        frappe.call({
          method: "frappe.desk.query_report.run",
          args: { report_name: REPORT_NAME, filters: { date: d, ...shared } },
        })
      );
      const results = await Promise.all(calls);

      const labels = [];
      const output = [];
      const target = [];

      results.forEach((resp, idx) => {
        const rows = ((resp || {}).message || {}).result || [];
        const totalOut = rows.reduce((s, r) => s + Number(r.output || 0), 0);
        const totalTgt = rows.reduce((s, r) => s + Number(r.target || 0), 0);
        labels.push(dates[idx]);   // every date in the range
        output.push(totalOut);
        target.push(totalTgt);
      });

      await loadChartJs();
      if ($canvas2[0]._chart) $canvas2[0]._chart.destroy();

      const ctx = $canvas2[0].getContext("2d");
      $canvas2[0]._chart = new Chart(ctx, {
        type: "bar",
        data: {
          labels,
          datasets: [
            { type: "bar",  label: "Output (Qty)", data: output,
              backgroundColor: COLORS.output, borderColor: COLORS.output, borderWidth: 1 },
            { type: "line", label: "Target (Qty)", data: target,
              borderColor: COLORS.target, backgroundColor: COLORS.target,
              borderWidth: 2, pointRadius: 2, tension: 0.25 },
          ]
        },
        options: {
          responsive: true,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "bottom", align: "center", labels: { boxWidth: 12, padding: 12 } },
            title:  { display: true, text: "Output vs Target (Daily)" },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = Number(ctx.parsed.y ?? 0);
                  const txt = Number.isFinite(v) ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "0";
                  return `${ctx.dataset.label}: ${txt}`;
                }
              }
            }
          },
          scales: {
            x: { title: { display: true, text: "Date" } },
            y: { title: { display: true, text: "Quantity" }, beginAtZero: true }
          }
        }
      });
    } catch (e) {
      frappe.msgprint({ title: "Daily Chart", message: e.message || e, indicator: "red" });
    }
  }

  // ---------- Bindings ----------
  const runHourlyDebounced = debounce(renderHourly, 250);
  const runDailyDebounced  = debounce(renderDaily, 300);

  // Hourly triggers
  fDate.$input && fDate.$input.on("change", runHourlyDebounced);

  // Filters shared by both charts — strong bindings + DOM observe
  function bindMultiSelect(ms) {
    if (!ms) return;

    // user typing / selecting from dropdown
    ms.$input && ms.$input.on("input change awesomplete-selectcomplete", () => {
      runHourlyDebounced(); runDailyDebounced();
    });

    // pill remove clicks
    $(ms.$wrapper).on(
      "click",
      ".amp-token-remove,.awesomplete .remove,.selected-pill .remove,.selected-item .remove",
      () => { runHourlyDebounced(); runDailyDebounced(); }
    );

    // observe token container changes (programmatic set_value etc.)
    const host = ms.$wrapper.find(".control-input-wrapper, .control-input").get(0);
    if (host && !ms._kpiObs) {
      ms._kpiObs = new MutationObserver(() => { runHourlyDebounced(); runDailyDebounced(); });
      ms._kpiObs.observe(host, { childList: true, subtree: true });
    }
  }
  bindMultiSelect(msCell);
  bindMultiSelect(msOp);

  // Daily range triggers
  fFrom.$input && fFrom.$input.on("change", runDailyDebounced);
  fTo.$input   && fTo.$input.on("change", runDailyDebounced);

  // ---------- Initial renders ----------
  renderHourly();
  renderDaily();
};
