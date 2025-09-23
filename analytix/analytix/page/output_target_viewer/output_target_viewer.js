frappe.pages['output-target-viewer'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Output vs Target',
    single_column: true
  });
  const $root = $(wrapper).find('.layout-main-section');

  // controls
  const $controls = $(`
    <div class="d-flex align-items-center" style="gap:8px; margin:12px 0;">
      <input type="date" class="form-control" style="max-width:200px;">
      <input type="text" class="form-control" placeholder="Physical Cell" style="max-width:200px;">
      <input type="text" class="form-control" placeholder="Operation" style="max-width:200px;">
      <button class="btn btn-default btn-sm">Run</button>
    </div>
  `).appendTo($root);
  const $date = $controls.find('input[type="date"]').val(frappe.datetime.get_today());
  const [$cell, $op] = [$controls.find('input').eq(1), $controls.find('input').eq(2)];
  const $btn = $controls.find('button');

  const $canvas = $(`<canvas style="max-height:520px;"></canvas>`).appendTo($root);

  // load Chart.js on demand
  function loadChartJs() {
    return new Promise((resolve, reject) => {
      if (window.Chart) return resolve();
      frappe.require('https://cdn.jsdelivr.net/npm/chart.js', resolve);
      setTimeout(() => !window.Chart && reject(new Error('Chart.js failed to load')), 4000);
    });
  }

  async function run() {
    $btn.prop('disabled', true);
    try {
      const r = await frappe.call({
        method: 'frappe.desk.query_report.run',
        args: {
          report_name: 'Output vs Target',
          filters: {
            date: $date.val(),
            physical_cell: $cell.val() || null,
            operation: $op.val() || null
          }
        }
      });
      const rows = (r.message || {}).result || [];
      const labels = rows.map(x => x.hour_label || ''); 
      const output = rows.map(x => Number(x.output || 0));
      const target = rows.map(x => Number(x.target || 0));

      await loadChartJs();

      // destroy old chart
      if ($canvas[0]._chart) { $canvas[0]._chart.destroy(); }

      const ctx = $canvas[0].getContext('2d');
      $canvas[0]._chart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            { type: 'bar',  label: 'Output', data: output },
            { type: 'line', label: 'Target', data: target }
          ]
        },
        options: {
          responsive: true,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { position: 'top' },
            title: { display: true, text: 'Output vs Target' }
          },
          scales: {
            x: {
              title: { display: true, text: 'Time (HH:00)' },
              ticks: { autoSkip: true, maxTicksLimit: 24 }
            },
            y: {
              title: { display: true, text: 'Quantity' },
              beginAtZero: true
            }
          }
        }
      });
    } catch (e) {
      frappe.msgprint({ title: 'Chart', message: e.message || e, indicator: 'red' });
    } finally {
      $btn.prop('disabled', false);
    }
  }

  $btn.on('click', run);
  run();
};
