/* @ts-nocheck */
// Viewer: Flow Rate (10-min & Hourly)
// Route: /app/flow-rate-viewer

frappe.pages['flow-rate-viewer'] = {
	on_page_load(wrapper) {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: 'Flow Rate', single_column: true });
		const $root = $(wrapper).find('.layout-main-section');

		// ---------- CONFIG ----------
		const DOCTYPES = { physical_cell: 'Physical Cell', operation: 'Operation' };
		const APPLY_COMPANY_FILTER = true; // only if DocType actually has a "company" field
		const COLORS = { output: '#96BE37', target: '#ECAD4B', avg: '#000000' };
		const REPORT_NAME = 'Flow Rate';

		// ---------- Meta: detect doctypes with company field ----------
		const DT_META = {
			physical_cell: { doctype: DOCTYPES.physical_cell, hasCompany: false },
			operation: { doctype: DOCTYPES.operation, hasCompany: false },
		};
		(async () => {
			for (const key of Object.keys(DT_META)) {
				try {
					await frappe.model.with_doctype(DT_META[key].doctype);
					DT_META[key].hasCompany = !!frappe.meta.get_docfield(DT_META[key].doctype, 'company', null);
				} catch { DT_META[key].hasCompany = false; }
			}
		})();

		// ---------- Controls ----------
		const fDate = page.add_field({ fieldtype: 'Date', fieldname: 'date', label: 'Date', default: frappe.datetime.get_today(), reqd: 1 });

		const msCell = page.add_field({
			fieldtype: 'MultiSelectList', fieldname: 'physical_cell_list', label: 'Physical Cell',
			get_data: async function (txt) {
				const hasCompany = DT_META.physical_cell.hasCompany; const filters = {};
				if (APPLY_COMPANY_FILTER && hasCompany) { const company = frappe.defaults.get_default('Company'); if (company) filters.company = company; }
				return frappe.db.get_link_options(DOCTYPES.physical_cell, txt, filters);
			}
		});

		const msOp = page.add_field({
			fieldtype: 'MultiSelectList', fieldname: 'operation_list', label: 'Operation',
			get_data: async function (txt) {
				const hasCompany = DT_META.operation.hasCompany; const filters = {};
				if (APPLY_COMPANY_FILTER && hasCompany) { const company = frappe.defaults.get_default('Company'); if (company) filters.company = company; }
				return frappe.db.get_link_options(DOCTYPES.operation, txt, filters);
			}
		});

		// Layout
		const $grid = $(`
		<div class="kpi-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;margin-top:12px;">
			<div class="kpi-card" style="border:1px solid var(--border-color,#e5e7eb);border-radius:8px;padding:12px;background:#fff;">
			<h6 style="margin:0 0 6px 0;color:var(--text-muted,#6b7280);font-weight:600;">10-min Flow Rate — selected day</h6>
			<canvas id="chart10"></canvas>
			</div>
			<div class="kpi-card" style="border:1px solid var(--border-color,#e5e7eb);border-radius:8px;padding:12px;background:#fff;">
			<h6 style="margin:0 0 6px 0;color:var(--text-muted,#6b7280);font-weight:600;">Hourly Flow Rate — selected day</h6>
			<canvas id="chartHr"></canvas>
			</div>
		</div>
		`).appendTo($root);


		const $c10 = $grid.find('#chart10');
		const $chr = $grid.find('#chartHr');

		// ---------- Utils ----------
		function loadChartJs() {
			return new Promise((resolve, reject) => {
				if (window.Chart) return resolve();
				frappe.require('https://cdn.jsdelivr.net/npm/chart.js', resolve);
				setTimeout(() => !window.Chart && reject(new Error('Chart.js failed to load')), 5000);
			});
		}

		function normalizeMS(val) {
			if (!val) return []; if (!Array.isArray(val)) return [];
			return val.map(x => (typeof x === 'string' ? x : (x && (x.value || x.label)) || '')).filter(Boolean);
		}

		function getSharedCsvFilters() {
			const cells = normalizeMS(msCell.get_value ? msCell.get_value() : []);
			const ops = normalizeMS(msOp.get_value ? msOp.get_value() : []);
			return { physical_cell_csv: cells.join(','), operation_csv: ops.join(',') };
		}

		async function fetchData() {
			const date = fDate.get_value();
			if (!date) { frappe.msgprint('Please select a Date.'); return null; }
			const shared = getSharedCsvFilters();
			const resp = await frappe.call({ method: 'frappe.desk.query_report.run', args: { report_name: REPORT_NAME, filters: { date, ...shared } } });
			return ((resp || {}).message || {}).result || [];
		}

		function splitLevels(rows) {
			const ten = rows.filter(r => (r.level || '').toLowerCase() === 'ten_min');
			const hr = rows.filter(r => (r.level || '').toLowerCase() === 'hour');
			return { ten, hr };
		}

		async function renderCharts() {
			const rows = await fetchData();
			if (!rows) return;
			const { ten, hr } = splitLevels(rows);

			await loadChartJs();
			if ($c10[0]._chart) $c10[0]._chart.destroy();
			if ($chr[0]._chart) $chr[0]._chart.destroy();

			// --- 10-min chart ---
			const labels10 = ten.map(r => r.label || '');
			const out10 = ten.map(r => Number(r.output || 0));
			const tgt10 = ten.map(r => Number(r.target || 0));
			const avg10 = ten.map(r => Number(r.avg_output || 0));

			$c10[0]._chart = new Chart($c10[0].getContext('2d'), {
				type: 'bar',
				data: {
					labels: labels10,
					datasets: [
						{ type: 'bar', label: 'Output (Qty)', data: out10, backgroundColor: COLORS.output, borderColor: COLORS.output, borderWidth: 1 },
						{ type: 'line', label: 'Target (Qty)', data: tgt10, borderColor: COLORS.target, backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.25 },
						{ type: 'line', label: 'Avg Output', data: avg10, borderColor: COLORS.avg, backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.25 },
					]
				},
				options: {
					responsive: true,
					interaction: { mode: 'index', intersect: false },
					plugins: {
						legend: { position: 'bottom', align: 'center', labels: { boxWidth: 12, padding: 12 } },
						title: { display: true, text: 'Flow Rate — every 10 minutes' },
						tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.y ?? 0).toLocaleString()}` } }
					},
					scales: {
						x: { title: { display: true, text: 'Time (10-min bins)' }, ticks: { autoSkip: true, maxTicksLimit: 24 } },
						y: { title: { display: true, text: 'Quantity' }, beginAtZero: true }
					}
				}
			});

			// --- Hourly chart ---
			const labelsH = hr.map(r => r.label || '');
			const outH = hr.map(r => Number(r.output || 0));
			const tgtH = hr.map(r => Number(r.target || 0));
			const avgH = hr.map(r => Number(r.avg_output || 0));

			$chr[0]._chart = new Chart($chr[0].getContext('2d'), {
				type: 'bar',
				data: {
					labels: labelsH,
					datasets: [
						{ type: 'bar', label: 'Output (Qty)', data: outH, backgroundColor: COLORS.output, borderColor: COLORS.output, borderWidth: 1 },
						{ type: 'line', label: 'Target (Qty)', data: tgtH, borderColor: COLORS.target, backgroundColor: 'transparent', borderWidth: 2, pointRadius: 2, tension: 0.25 },
						{ type: 'line', label: 'Avg Output', data: avgH, borderColor: COLORS.avg, backgroundColor: 'transparent', borderWidth: 2, pointRadius: 2, tension: 0.25 },
					]
				},
				options: {
					responsive: true,
					interaction: { mode: 'index', intersect: false },
					plugins: {
						legend: { position: 'bottom', align: 'center', labels: { boxWidth: 12, padding: 12 } },
						title: { display: true, text: 'Flow Rate — hourly' },
						tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.y ?? 0).toLocaleString()}` } }
					},
					scales: {
						x: { title: { display: true, text: 'Hour (HH:00)' }, ticks: { autoSkip: true, maxTicksLimit: 24 } },
						y: { title: { display: true, text: 'Quantity' }, beginAtZero: true }
					}
				}
			});
		}

		function debounce(fn, wait = 250) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); }; }
		const rerender = debounce(renderCharts, 250);

		// Bindings
		fDate.$input && fDate.$input.on('change', rerender);
		function bindMS(ms) {
			if (!ms) return;
			ms.$input && ms.$input.on('input change awesomplete-selectcomplete', rerender);
			$(ms.$wrapper).on('click', '.amp-token-remove,.awesomplete .remove', rerender);
			const host = ms.$wrapper.find('.control-input, .control-input-wrapper')[0] || ms.$wrapper[0];
			if (host) { const obs = new MutationObserver(rerender); obs.observe(host, { childList: true, subtree: true }); ms._obs = obs; }
		}
		bindMS(msCell); bindMS(msOp);

		// First render
		renderCharts();
	}
};
