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
		const STATUS_ORDER = ["Pattern Issues", "Sewing Pending", "Under Checking", "Completed"];

		// ─── Flatpickr format ──────────────────────────────────────────────────
		// Convert Frappe's date format string (e.g. "dd-mm-yyyy") to flatpickr's
		// token format (e.g. "d-m-Y") so the picker matches all other date columns.
		function getFlatpickrFormat() {
			return frappe.datetime.get_user_date_fmt()
				.toLowerCase()
				.replace("dd", "d")
				.replace("mm", "m")
				.replace("yyyy", "Y");
		}

		// ─── Lazy flatpickr init ───────────────────────────────────────────────
		// Initialise once per input on first click; re-open immediately.
		$wrap.on("click", ".report-date-input", function () {
			const el = this;
			const $el = $(el);

			if ($el.data("fp-ready")) {
				el._flatpickr && el._flatpickr.open();
				return;
			}

			const fp = flatpickr(el, {
				dateFormat: getFlatpickrFormat(),
				// defaultDate expects the display-format string already set as .val()
				defaultDate: $el.val() || null,
				allowInput: true,
				onChange(selectedDates) {
					// Store YYYY-MM-DD internally for saving; display value is
					// already updated by flatpickr in the input itself.
					const storageVal = selectedDates[0]
						? frappe.datetime.obj_to_str(selectedDates[0]).substring(0, 10)
						: "";
					$el.data("storage-value", storageVal);
				},
				onClose(selectedDates) {
					const newStorage = $el.data("storage-value") ?? "";
					const oldStorage = $el.data("old-value") ?? "";

					if (!$el.val()) $el.css("color", "transparent");

					if (newStorage === oldStorage) return;

					saveDate($el, newStorage, oldStorage);
				}
			});

			$el.data("fp-ready", true);
			fp.open();
		});

		$wrap.on("focus", ".report-date-input", function () {
			$(this).css("color", "#333");
		});
		$wrap.on("blur", ".report-date-input", function () {
			if (!$(this).val()) $(this).css("color", "transparent");
		});

		// ─── Date save ─────────────────────────────────────────────────────────

		function saveDate($el, newStorage, oldStorage) {
			$el.css("opacity", 0.6);

			frappe.call({
				method: "frappe.client.set_value",
				args: {
					doctype: "Sales Order",
					name: $el.data("docname"),
					fieldname: $el.data("fieldname"),
					value: newStorage || null
				},
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Saved"), indicator: "green" });
						$el.data("old-value", newStorage);
						$el.data("storage-value", newStorage);
					} else {
						frappe.msgprint(__("Save failed"));
						// Revert display to old user-formatted value
						const revertDisplay = oldStorage
							? frappe.datetime.str_to_user(oldStorage)
							: "";
						$el.val(revertDisplay);
						if ($el[0]._flatpickr) {
							$el[0]._flatpickr.setDate(revertDisplay || null, false);
						}
						$el.data("storage-value", oldStorage);
						if (!revertDisplay) $el.css("color", "transparent");
					}
				},
				always() {
					$el.css("opacity", 1);
				}
			});
		}

		// ─── Status helpers ────────────────────────────────────────────────────

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
			$select.data("old-value", currentValue);
		}

		const saveStatus = frappe.utils.debounce((e) => {
			const $el = $(e.currentTarget);
			const docname = $el.data("docname");
			const newValue = $el.val();
			const oldValue = $el.data("old-value");

			if (newValue === oldValue) return;

			const oldIndex = STATUS_ORDER.indexOf(oldValue);
			const newIndex = STATUS_ORDER.indexOf(newValue);

			if (oldIndex === -1 || newIndex === -1) {
				frappe.msgprint(__("Invalid status."));
				updateDropdownOptions($el);
				return;
			}

			if (newIndex !== oldIndex && newIndex !== oldIndex + 1) {
				frappe.msgprint(__("You can only move to the next stage in the Size Set workflow."));
				updateDropdownOptions($el);
				return;
			}

			$el.css("opacity", 0.6);

			const fieldsToUpdate = { custom_size_set_status: newValue };
			if (newValue === "Completed") {
				fieldsToUpdate.custom_completion_on = frappe.datetime.now_date();
			}

			frappe.call({
				method: "frappe.client.set_value",
				args: {
					doctype: "Sales Order",
					name: docname,
					fieldname: fieldsToUpdate
				},
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Saved"), indicator: "green" });
						if (newValue === "Completed") {
							report.refresh();
						} else {
							updateDropdownOptions($el);
						}
					} else {
						frappe.msgprint(__("Save failed"));
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
		$wrap.on("change", ".report-status-select", saveStatus);
	},

	// ─── Formatter ────────────────────────────────────────────────────────────

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);

		// ── Editable date fields ──────────────────────────────────────────────
		const EDITABLE_DATE_FIELDS = [
			"custom_ppm_date",
			"custom_pcd_committed",
			"custom_size_set_planned_date",
			"custom_size_set_cut_date"
		];

		if (EDITABLE_DATE_FIELDS.includes(column.fieldname)) {
			// displayValue uses Frappe's system date format — same as all other date columns.
			// storageValue (YYYY-MM-DD) is kept in data-old-value / data-storage-value for saving.
			const displayValue = value ? frappe.datetime.str_to_user(value) : "";
			const storageValue = value || "";
			const colorStyle = displayValue ? "color:#333" : "color:transparent";

			return `
				<input
					type="text"
					class="report-date-input"
					data-docname="${data.ocn}"
					data-fieldname="${column.fieldname}"
					data-old-value="${storageValue}"
					data-storage-value="${storageValue}"
					value="${displayValue}"
					readonly
					style="width:100%; padding:3px 6px; border:1px solid #d1d8dd;
					       border-radius:4px; font-size:12px; cursor:pointer;
					       background:#fff; ${colorStyle}">
			`;
		}

		// ── Status column ─────────────────────────────────────────────────────
		if (column.fieldname !== "custom_size_set_status") {
			return default_formatter(value, row, column, data);
		}

		const currentValue = value || "Pattern Issues";

		// Completed rows → read-only badge
		if (currentValue === "Completed") {
			return `
				<span style="
					display:inline-block;
					padding:3px 10px;
					border-radius:12px;
					background:#d4edda;
					color:#155724;
					font-weight:600;
					font-size:12px;
					letter-spacing:0.3px;">
					✓ Completed
				</span>`;
		}

		const STATUS_ORDER = ["Pattern Issues", "Sewing Pending", "Under Checking", "Completed"];
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