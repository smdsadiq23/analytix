// Viewer: Output vs Target (multi-select fixed, robust normalization, wrapped pills)
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
    physical_cell: "Physical Cell",
    operation: "Operation",
  };
  const APPLY_COMPANY_FILTER = true; // only if DocType has `company`
  const COLORS = { output: "#96BE37", target: "#ECAD4B" };

  // ---------- Meta detector (DocTypes that actually have "company") ----------
  const DT_META = {
    physical_cell: { doctype: DOCTYPES.physical_cell, hasCompany: false },
    operation:     { doctype: DOCTYPES.operation,     hasCompany: false },
  };
  (async () => {
    for (const key of Object.keys(DT_META)) {
      const dt = DT_META[key].doctype;
      try {
        await frappe.model.with_doctype(dt);
        DT_META[key].hasCompany = !!frappe.meta.get_docfield(dt, "company", null);
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

  // Optional: "Open Report" link
  const $tools = $(`
    <div class="d-flex align-items-center" style="gap:8px; margin:8px 0 12px;">
      <a class="btn btn-default btn-sm" data-action="open-report" href="javascript:void(0)">Open Report</a>
    </div>
  `).appendTo($root);

  // ---- Clear buttons + token wrapping CSS ----
  $(`<style>
    .kpi-clear-parent{ position:relative }
    .kpi-clear-pad input{ padding-right:22px }
    .kpi-clear-btn{
      position:absolute; right:6px; top:50%; transform:translateY(-50%);
      border:0; background:transparent; line-height:1; padding:0 6px;
      color:var(--gray-600); cursor:pointer; border-radius:6px; z-index:2;
    }
    .kpi-clear-btn:hover{ background:var(--gray-100) }

    /* Robust MultiSelectList wrapping across Frappe variants */
    .kpi-ms .control-input, .kpi-ms .control-input-wrapper { display:flex; flex-wrap:wrap; align-items:center; }
    .kpi-ms .awesomplete { flex: 1 1 180px; min-width:180px; }

    /* Common token selectors */
    .kpi-ms .amp-token,
    .kpi-ms .awesomplete .token,
    .kpi-ms .selected-pill,
    .kpi-ms .selected-item {
      margin: 2px 6px 2px 0; max-width:100%;
    }

    /* Inner text nodes—truncate long labels */
    .kpi-ms .amp-token span,
    .kpi-ms .awesomplete .token span,
    .kpi-ms .selected-pill span,
    .kpi-ms .selected-item span,
    .kpi-ms .amp-token .label,
    .kpi-ms .selected-pill .label {
      display:inline-block; max-width:260px;
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
      vertical-align:bottom;
    }
  </style>`).appendTo(document.head);

  msCell.$wrapper.addClass("kpi-ms");
  msOp.$wrapper.addClass("kpi-ms");

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
            try { control.set_value && control.set_value([]); } catch {}
          } else {
            try { control.set_value && control.set_value(""); } catch {}
            try { control.set_input && control.set_input(""); } catch {}
            try { control.$input && control.$input.val(""); } catch {}
          }
          control.$input && control.$input.trigger("input").trigger("change");
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
    control.$input && control.$input.on("input change blur awesomplete-selectcomplete", toggle);
    setTimeout(toggle, 0);
  }
  addClearAll(fDate,  "date", false);
  addClearAll(msCell, "physical_cell_list", true);
  addClearAll(msOp,   "operation_list", true);

  // ---------- Prefill from URL ----------
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

  // ---------- Normalize & gather filters ----------
  function normalizeMS(val) {
    // Accept: CSV string, array of strings, array of {value|label|name|id}
    if (!val) return [];
    if (typeof val === "string") {
      return val.split(",").map(s => s && s.trim()).filter(Boolean);
    }
    if (!Array.isArray(val)) return [];
    return val.map(x => {
      if (typeof x === "string") return x;
      if (x && typeof x === "object") {
        return x.value || x.label || x.name || x.id || "";
      }
      return "";
    }).filter(Boolean);
  }

  function getFilters() {
    const cells = normalizeMS(msCell.get_value ? msCell.get_value() : []);
    const ops   = normalizeMS(msOp.get_value   ? msOp.get_value()   : []);
    return {
      date: fDate.get_value(),
      physical_cell_csv: cells.join(","),
      operation_csv:     ops.join(","),
    };
  }

  const keyOf = (f) => [f.date || "", f.physical_cell_csv || "", f.operation_csv || ""].join("|");
  let lastKey = "";

  function debounce(fn, wait = 250) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); };
  }

  // ---------- Fetch + chart ----------
  async function run() {
    const filters = getFilters();
    const key = keyOf(filters);
    if (!filters.date) { frappe.msgprint("Please select a Date."); return; }
    if (key === lastKey) return;
    lastKey = key;

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
            legend: { position: "top" },
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
      frappe.msgprint({ title: "Chart", message: e.message || e, indicator: "red" });
    }
  }

  const runDebounced = debounce(run, 250);

  // ---------- Auto-run bindings ----------
  fDate.$input && fDate.$input.on("change", runDebounced);

  function bindMultiSelect(ms) {
    if (!ms) return;
    // fire only when a real selection/pill happens
    ms.$input && ms.$input.on("awesomplete-selectcomplete change", runDebounced);
    $(ms.$wrapper).on("click", ".amp-token-remove,.awesomplete .remove,.selected-pill .remove", runDebounced);

    // observe token changes (covers programmatic set_value and pill layout changes)
    const host = ms.$wrapper.find(".control-input, .control-input-wrapper")[0] || ms.$wrapper[0];
    if (host) {
      const obs = new MutationObserver(() => runDebounced());
      obs.observe(host, { childList: true, subtree: true });
      ms._obs = obs;
    }
    // control-level on_change, if present
    if (typeof ms.on_change === "function") {
      const prev = ms.on_change.bind(ms);
      ms.on_change = (...a) => { try { prev(...a); } catch {} runDebounced(); };
    } else {
      ms.on_change = runDebounced;
    }
  }
  bindMultiSelect(msCell);
  bindMultiSelect(msOp);

  // ---------- Open Report with same filters ----------
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
