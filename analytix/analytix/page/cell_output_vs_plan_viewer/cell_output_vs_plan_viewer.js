// Viewer: Cell Output vs Plan
// Route: /app/cell-output-vs-plan-viewer

frappe.pages["cell-output-vs-plan-viewer"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Cell Output vs Plan",
    single_column: true,
  });

  const $root = $(wrapper).find(".layout-main-section");

  // 👇 Breadcrumb
  $(`
    <div class="breadcrumb-bar" style="
      padding: 8px 16px;
      background: #f9fafb;
      border-bottom: 1px solid #e5e7eb;
      font-size: 14px;
      margin-bottom: 16px;
    ">
      <a href="/app/kpi-hub" style="color: #1f2937; text-decoration: none;">KPI Hub</a>
      <span style="margin: 0 8px;">></span>
      <span style="color: #6b7280;">Cell Output vs Plan</span>
    </div>
  `).prependTo($root);

  // ---------- CONFIG ----------
  const REPORT_NAME = "Cell Output vs Plan";
  const MAX_RANGE_DAYS = 45;
  const COLORS = { output: "#96BE37", target: "#ECAD4B" };

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
    reqd: 1,
    get_data: (txt) => frappe.db.get_link_options("Physical Cell", txt),
  });

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

  // ---------- Styling ----------
  $("#cell-output-vs-plan-styles").remove();
  $(`<style id="cell-output-vs-plan-styles">
    .kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px; }
    @media (max-width: 1100px) { .kpi-grid { grid-template-columns: 1fr; } }
    .kpi-card { border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; background: #fff; }
    .kpi-card h6 { margin: 0 0 6px; color: var(--text-muted); font-weight: 600; }
    .kpi-card canvas { width: 100%; height: 420px; max-height: 420px; }
    .page-form .frappe-control { min-width: 0; }
    .frappe-control[data-fieldname="date"] .control-input-wrapper { position: relative; }
    .frappe-control[data-fieldname="date"] input { padding-right: 26px !important; }
    .frappe-control[data-fieldname="date"] .kpi-clear-btn {
      position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
      background: transparent; border: 0; color: var(--gray-600); cursor: pointer;
    }
  </style>`).appendTo(document.head);

  // Clear button for date
  const $dateWrapper = fDate.$wrapper.find(".control-input-wrapper").first() || fDate.$wrapper;
  $(`<button class="kpi-clear-btn" title="Clear">×</button>`)
    .appendTo($dateWrapper)
    .on("click", (e) => {
      e.preventDefault();
      fDate.set_value("");
      fDate.$input?.val("").trigger("change");
    });

  // ---------- Charts ----------
  const $grid = $(`
    <div class="kpi-grid">
      <div class="kpi-card"><h6>Hourly Output — Selected Day</h6><canvas id="chartHourly"></canvas></div>
      <div class="kpi-card"><h6>Daily Output — Date Range</h6><canvas id="chartDaily"></canvas></div>
    </div>
  `).appendTo($root);

  // ---------- Utils ----------
  function loadChartJs() {
    return new Promise((resolve, reject) => {
      if (window.Chart) return resolve();
      frappe.require("https://cdn.jsdelivr.net/npm/chart.js", resolve);
      setTimeout(() => reject(new Error("Chart.js failed to load")), 5000);
    });
  }

  function fmtDMY(iso) {
    if (!iso) return iso;
    const [y, m, d] = iso.split("-");
    return `${d}-${m}-${y}`;
  }

  function normalizeMS(val) {
    if (!val) return [];
    if (!Array.isArray(val)) return [];
    return val.map(x => (typeof x === "string" ? x : (x?.value || x?.label)) || "").filter(Boolean);
  }

  function getFilters() {
    const cells = normalizeMS(msCell.get_value?.());
    return {
      date: fDate.get_value(),
      physical_cell_csv: cells.join(","),
    };
  }

  function enumerateDates(from, to) {
    const dates = [];
    if (!from || !to) return dates;
    const start = new Date(from);
    const end = new Date(to);
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      dates.push(frappe.datetime.str_to_user(frappe.datetime.obj_to_str(d)));
    }
    return dates;
  }

  const debounce = (fn, wait = 300) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  };

  // ---------- Renderers ----------
  async function renderHourly() {
    const filters = getFilters();
    if (!filters.date || !filters.physical_cell_csv) return;

    try {
      const res = await frappe.call({
        method: "frappe.desk.query_report.run",
        args: { report_name: REPORT_NAME, filters },
      });

      const rows = res.message?.result || [];
      const labels = rows.map(r => r.hour_label || "");
      const output = rows.map(r => parseFloat(r.output) || 0);
      const target = rows.map(r => parseFloat(r.target) || 0);

      await loadChartJs();
      const ctx = document.getElementById("chartHourly").getContext("2d");
      if (ctx.canvas._chart) ctx.canvas._chart.destroy();

      ctx.canvas._chart = new Chart(ctx, {
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
              borderWidth: 1,
            },
            {
              type: "line",
              label: "Plan (Qty)",
              data: target,
              borderColor: COLORS.target,
              backgroundColor: "transparent",
              borderWidth: 2,
              pointRadius: 2,
              tension: 0.25,
            },
          ],
        },
        options: {
          responsive: true,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "bottom" },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.y || 0).toLocaleString()}`,
              },
            },
          },
          scales: {
            x: { title: { display: true, text: "Hour" } },
            y: { beginAtZero: true, title: { display: true, text: "Quantity" } },
          },
        },
      });
    } catch (e) {
      console.error(e);
      frappe.msgprint({ title: "Error", message: e.message || "Failed to load hourly data", indicator: "red" });
    }
  }

  async function renderDaily() {
    const from = fFrom.get_value();
    const to = fTo.get_value();
    const cells = normalizeMS(msCell.get_value?.());
    if (!from || !to || !cells.length) return;

    const days = frappe.datetime.get_day_diff(to, from) + 1;
    if (days > MAX_RANGE_DAYS) {
      frappe.msgprint(`Date range must be ≤ ${MAX_RANGE_DAYS} days.`);
      return;
    }

    try {
      const dates = enumerateDates(from, to);
      const calls = dates.map(date =>
        frappe.call({
          method: "frappe.desk.query_report.run",
          args: {
            report_name: REPORT_NAME,
            filters: { date, physical_cell_csv: cells.join(",") },
          },
        })
      );

      const results = await Promise.all(calls);

      const labels = [];
      const output = [];
      const target = [];

      results.forEach((res, i) => {
        const rows = res.message?.result || [];
        const out = rows.reduce((sum, r) => sum + (parseFloat(r.output) || 0), 0);
        const tgt = rows.reduce((sum, r) => sum + (parseFloat(r.target) || 0), 0);
        labels.push(fmtDMY(dates[i]));
        output.push(out);
        target.push(tgt);
      });

      await loadChartJs();
      const ctx = document.getElementById("chartDaily").getContext("2d");
      if (ctx.canvas._chart) ctx.canvas._chart.destroy();

      ctx.canvas._chart = new Chart(ctx, {
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
              borderWidth: 1,
            },
            {
              type: "line",
              label: "Plan (Qty)",
              data: target,
              borderColor: COLORS.target,
              backgroundColor: "transparent",
              borderWidth: 2,
              pointRadius: 2,
              tension: 0.25,
            },
          ],
        },
        options: {
          responsive: true,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "bottom" },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.y || 0).toLocaleString()}`,
              },
            },
          },
          scales: {
            x: { title: { display: true, text: "Date (dd-mm-yyyy)" } },
            y: { beginAtZero: true, title: { display: true, text: "Quantity" } },
          },
        },
      });
    } catch (e) {
      console.error(e);
      frappe.msgprint({ title: "Error", message: e.message || "Failed to load daily data", indicator: "red" });
    }
  }

  // ---------- Bindings ----------
  const debouncedHourly = debounce(renderHourly, 300);
  const debouncedDaily = debounce(renderDaily, 300);

  fDate.$input?.on("change", debouncedHourly);
  fFrom.$input?.on("change", debouncedDaily);
  fTo.$input?.on("change", debouncedDaily);

  // Physical Cell changes affect both charts
  function bindCell() {
    msCell.$input?.on("change input awesomplete-selectcomplete", () => {
      debouncedHourly();
      debouncedDaily();
    });
    $(msCell.$wrapper).on("click", ".remove, .amp-token-remove", () => {
      debouncedHourly();
      debouncedDaily();
    });
  }
  bindCell();

  // Initial load
  renderHourly();
  renderDaily();
};