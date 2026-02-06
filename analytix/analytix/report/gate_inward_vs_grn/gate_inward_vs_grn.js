// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Gate Inward vs GRN"] = {
	onload: function () {
		this.setupEditButtonHandler();
	},

	onrefresh: function () {
		this.setupEditButtonHandler();
	},

	setupEditButtonHandler: function () {
		frappe.after_ajax(() => {
			setTimeout(() => {
				const report = frappe.query_report;
				if (!report || !report.columns || !report.data) return;

				// Find button column index
				const btn_idx = report.columns.findIndex((col) => col.fieldname === "edit_btn");
				if (btn_idx === -1) return;

				// Process each row
				report.data.forEach((row, i) => {
					const $cell = report.$report.find(`.dt-row:eq(${i}) .dt-cell--col-${btn_idx}`);
					if (!$cell.length) return;

					// ONLY show button for editable rows (Draft GRN with PR linked)
					if (row.purchase_receipt && row.inward_status === "Pending") {
						$cell.html(`
                            <button class="btn btn-xs btn-primary edit-remarks-btn" 
                                    data-pr="${row.purchase_receipt}"
                                    data-current="${frappe.utils.escape_html(row.remarks || "")}"
                                    title="Edit Remarks for GRN ${row.purchase_receipt}">
                                <i class="fa fa-edit"></i> Edit
                            </button>
                        `);
					} else {
						$cell.html(""); // Clear for non-editable rows
					}
				});

				// EVENT DELEGATION for edit buttons (works for dynamically added buttons)
				report.$report
					.off("click", ".edit-remarks-btn")
					.on("click", ".edit-remarks-btn", function (e) {
						e.stopPropagation();
						const $btn = $(this);
						const pr_name = $btn.data("pr");
						const current_remarks = $btn.data("current") || "";

						// Open edit dialog
						frappe.prompt(
							{
								fieldtype: "Small Text",
								label: __("Remarks for GRN") + `: ${pr_name}`,
								fieldname: "remarks",
								default: current_remarks,
								reqd: 0,
								maxlength: 500,
							},
							// Callback on save
							function (values) {
								frappe.call({
									method: "frappe.client.set_value",
									args: {
										doctype: "Purchase Receipt",
										name: pr_name,
										fieldname: "remarks",
										value: values.remarks,
									},
									freeze: true,
									freeze_message: __("Saving remarks..."),
									callback: function (r) {
										if (!r.exc) {
											frappe.show_alert(
												{
													message: __(
														"Remarks updated successfully for {0}",
														[pr_name.bold()],
													),
													indicator: "green",
												},
												3,
											);

											// Update the row's remarks value in report data
											const row_idx = report.data.findIndex(
												(r) => r.purchase_receipt === pr_name,
											);
											if (row_idx !== -1) {
												report.data[row_idx].remarks = values.remarks;
											}

											// Refresh report to show updated value
											report.refresh();
										} else {
											frappe.msgprint({
												title: __("Error"),
												message: __("Failed to update remarks: {0}", [
													r.exc,
												]),
												indicator: "red",
											});
										}
									},
								});
							},
							__("Edit Remarks"),
							__("Save"),
						);
					});
			}, 300);
		});
	},
};
