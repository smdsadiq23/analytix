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

		// ─── Date field interactions ───────────────────────────────────────────
		// Rendered as type="text" (showing user-formatted date) so no browser
		// placeholder appears. On click, swap to type="date" so the native picker
		// opens; on blur/change swap back to type="text" with formatted display.

		$wrap.on("click", ".report-date-input", function () {
			const $el = $(this);
			if ($el.attr("type") === "date") return; // already open

			const iso = $el.data("iso") || "";        // YYYY-MM-DD stored in data attr
			$el.data("old-iso", iso);                 // snapshot for revert

			$el.attr("type", "date").val(iso);

			// showPicker() is supported in Chrome 99+, Edge 99+, Firefox 101+
			try { this.showPicker(); } catch (_) { this.focus(); }
		});

		$wrap.on("change", ".report-date-input", function () {
			const $el = $(this);
			const newIso = $el.val();                 // YYYY-MM-DD from native picker
			const oldIso = $el.data("old-iso") || "";

			// Swap back to text display immediately
			const displayVal = newIso ? frappe.datetime.str_to_user(newIso) : "";
			$el.attr("type", "text").val(displayVal);
			$el.data("iso", newIso);

			if (newIso === oldIso) return;

			$el.css("opacity", 0.6);

			frappe.call({
				method: "frappe.client.set_value",
				args: {
					doctype: "Sales Order",
					name: $el.data("docname"),
					fieldname: $el.data("fieldname"),
					value: newIso || null
				},
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Saved"), indicator: "green" });
					} else {
						frappe.msgprint(__("Save failed"));
						const revertDisplay = oldIso ? frappe.datetime.str_to_user(oldIso) : "";
						$el.val(revertDisplay).data("iso", oldIso);
					}
				},
				always() { $el.css("opacity", 1); }
			});
		});

		// If user clicks away without picking, swap back to text
		$wrap.on("blur", ".report-date-input", function () {
			const $el = $(this);
			if ($el.attr("type") !== "date") return;

			const iso = $el.data("iso") || "";
			const displayVal = iso ? frappe.datetime.str_to_user(iso) : "";
			$el.attr("type", "text").val(displayVal);
		});

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
			// Display in Frappe's user date format — same as all read-only date columns.
			// The raw YYYY-MM-DD is kept in data-iso for the save handler.
			const isoValue = value || "";
			const displayValue = isoValue ? frappe.datetime.str_to_user(isoValue) : "";

			return `
				<input
					type="text"
					class="report-date-input"
					data-docname="${data.ocn}"
					data-fieldname="${column.fieldname}"
					data-iso="${isoValue}"
					value="${displayValue}"
					placeholder=""
					style="width:100%; padding:3px 6px; border:1px solid #d1d8dd;
					       border-radius:4px; font-size:12px; cursor:pointer;
					       background:#fff; color:${displayValue ? "#333" : "#333"};">
			`;
		}

		// ── Status column ─────────────────────────────────────────────────────
		if (column.fieldname !== "custom_size_set_status") {
			return default_formatter(value, row, column, data);
		}

		const currentValue = value || "Pattern Issues";

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