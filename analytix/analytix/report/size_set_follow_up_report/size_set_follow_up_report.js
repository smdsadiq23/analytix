// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Size Set Follow-up Report"] = {
	onload(report) {
		CX.mountBreadcrumb({
			wrapper: report.page.wrapper || report.page.$wrapper,
			trail: [
				{ label: "KPI Hub", href: "/app/kpi-hub" },
				{ label: "Size Set Follow-up Report" }
			]
		});   

		const $wrap = report.page.wrapper;
		const STATUS_ORDER = ["Under Checking", "Awaiting Pattern", "Sewing Pending", "Completed"];

		// Helper: update dropdown options based on current value
		function updateDropdownOptions($select) {
			const currentValue = $select.val();
			const currentIndex = STATUS_ORDER.indexOf(currentValue);

			let allowedOptions = [currentValue];
			if (currentIndex !== -1 && currentIndex < STATUS_ORDER.length - 1) {
				allowedOptions.push(STATUS_ORDER[currentIndex + 1]);
			}

			const optionsHtml = allowedOptions
				.map(opt => `<option value="${opt}" ${opt === currentValue ? "selected" : ""}>${opt}</option>`)
				.join("");

			$select.html(optionsHtml);
			$select.data("old-value", currentValue); // sync old-value
		}

		const save = frappe.utils.debounce((e) => {
			const $el = $(e.currentTarget);
			const docname = $el.data("docname");
			const newValue = $el.val();
			const oldValue = $el.data("old-value");

			if (newValue === oldValue) return;

			const oldIndex = STATUS_ORDER.indexOf(oldValue);
			const newIndex = STATUS_ORDER.indexOf(newValue);

			if (oldIndex === -1 || newIndex === -1) {
				frappe.msgprint(__("Invalid status."));
				updateDropdownOptions($el); // reset to valid state
				return;
			}

			if (newIndex !== oldIndex && newIndex !== oldIndex + 1) {
				frappe.msgprint(__("You can only move to the next stage in the Size Set workflow."));
				updateDropdownOptions($el); // revert options + selection
				return;
			}

			$el.css("opacity", 0.6);
			frappe.call({
				method: "frappe.client.set_value",
				args: {
					doctype: "Sales Order",
					name: docname,
					fieldname: "custom_size_set_status",
					value: newValue
				},
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Saved"), indicator: "green" });
						// ✅ CRITICAL: Update dropdown to reflect new state
						updateDropdownOptions($el);
					} else {
						frappe.msgprint(__("Save failed"));
						// Revert to old value and update options
						$el.val(oldValue);
						updateDropdownOptions($el);
					}
				},
				always() {
					$el.css("opacity", 1);
				}
			});
		}, 600);

		$wrap.on("focus", ".report-status-select", function () {
			$(this).data("old-value", $(this).val());
		});

		$wrap.on("change", ".report-status-select", save);
	},

	formatter(value, row, column, data, default_formatter) {
		if (!data || column.fieldname !== "custom_size_set_status") {
			return default_formatter(value, row, column, data);
		}

		const currentValue = value || "Under Checking";
		const STATUS_ORDER = ["Under Checking", "Awaiting Pattern", "Sewing Pending", "Completed"];
		const currentIndex = STATUS_ORDER.indexOf(currentValue);

		let allowedOptions = [currentValue];
		if (currentIndex !== -1 && currentIndex < STATUS_ORDER.length - 1) {
			allowedOptions.push(STATUS_ORDER[currentIndex + 1]);
		}

		const options = allowedOptions
			.map(opt => `<option value="${opt}" ${opt === currentValue ? "selected" : ""}>${opt}</option>`)
			.join("");

		return `
			<select class="report-status-select"
					data-docname="${data.ocn}"
					style="width:100%; padding:4px; border-radius:4px;">
				${options}
			</select>
		`;
	}
};