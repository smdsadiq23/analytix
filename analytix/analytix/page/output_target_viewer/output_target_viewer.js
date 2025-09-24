// Viewer: Output vs Target (hourly + daily)
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
  const APPLY_COMPANY_FILTER = true; // only if DocType actually has `company`
  const COLORS = { output: "#96BE37", target: "#ECAD4B" };
  const REPORT_NAME = "Output vs Target";
  const MAX_RANGE_DAYS = 45; // safety cap for daily chart calls

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

  // ---------- Controls (shared filters) ----------
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

  // ---------- Date range just for chart #2 ----------
  const fFrom = page.add_field({
    fieldtype: "Date",
    fieldname: "from_date",
    label: "From Date",
    default: frappe.datetime.month_start(), // default to current month start
  });
  const fTo = page.add_field({
    fieldtype: "Date",
    fieldname: "to_date",
    label: "To Date",
    default: frappe.datetime.get_today(),
  });

  // ===== Overflow fix for MultiSelects (scoped) =====
  $("#kpi-ms-overflow-fix").remove();
  msCell.$wrapper.addClass("kpi-ms");
  msOp.$wrapper.addClass("kpi-ms");
  $(`<style id="kpi-ms-overflow-fix">
    .page-form .frappe-control { min-width: 0; }

    .kpi-ms .form-control.input-xs {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .kpi-ms .control-input, .kpi-ms .control-input-wrapper {
      display: flex; flex-wrap: wrap; gap: 4px; overflow: hidden;
    }
    .kpi-ms input.input-with-feedback {
      min-width: 140px; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
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
  </style>`).appendTo(document.head);

  // Add clear buttons
  function addClear(control, fieldname, isMulti=false){
    const $host = control.$wrapper.find(".control-input, .control-input-wrapper").first().length
      ? control.$wrapper.find(".control-input, .control-input-wrapper").first()
      : control.$wrapper;
    let $btn = $host.find(`.kpi-clear-btn[data-for="${fieldname}"]`);
    if (!$btn.length) {
      $btn = $(`<button type="button" class="kpi-clear-btn" data-for="${fieldname}" title="Clear">×</button>`)
        .appendTo($host)
        .on("click", (e)=>{
          e.preventDefault(); e.stopPropagation();
          if (isMulti) { try { control.set_value([]); } catch {} }
          else { try { control.set_value(""); } catch {}; try { control.set_input && control.set_input(""); } catch {}; control.$input && control.$input.val(""); }
          control.$input && control.$input.trigger("input").trigger("change");
        });
    }
  }
  addClear(fDate, "date", false);

  // ---------- Prefill ----------
  const qp = frappe.utils.get_query_params();
  if (qp.date) fDate.set_value(qp.date);

  // ---------- Layout for charts (SIDE-BY-SIDE) ----------
  const $chartsRow = $(`
    <div class="row" style="margin-top: 20px;">
      <div class="col-md-6">
        <div class="h6 text-muted" style="margin-bottom:4px;">Hourly — selected day</div>
        <canvas id="chartHourly" style="max-height:420px; width:100%;"></canvas>
      </div>
      <div class="col-md-6">
        <div class="h6 text-muted" style="margin-bottom:4px;">Daily — between From/To dates</div>
        <canvas id="chartDaily" style="max-height:420px; width:100%;"></canvas>
      </div>
    </div>
  `).appendTo($root);

  const $canvas1 = $chartsRow.find("#chartHourly");
  const $canvas2 = $chartsRow.find("#chartDaily");

  // ---------- Utils ----------
  function loadChartJs() {
    return new Promise((resolve, reject) => {
      if (window.Chart) return resolve();
      frappe.require("https://cdn.jsdelivr.net/npm/chart.js", resolve);
      setTimeout(() => !window.Chart && reject(new Error("Chart.js failed to load")), 5000);
    });
  }

  function normalizeMS(val) {
    if (!val) return [];
    if (!Array.isArray(val)) return [];
    return val.map(x => (typeof x === "string" ? x : (x && (x.value || x.label || x.name || x.id)) || ""))
             .filter(Boolean);
  }

  function getSharedCsvFilters() {
    const cells = normalizeMS(msCell.get_value && msCell.get_value());
    const ops   = normalizeMS(msOp.get_value   && msOp.get_value());
    return {
      physical_cell_csv: (cells || []).join(","),
      operation_csv:     (ops   || []).join(","),
    };
  }

  function fmtDate(d) {
    // d is "YYYY-MM-DD"
    return d;
  }

  function* dateRange(from, to) {
    // from/to "YYYY-MM-DD"
    const d0 = frappe.datetime.str_to_obj(from);
    const d1 = frappe.datetime.str_to_obj(to);
    for (let d = d0; d <= d1; d = frappe.datetime.add_days(d, 1)) {
      yield frappe.datetime.obj_to_str(d).split(" ")[0];
    }
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
          maintainAspectRatio: false,
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
    if (!from_date || !to_date) { /* optional: message */ return; }

    // validate range size
    const days = frappe.datetime.get_day_diff(to_date, from_date) + 1;
    if (days > MAX_RANGE_DAYS) {
      frappe.msgprint(`Please select a date range ≤ ${MAX_RANGE_DAYS} days.`);
      return;
    }

    const shared = getSharedCsvFilters();

    try {
      // Call the SAME report per-day and aggregate totals (no backend change needed)
      const dates = Array.from(dateRange(from_date, to_date));
      const calls = dates.map(d =>
        frappe.call({
          method: "frappe.desk.query_report.run",
          args: { report_name: REPORT_NAME, filters: { date: d, ...shared } },
        })
      );
      const results = await Promise.all(calls);

      // For each day, sum the "output" from hourly rows
      const labels = [];
      const output = [];
      const target = []; // still zero unless you add target logic

      results.forEach((resp, idx) => {
        const rows = ((resp || {}).message || {}).result || [];
        const totalOut = rows.reduce((s, r) => s + Number(r.output || 0), 0);
        const totalTgt = rows.reduce((s, r) => s + Number(r.target || 0), 0);
        labels.push(fmtDate(dates[idx]));
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
          maintainAspectRatio: false,
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

  // Hourly chart triggers
  fDate.$input && fDate.$input.on("change", runHourlyDebounced);

  function bindMultiSelect(ms) {
    if (!ms) return;
    ms.$input && ms.$input.on("input change awesomplete-selectcomplete", () => { runHourlyDebounced(); runDailyDebounced(); });
    $(ms.$wrapper).on("click", ".amp-token-remove,.awesomplete .remove,.selected-pill .remove,.selected-item .remove", () => { runHourlyDebounced(); runDailyDebounced(); });
    const host = ms.$wrapper.find(".control-input-wrapper, .control-input").get(0);
    if (host && !ms._kpiObs) {
      ms._kpiObs = new MutationObserver(() => { runHourlyDebounced(); runDailyDebounced(); });
      ms._kpiObs.observe(host, { childList: true, subtree: true });
    }
  }
  bindMultiSelect(msCell);
  bindMultiSelect(msOp);

  // Daily chart triggers (range)
  fFrom.$input && fFrom.$input.on("change", runDailyDebounced);
  fTo.$input   && fTo.$input.on("change", runDailyDebounced);

  // ---------- Initial renders ----------
  renderHourly();
  renderDaily();
};