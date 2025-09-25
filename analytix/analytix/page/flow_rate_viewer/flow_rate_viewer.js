// Viewer: Flow Rate (10-min + Hourly)
// Route: /app/flow-rate-viewer

frappe.pages["flow-rate-viewer"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Flow Rate",
    single_column: true,
  });

  const $root = $(wrapper).find(".layout-main-section");

  // 👇 Add manual breadcrumb bar
  const $breadcrumb = $(`
    <div class="breadcrumb-bar" style="
      padding: 8px 16px;
      background: #f9fafb;
      border-bottom: 1px solid #e5e7eb;
      font-size: 14px;
      margin-bottom: 16px;
    ">
      <a href="/app/kpi-hub" style="color: #1f2937; text-decoration: none;">KPI Hub</a>
      <span style="margin: 0 8px;">></span>
      <span style="color: #6b7280;">Flow Rate</span>
    </div>
  `).prependTo($root);

  
  // ---------- CONFIG ----------
  const DOCTYPES = { physical_cell: "Physical Cell", operation: "Operation" };
  const APPLY_COMPANY_FILTER = true; // only if DocType has "company"
  const COLORS = { output: "#96BE37", target: "#ECAD4B", avg: "#000000" };
  const REPORT_NAME = "Flow Rate";

  // ---------- Meta detector (does the doctype have `company`?) ----------
  const DT_META = {
    physical_cell: { doctype: DOCTYPES.physical_cell, hasCompany: false },
    operation: { doctype: DOCTYPES.operation, hasCompany: false },
  };
  (async () => {
    for (const key of Object.keys(DT_META)) {
      try {
        await frappe.model.with_doctype(DT_META[key].doctype);
        DT_META[key].hasCompany = !!frappe.meta.get_docfield(
          DT_META[key].doctype,
          "company",
          null
        );
      } catch {
        DT_META[key].hasCompany = false;
      }
    }
  })();

  // ---------- Controls ----------
  const fDate = page.add_field({
    fieldtype: "Date",
    fieldname: "date",
    label: "Date",
    default: frappe.datetime.get_today(),
    reqd: 1,
  });

  const msCell = page.add_field({
    fieldtype: "MultiSelectList",
    fieldname: "physical_cell_list",
    label: "Physical Cell",
    reqd: 0,
    get_data: async function (txt) {
      const filters = {};
      if (APPLY_COMPANY_FILTER && DT_META.physical_cell.hasCompany) {
        const company = frappe.defaults.get_default("Company");
        if (company) filters.company = company;
      }
      return frappe.db.get_link_options(DOCTYPES.physical_cell, txt, filters);
    },
  });

  const msOp = page.add_field({
    fieldtype: "MultiSelectList",
    fieldname: "operation_list",
    label: "Operation",
    reqd: 0,
    get_data: async function (txt) {
      const filters = {};
      if (APPLY_COMPANY_FILTER && DT_META.operation.hasCompany) {
        const company = frappe.defaults.get_default("Company");
        if (company) filters.company = company;
      }
      return frappe.db.get_link_options(DOCTYPES.operation, txt, filters);
    },
  });

  // ===== Styles =====
  $("#kpi-ms-overflow-fix").remove();
  msCell.$wrapper.addClass("kpi-ms");
  msOp.$wrapper.addClass("kpi-ms");
  $(`<style id="kpi-ms-overflow-fix">
    .page-form .frappe-control { min-width: 0; }
    .kpi-ms .form-control.input-xs { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .kpi-ms .control-input, .kpi-ms .control-input-wrapper { display:flex; flex-wrap:wrap; gap:4px; overflow:hidden; }
    .kpi-ms input.input-with-feedback { min-width:140px; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .kpi-ms .status-text { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100%; }
    .kpi-ms .amp-token span, .kpi-ms .selected-pill span, .kpi-ms .selected-item span,
    .kpi-ms .awesomplete .token span, .kpi-ms .amp-token .label, .kpi-ms .selected-pill .label {
      max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:inline-block;
    }
    .frappe-control[data-fieldname="date"] .control-input,
    .frappe-control[data-fieldname="date"] .control-input-wrapper { position: relative; }
    .frappe-control[data-fieldname="date"] input.input-with-feedback { padding-right: 26px !important; }
    .frappe-control[data-fieldname="date"] .kpi-clear-btn{
      position:absolute; right:8px; top:50%; transform:translateY(-50%);
      border:0; background:transparent; line-height:1; padding:0 6px; color:var(--gray-600);
      border-radius:6px; cursor:pointer; z-index:2;
    }
    .frappe-control[data-fieldname="date"] .kpi-clear-btn:hover{ background: var(--gray-100); }      
    .kpi-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start; margin-top:12px; }
    @media (max-width:1100px){ .kpi-grid { grid-template-columns:1fr; } }
    .kpi-card { border:1px solid var(--border-color,#e5e7eb); border-radius:8px; padding:12px; background:#fff; }
    .kpi-card h6 { margin:0 0 6px 0; color:var(--text-muted,#6b7280); font-weight:600; }
    .kpi-card canvas { width:100%; height:420px; max-height:420px; }
  </style>`).appendTo(document.head);

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

  // ---------- Prefill from query params ----------
  const qp = frappe.utils.get_query_params();
  if (qp.date) fDate.set_value(qp.date);

  // ---------- Charts layout ----------
  const $grid = $(
    `<div class="kpi-grid">
      <div class="kpi-card">
        <h6>10-min Flow Rate — selected day</h6>
        <canvas id="chart10"></canvas>
      </div>
      <div class="kpi-card">
        <h6>Hourly Flow Rate — selected day</h6>
        <canvas id="chartHr"></canvas>
      </div>
    </div>`
  ).appendTo($root);

  const $canvas10 = $grid.find("#chart10");
  const $canvasHr = $grid.find("#chartHr");

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
    return val
      .map((x) => (typeof x === "string" ? x : (x && (x.value || x.label)) || ""))
      .filter(Boolean);
  }

  function getSharedCsvFilters() {
    const cells = normalizeMS(msCell.get_value ? msCell.get_value() : []);
    const ops = normalizeMS(msOp.get_value ? msOp.get_value() : []);
    return { physical_cell_csv: cells.join(","), operation_csv: ops.join(",") };
  }

  async function fetchRows() {
    const date = fDate.get_value();
    if (!date) {
      frappe.msgprint("Please select a Date.");
      return [];
    }
    const shared = getSharedCsvFilters();
    const resp = await frappe.call({
      method: "frappe.desk.query_report.run",
      args: { report_name: REPORT_NAME, filters: { date, ...shared } },
    });
    return ((resp || {}).message || {}).result || [];
  }

  function splitRows(rows) {
    const ten = rows.filter((r) => (r.level || "").toLowerCase() === "ten_min");
    const hr = rows.filter((r) => (r.level || "").toLowerCase() === "hour");
    return { ten, hr };
  }

  // ---------- Renderers ----------
  async function renderTen() {
    const rows = await fetchRows();
    const { ten } = splitRows(rows);
    await loadChartJs();
    if ($canvas10[0]._chart) $canvas10[0]._chart.destroy();

    let labels = ten.map((r) => r.label || "");
    let output = ten.map((r) => Number(r.output || 0));
    let target = ten.map((r) => Number(r.target || 0));
    let avg    = ten.map((r) => Number(r.avg_output || 0));

    const ctx = $canvas10[0].getContext("2d");
    $canvas10[0]._chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { type: "bar",  label: "Output (Qty)", data: output,
            backgroundColor: COLORS.output, borderColor: COLORS.output, borderWidth: 1 },
          { type: "line", label: "Target (Qty)", data: target,
            borderColor: COLORS.target, backgroundColor: "transparent",
            borderWidth: 2, pointRadius: 0, tension: 0.25 },
          { type: "line", label: "Avg Output", data: avg,
            borderColor: COLORS.avg, backgroundColor: "transparent",
            borderWidth: 2, pointRadius: 0, tension: 0.25 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "bottom", align: "center", labels: { boxWidth: 12, padding: 12 } },
          title:  { display: true, text: "Flow Rate — every 10 minutes" },
          tooltip: {
            callbacks: { label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.y ?? 0).toLocaleString()}` },
          },
        },
        scales: {
          x: {
            type: "category",                 // CHANGED
            title: { display: true, text: "Time (10-min)" },
            ticks: {
              autoSkip: false,               // CHANGED: show every 10-min tick
              maxRotation: 60,               // CHANGED: readable angle
              minRotation: 60,               // CHANGED
              font: { size: 10 },            // CHANGED: smaller tick font
              callback: (value, idx) => labels[idx], // CHANGED: ensure raw label is used
            },
          },
          y: { title: { display: true, text: "Quantity" }, beginAtZero: true },
        },
      },
    });
  }

  async function renderHr() {
    const rows = await fetchRows();
    const { hr } = splitRows(rows);
    await loadChartJs();
    if ($canvasHr[0]._chart) $canvasHr[0]._chart.destroy();

    const labels = hr.map((r) => r.label || "");
    const output = hr.map((r) => Number(r.output || 0));
    const target = hr.map((r) => Number(r.target || 0));
    const avg    = hr.map((r) => Number(r.avg_output || 0));

    const ctx = $canvasHr[0].getContext("2d");
    $canvasHr[0]._chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { type: "bar",  label: "Output (Qty)", data: output,
            backgroundColor: COLORS.output, borderColor: COLORS.output, borderWidth: 1 },
          { type: "line", label: "Target (Qty)", data: target,
            borderColor: COLORS.target, backgroundColor: "transparent",
            borderWidth: 2, pointRadius: 2, tension: 0.25 },
          { type: "line", label: "Avg Output", data: avg,
            borderColor: COLORS.avg, backgroundColor: "transparent",
            borderWidth: 2, pointRadius: 2, tension: 0.25 },
        ],
      },
      options: {
        responsive: true,
		maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "bottom", align: "center", labels: { boxWidth: 12, padding: 12 } },
          title:  { display: true, text: "Flow Rate — hourly" },
          tooltip: {
            callbacks: { label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.y ?? 0).toLocaleString()}` },
          },
        },
        scales: {
          x: {
            title: { display: true, text: "Hour (HH:00)" },
            ticks: { autoSkip: true, maxTicksLimit: 24 }, // fine here
          },
          y: { title: { display: true, text: "Quantity" }, beginAtZero: true },
        },
      },
    });
  }

  function debounce(fn, wait = 250) {
    let t;
    return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); };
  }
  const runTen = debounce(renderTen, 250);
  const runHr  = debounce(renderHr, 250);

  // ---------- Bindings ----------
  fDate.$input && fDate.$input.on("change", () => { runTen(); runHr(); });

  function bindMultiSelect(ms) {
    if (!ms) return;
    ms.$input && ms.$input.on("input change awesomplete-selectcomplete", () => { runTen(); runHr(); });
    $(ms.$wrapper).on("click", ".amp-token-remove,.awesomplete .remove", () => { runTen(); runHr(); });
    const host = ms.$wrapper.find(".control-input, .control-input-wrapper")[0] || ms.$wrapper[0];
    if (host) {
      const obs = new MutationObserver(() => { runTen(); runHr(); });
      obs.observe(host, { childList: true, subtree: true });
      ms._obs = obs;
    }
    if (typeof ms.on_change === "function") {
      const prev = ms.on_change.bind(ms);
      ms.on_change = (...a) => { try { prev(...a); } catch {} runTen(); runHr(); };
    } else {
      ms.on_change = () => { runTen(); runHr(); };
    }
  }
  bindMultiSelect(msCell);
  bindMultiSelect(msOp);

  // ---------- Initial renders ----------
  renderTen();
  renderHr();
};
