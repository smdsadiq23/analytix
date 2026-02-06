// Copyright (c) 2026 Your Company
// Enables inline editing of Remarks field in report

// Copyright (c) 2026 Your Company
// Enables inline editing of Remarks field in report

frappe.query_reports["Gate Inward vs GRN"] = {
	onload: function (report) {
		report.page.add_inner_button(
			__("Refresh"),
			function () {
				report.refresh();
			},
			__("Actions"),
		);
	},

	formatter: function (value, row, column, data, default_formatter) {
		// Make Remarks field editable only when GRN exists
		if (column.fieldname === "remarks" && data.purchase_receipt) {
			const safe_value = frappe.utils.escape_html(value || "");

			return `
                <div class="editable-remarks-container"
                    data-pr-name="${data.purchase_receipt}"
                    data-original-value="${safe_value}"
                    style="min-height:24px; padding:3px; cursor:text;
                           border-radius:3px; background-color:#f8f9fa;">
                    ${safe_value || '<span class="text-muted">Click to add remarks</span>'}
                </div>
            `;
		}

		return default_formatter(value, row, column, data);
	},

	onrender: function (report) {
		// Attach click-to-edit behavior (safe rebind)
		$(report.wrapper)
			.off("click", ".editable-remarks-container")
			.on("click", ".editable-remarks-container", function (e) {
				const $container = $(this);

				// Prevent re-entering edit mode
				if ($container.find("input").length) return;

				const pr_name = $container.data("pr-name");
				const current_value = $container.data("original-value") || "";

				// Switch to input
				$container.html(`
                    <input type="text"
                        class="editable-remarks-input form-control"
                        value="${frappe.utils.escape_html(current_value)}"
                        style="min-width:150px; padding:2px 4px; height:24px;">
                `);

				const $input = $container.find("input");
				$input.focus().select();

				// Save on blur or Enter
				$input
					.on("blur", function () {
						save_remarks($container, pr_name, $(this).val());
					})
					.on("keydown", function (e) {
						if (e.key === "Enter") {
							e.preventDefault();
							$(this).blur();
						}

						if (e.key === "Escape") {
							const safe_original = frappe.utils.escape_html(current_value || "");
							$container.html(
								safe_original ||
									'<span class="text-muted">Click to add remarks</span>',
							);
						}
					});
			});
	},
};

// --------------------------------------------------------
// SAVE FUNCTION
// --------------------------------------------------------
function save_remarks($container, pr_name, new_value) {
	new_value = (new_value || "").trim();

	const original_value = $container.data("original-value") || "";

	// No change → restore text
	if (new_value === original_value) {
		const safe_value = frappe.utils.escape_html(new_value);
		$container.html(safe_value || '<span class="text-muted">Click to add remarks</span>');
		return;
	}

	// Saving indicator
	$container.html('<span class="text-muted">Saving...</span>');

	frappe.call({
		method: "frappe.client.set_value",
		args: {
			doctype: "Purchase Receipt",
			name: pr_name,
			fieldname: "remarks",
			value: new_value,
		},
		callback: function (r) {
			if (r.message) {
				$container.data("original-value", new_value);

				const safe_value = frappe.utils.escape_html(new_value);
				$container.html(
					safe_value || '<span class="text-muted">Click to add remarks</span>',
				);

				frappe.show_alert({
					message: __("Remarks updated"),
					indicator: "green",
				});
			} else {
				restore_original($container, original_value);
			}
		},
		error: function () {
			restore_original($container, original_value);
		},
	});
}

// --------------------------------------------------------
// RESTORE ORIGINAL VALUE
// --------------------------------------------------------
function restore_original($container, original_value) {
	const safe_original = frappe.utils.escape_html(original_value || "");
	$container.html(safe_original || '<span class="text-muted">Click to add remarks</span>');

	frappe.show_alert({
		message: __("Failed to update remarks"),
		indicator: "red",
	});
}
