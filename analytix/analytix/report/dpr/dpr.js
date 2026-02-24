// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["DPR"] = {
	filters: [],

	onload(report) {
		CX.mountBreadcrumb({
			wrapper: report.page.wrapper || report.page.$wrapper,
			trail: [{ label: "KPI Hub", href: "/app/kpi-hub" }, { label: "DPR" }],
		});
	},

	// ✅ Freeze first 4 columns after datatable renders
	after_datatable_render(datatable) {
		const numColumnsToFreeze = 6; // ← Only change from original: 4 instead of 5
		
		const bodyScrollable = datatable.bodyScrollable;
		if (!bodyScrollable) return;

		bodyScrollable.addEventListener('scroll', (e) => {
			if (datatable._settingHeaderPosition) return;
			datatable._settingHeaderPosition = true;

			requestAnimationFrame(() => {
				const scrollLeft = e.target.scrollLeft;

				// Freeze header columns
				for (let i = 0; i < numColumnsToFreeze; i++) {
					const headerCells = $(`.dt-cell--col-${i}`, datatable.header);
					headerCells.each(function () {
						this.style.transform = `translateX(${scrollLeft}px)`;
						this.style.position = 'relative';
						this.style.zIndex = '10';
						this.style.backgroundColor = '#f5f7fa';
					});
				}

				// Freeze body row cells
				const $allRows = $(bodyScrollable).find('.dt-row');
				$allRows.each(function () {
					const $cells = $(this).find('.dt-cell');
					for (let i = 0; i < numColumnsToFreeze && i < $cells.length; i++) {
						const cell = $cells[i];
						cell.style.transform = `translateX(${scrollLeft}px)`;
						cell.style.position = 'relative';
						cell.style.zIndex = '10';
						cell.style.backgroundColor = '#ffffff';
					}
				});

				// Freeze footer/total row (if any)
				const $footer = $(datatable.wrapper).find('.dt-footer');
				if ($footer.length) {
					for (let i = 0; i < numColumnsToFreeze; i++) {
						const footerCells = $(`.dt-cell--col-${i}`, $footer);
						footerCells.each(function () {
							this.style.transform = `translateX(${scrollLeft}px)`;
							this.style.position = 'relative';
							this.style.zIndex = '10';
							this.style.backgroundColor = '#fafbfc';
						});
					}
				}

				datatable._settingHeaderPosition = false;
			});
		});
	}
};