// Viewer: Output vs Target (with multi-select & safe company filter)
// Route: /app/output-target-viewer

frappe.pages["output-target-viewer"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Output vs Target",
    single_column: true,
  });
  const $root = $(wrapper).find(".layout-main-section");

  // ---------- CONFIG ----------
  const DOCTYPES = {
    physical_cell: "Physical Cell", // change if needed
    operation: "Operation",
  };
  const APPLY_COMPANY_FILTER = true; // will only apply if doctype actually has "company" field
  const COLORS = {
    output: "#96BE37", // bar
    target: "#ECAD4B", // line
  };

  // ---------- Meta detector (doctypes that actually have "company") ----------
  const DT_META = {
    physical_cell: { doctype: DOCTYPES.physical_cell, hasCompany: false },
    operation:     { doctype: DOCTYPES.operation,     hasCompany: false },
  };

  async function detectCompanyFields() {
    for (const key of Object.keys(DT_META)) {
      const dt = DT_META[key].doctype;
      try {
        await frappe.model.with_doctype(dt);
        DT_META[key].hasCompany = !!frappe.meta.get_docfield(dt, "company", null);
      } catch {
        DT_META[key].hasCompany = false;
      }
    }
  }
  // kick it off (no need to await here; get_data checks flags at call time)
  detectCompanyFields();

  // ---------- Controls ----------
  const fDate = page.add_field({
    fieldtype: "Date",
    fieldname: "date",
    label: "Date",
    default: frappe.datetime.get_today(),
    reqd: 1,
  });

  // MultiSelectList — Physical Cell
  const msCell = page.add_field({
    fieldtype: "MultiSelectList",
    fieldname: "physical_cell_list",
    label: "Physical Cell",
    reqd: 0,
    get_data: async function (txt) {
      // apply company filter only if the doctype has a "company" field
      const hasCompany = DT_META.physical_cell.hasCompany;
      const filters = {};
      if (APPLY_COMPANY_FILTER && hasCompany) {
        const company = frappe.defaults.get_default("Company");
        if (company) filters.company = company;
      }
      return frappe.db.get_link_options(DOCTYPES.physical_cell, txt, filters);
    },
  });

  // MultiSelectList — Operation
  const msOp = page.add_field({
    fieldtype: "MultiSelectList",
    fieldname: "operation_list",
    label: "Operation",
    reqd: 0,
    get_data: async function (txt) {
      const hasCompany = DT_META.operation.hasCompany;
      const filters = {};
      if (APPLY_COMPANY_FILTER && hasCompany) {
        const company = frappe.defaults.get_default("Company");
        if (company) filters.company = company;
      }
      return frappe.db.get_link_options(DOCTYPES.operation, txt, filters);
    },
  });

  // Optional: "Open Report" link
  const $tools = $(`
    <div class="d-flex align-items-center" style="gap:8px; margin:8px 0 12px;">
      <a class="btn btn-default btn-sm" data-action="open-report" href="javascript:void(0)">Open Report</a>
    </div>
  `).appendTo($root);

  // ---- Clear-all buttons for each control (Date + MultiSelects) ----
  $(`<style>
    .kpi-clear-parent{ position:relative }
    .kpi-clear-pad input{ padding-right:22px }
    .kpi-clear-btn{
      position:absolute; right:6px; top:50%; transform:translateY(-50%);
      border:0; background:transparent; line-height:1; padding:0 6px;
      color:var(--gray-600); cursor:pointer; border-radius:6px; z-index:2;
    }
    .kpi-clear-btn:hover{ background:var(--gray-100) }
  </style>`).appendTo(document.head);

  function addClearAll(control, fieldname, isMulti=false){
    const $host = control.$wrapper.find(".control-input, .control-input-wrapper").first().length
      ? control.$wrapper.find(".control-input, .control-input-wrapper").first()
      : control.$wrapper;
    $host.addClass("kpi-clear-parent kpi-clear-pad");

    let $btn = $host.find(`.kpi-clear-btn[data-for="${fieldname}"]`);
    if (!$btn.length) {
      $btn = $(`<button type="button" class="kpi-clear-btn" data-for="${fieldname}" title="Clear">×</button>`)
        .appendTo($host)
        .on("click", (e)=>{
          e.preventDefault(); e.stopPropagation();
          if (isMulti) {
            control.set_value && control.set_value([]);
          } else {
            control.set_value && control.set_value("");
          }
          control.$input && control.$input.trigger("input").trigger("change"); // refresh
          toggle();
        });
    }

    const hasVal = ()=>{
      try {
        const v = control.get_value ? control.get_value() : null;
        return isMulti ? (Array.isArray(v) && v.length>0) : !!(v && String(v).trim());
      } catch { return false; }
    };
    const toggle = ()=> $btn.toggle(hasVal());

    control.$input && control.$input.on("input change awesomplete-selectcomplete", toggle);
    toggle();
  }
  addClearAll(fDate,  "date", false);
  addClearAll(msCell, "physical_cell_list", true);
  addClearAll(msOp,   "operation_list", true);

  // ---------- Prefill from URL (?physical_cell=A,B&operation=X,Y) ----------
  const qp = frappe.utils.get_query_params();
  if (qp.date) fDate.set_value(qp.date);
  if (qp.physical_cell) msCell.set_value(qp.physical_cell.split(",").filter(Boolean));
  if (qp.operation)     msOp.set_value(qp.operation.split(",").filter(Boolean));

  // ---------- Canvas ----------
  const $canvas = $(`<canvas style="max-height:520px;"></canvas>`).appendTo($root);

  function loadChartJs() {
    return new Promise((resolve, reject) => {
      if (window.Chart) return resolve();
      frappe.require("https://cdn.jsdelivr.net/npm/chart.js", resolve);
      setTimeout(() => !window.Chart && reject(new Error("Chart.js failed to load")), 4000);
    });
  }

  // ---------- Collect filters (send CSV for multi-selects) ----------
  function getFilters() {
    const cells = msCell.get_value ? msCell.get_value() : [];
    const ops   = msOp.get_value ? msOp.get_value() : [];
    return {
      date: fDate.get_value(),
      physical_cell_csv: (cells || []).join(","),
      operation_csv:     (ops   || []).join(","),
    };
  }

  function debounce(fn, wait = 250) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); };
  }

  // ---------- Fetch + chart ----------
  async function run() {
    const filters = getFilters();
    if (!filters.date) { frappe.msgprint("Please select a Date."); return; }

    try {
      const resp = await frappe.call({
        method: "frappe.desk.query_report.run",
        args: { report_name: "Output vs Target", filters },
      });

      const result = (resp.message || {}).result || [];
      const labels = result.map(r => r.hour_label || "");
      const output = result.map(r => Number(r.output || 0));
      const target = result.map(r => Number(r.target || 0));

      await loadChartJs();

      if ($canvas[0]._chart) $canvas[0]._chart.destroy();

      const ctx = $canvas[0].getContext("2d");
      $canvas[0]._chart = new Chart(ctx, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              type: "bar",
              label: "Output (Qty)",
              data: output,
              backgroundColor: COLORS.output,
              borderColor: COLORS.output,
              borderWidth: 1
            },
            {
              type: "line",
              label: "Target (Qty)",
              data: target,
              borderColor: COLORS.target,
              backgroundColor: COLORS.target,
              borderWidth: 2,
              pointRadius: 2,
              tension: 0.25
            }
          ]
        },
        options: {
          responsive: true,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "top" },
            title:  { display: true, text: "Output vs Target (Hourly)" },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = Number(ctx.parsed.y ?? 0);
                  const txt = Number.isFinite(v)
                    ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
                    : "0";
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
      frappe.msgprint({ title: "Chart", message: e.message || e, indicator: "red" });
    }
  }

  const runDebounced = debounce(run, 250);

  // ---------- Auto-run on filter change ----------
  fDate.$input && fDate.$input.on("change", runDebounced);
  [msCell, msOp].forEach(ms => {
    if (!ms || !ms.$input) return;
    ms.$input.on("input change awesomplete-selectcomplete", runDebounced);
    // also catch pill removes
    $(ms.$wrapper).on("click", ".amp-token-remove", runDebounced);
  });

  // ---------- Open Report with same filters (CSV in URL) ----------
  $tools.on("click", '[data-action="open-report"]', function (e) {
    e.preventDefault(); e.stopPropagation();
    const f = getFilters();
    const params = $.param({
      date: f.date || "",
      physical_cell: f.physical_cell_csv || "",
      operation: f.operation_csv || ""
    });
    const url = frappe.urllib.get_full_url(
      `/app/query-report/${encodeURIComponent("Output vs Target")}?${params}`
    );
    window.open(url, "_blank", "noopener");
  });

  // Initial render
  run();
};
