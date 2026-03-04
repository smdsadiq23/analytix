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
		const UPSERT_API   = "analytix.analytix.api.size_set_tracker.upsert_tracker";

		const REQUIRED_DATE_FIELDS = ["ppm_date", "pcd_committed", "size_set_planned_date", "size_set_cut_date"];
		const DATE_FIELD_LABELS = {
			ppm_date:              "PPM Date",
			pcd_committed:         "PCD Committed",
			size_set_planned_date: "Size Set Planned Date",
			size_set_cut_date:     "Size Set Cut Date"
		};

		// ─── Shared upsert helper ──────────────────────────────────────────────
		function upsertTracker({ ocn, style, colour, fields, onSuccess, onFail, $el }) {
			frappe.call({
				method: UPSERT_API,
				args: { ocn, style, colour, fields: JSON.stringify(fields) },
				callback(r) {
					if (!r.exc && r.message) {
						frappe.show_alert({ message: __("Saved"), indicator: "green" });
						onSuccess && onSuccess(r.message);
					} else {
						frappe.msgprint(__("Save failed"));
						onFail && onFail();
					}
				},
				always() { $el && $el.css("opacity", 1); }
			});
		}

		// ─── Date field interactions ───────────────────────────────────────────

		$wrap.on("click", ".report-date-input", function () {
			const $el = $(this);
			if ($el.attr("type") === "date") return;

			const iso = $el.data("iso") || "";
			$el.data("old-iso", iso);
			$el.attr("type", "date").val(iso);

			try { this.showPicker(); } catch (_) { this.focus(); }
		});

		$wrap.on("change", ".report-date-input", function () {
			const $el    = $(this);
			const newIso = $el.val();
			const oldIso = $el.data("old-iso") || "";
			const ocn    = $el.data("ocn");
			const style  = $el.data("style");
			const colour = $el.data("colour");
			const field  = $el.data("fieldname");

			// Swap back to formatted display immediately
			const display = newIso ? frappe.datetime.str_to_user(newIso) : "";
			$el.attr("type", "text").val(display).data("iso", newIso);

			if (newIso === oldIso) return;

			$el.css("opacity", 0.6);

			upsertTracker({
				ocn, style, colour,
				fields: { [field]: newIso || null },
				$el,
				onSuccess() { /* iso already stored above */ },
				onFail() {
					const revert = oldIso ? frappe.datetime.str_to_user(oldIso) : "";
					$el.val(revert).data("iso", oldIso);
				}
			});
		});

		$wrap.on("blur", ".report-date-input", function () {
			const $el = $(this);
			if ($el.attr("type") !== "date") return;
			const iso     = $el.data("iso") || "";
			const display = iso ? frappe.datetime.str_to_user(iso) : "";
			$el.attr("type", "text").val(display);
		});

		// ─── Status helpers ────────────────────────────────────────────────────

		function updateDropdownOptions($select) {
			const currentValue = $select.val();
			const currentIndex = STATUS_ORDER.indexOf(currentValue);

			let allowedOptions = [currentValue];
			if (currentIndex !== -1 && currentIndex < STATUS_ORDER.length - 1) {
				allowedOptions.push(STATUS_ORDER[currentIndex + 1]);
			}

			$select.html(
				allowedOptions
					.map(opt => `<option value="${opt}" ${opt === currentValue ? "selected" : ""}>${opt}</option>`)
					.join("")
			);
			$select.data("old-value", currentValue);
		}

		const saveStatus = frappe.utils.debounce((e) => {
			const $el      = $(e.currentTarget);
			const ocn      = $el.data("ocn");
			const style    = $el.data("style");
			const colour   = $el.data("colour");
			const newValue = $el.val();
			const oldValue = $el.data("old-value");

			if (newValue === oldValue) return;

			const oldIndex = STATUS_ORDER.indexOf(oldValue);
			const newIndex = STATUS_ORDER.indexOf(newValue);

			if (oldIndex === -1 || newIndex === -1) {
				frappe.msgprint(__("Invalid status."));
				$el.val(oldValue);
				updateDropdownOptions($el);
				return;
			}
			if (newIndex !== oldIndex + 1) {
				frappe.msgprint(__("You can only move to the next stage in the Size Set workflow."));
				$el.val(oldValue);
				updateDropdownOptions($el);
				return;
			}

			// ── Mandatory date check before allowing Completed ─────────────────
			// Find sibling date inputs by matching ocn+style+colour attributes
			// (more reliable than closest("tr") in Frappe's report DOM).
			if (newValue === "Completed") {
				const missing = REQUIRED_DATE_FIELDS.filter(f => {
					const $input = $wrap.find(
						`.report-date-input[data-ocn="${ocn}"][data-style="${style}"][data-colour="${colour}"][data-fieldname="${f}"]`
					);
					// data("iso") reads jQuery cache (updated on pick),
					// attr("data-iso") reads the original rendered attribute.
					return !($input.data("iso") || $input.attr("data-iso"));
				});

				if (missing.length) {
					const labels = missing.map(f => `<b>${DATE_FIELD_LABELS[f]}</b>`).join(", ");
					frappe.msgprint(
						__("Please fill in the following before marking as Completed: ") + labels
					);
					$el.val(oldValue);                 // revert visible selection
					updateDropdownOptions($el);        // rebuild options from oldValue
					return;
				}
			}

			$el.css("opacity", 0.6);

			const fields = { size_set_status: newValue };
			if (newValue === "Completed") {
				fields.completion_on = frappe.datetime.now_date();
			}

			upsertTracker({
				ocn, style, colour, fields, $el,
				onSuccess() {
					if (newValue === "Completed") {
						report.refresh();
					} else {
						updateDropdownOptions($el);
					}
				},
				onFail() {
					$el.val(oldValue);
					updateDropdownOptions($el);
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
			"ppm_date",
			"pcd_committed",
			"size_set_planned_date",
			"size_set_cut_date"
		];

		if (EDITABLE_DATE_FIELDS.includes(column.fieldname)) {
			const isoValue     = value || "";
			const displayValue = isoValue ? frappe.datetime.str_to_user(isoValue) : "";

			// Completed rows → plain read-only text
			if (data.size_set_status === "Completed") {
				return `<span style="font-size:12px; color:#333;">${displayValue || "—"}</span>`;
			}

			return `
				<input
					type="text"
					class="report-date-input"
					data-ocn="${data.ocn}"
					data-style="${data.style || ""}"
					data-colour="${data.colour || ""}"
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
		if (column.fieldname !== "size_set_status") {
			return default_formatter(value, row, column, data);
		}

		const currentValue = value || "Pattern Issues";

		if (currentValue === "Completed") {
			return `
				<span style="
					display:inline-block; padding:3px 10px; border-radius:12px;
					background:#d4edda; color:#155724; font-weight:600;
					font-size:12px; letter-spacing:0.3px;">
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
					data-ocn="${data.ocn}"
					data-style="${data.style || ""}"
					data-colour="${data.colour || ""}"
					style="width:100%; padding:4px; border-radius:4px;">
				${options}
			</select>
		`;
	}
};