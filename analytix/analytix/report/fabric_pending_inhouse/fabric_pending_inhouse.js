// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Fabric Pending Inhouse"] = {

    // // ------------------------------------------------------------------
    // // Filter definitions
    // // ------------------------------------------------------------------
    // filters: [
    //     {
    //         fieldname: "from_date",
    //         label:     __("From Date"),
    //         fieldtype: "Date",
    //         default:   frappe.datetime.add_months(frappe.datetime.get_today(), -1),
    //     },
    //     {
    //         fieldname: "to_date",
    //         label:     __("To Date"),
    //         fieldtype: "Date",
    //         default:   frappe.datetime.get_today(),
    //     },
    //     {
    //         fieldname: "customer",
    //         label:     __("Buyer"),
    //         fieldtype: "Link",
    //         options:   "Customer",
    //     },
    //     {
    //         fieldname: "responsible",
    //         label:     __("Responsible"),
    //         fieldtype: "Select",
    //         options:   "\nFabric\nMerchant\nProduction\nOther",
    //     },
    // ],

    onload(report) {
        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Fabric Pending Inhouse" },
                ],
            });
        }

        report.page.wrapper.on("report-rendered", () => {
            _attach_listeners();
        });
    },

    // ------------------------------------------------------------------
    // Column formatters
    //   - remarks / manager_remarks → <select> dropdowns
    //   - fabric_remarks            → <input type="date">
    //   - balance_to_receive        → orange highlight when negative
    // ------------------------------------------------------------------
    formatter(value, row, column, data, default_formatter) {

        if (column.fieldname === "remarks") {
            return _make_select(data, "remarks", value, [
                { value: "",            label: "—" },
                { value: "Short Close", label: "Short Close" },
            ]);
        }

        if (column.fieldname === "manager_remarks") {
            return _make_select(data, "manager_remarks", value, [
                { value: "",         label: "—" },
                { value: "Approved", label: "Approved" },
            ]);
        }

        if (column.fieldname === "fabric_remarks") {
            return _make_date_input(data, "fabric_remarks", value);
        }

        // Highlight negative balance in orange
        if (column.fieldname === "balance_to_receive" && value < 0) {
            return `<span style="color:#d97706;font-weight:600;">${flt(value, 2)}</span>`;
        }

        return default_formatter(value, row, column, data);
    },

    // ------------------------------------------------------------------
    // After report render — attach change listeners to every interactive cell
    // ------------------------------------------------------------------
    after_datatable_render(datatable) {
        _attach_listeners(datatable);
    },
};

// ------------------------------------------------------------------
// Helpers (module-private)
// ------------------------------------------------------------------

/**
 * Build an HTML <select> element for a report cell.
 */
function _make_select(data, field, current_value, options) {
    if (!data) return current_value || "";

    const ocn    = data.ocn    || "";
    const colour = data.colour || "";

    let html = `<select
        class="fpih-remark-select"
        data-ocn="${frappe.utils.escape_html(ocn)}"
        data-colour="${frappe.utils.escape_html(colour)}"
        data-field="${field}"
        style="width:100%;border:none;background:transparent;font-size:var(--text-sm);"
    >`;

    options.forEach(opt => {
        const selected = (opt.value === (current_value || "")) ? "selected" : "";
        html += `<option value="${opt.value}" ${selected}>${opt.label}</option>`;
    });

    html += `</select>`;
    return html;
}

/**
 * Build an HTML <input type="date"> element for a report cell.
 */
function _make_date_input(data, field, current_value) {
    if (!data) return current_value || "";

    const ocn    = data.ocn    || "";
    const colour = data.colour || "";
    // Frappe stores dates as YYYY-MM-DD which is exactly what <input type="date"> expects
    const val    = current_value || "";

    return `<input
        type="date"
        class="fpih-date-input"
        data-ocn="${frappe.utils.escape_html(ocn)}"
        data-colour="${frappe.utils.escape_html(colour)}"
        data-field="${field}"
        value="${frappe.utils.escape_html(val)}"
        style="width:100%;border:none;background:transparent;font-size:var(--text-sm);color:inherit;"
    />`;
}

/**
 * Attach onChange listeners to all remark selects and date inputs
 * in the rendered table.  Calls the whitelisted Python method to
 * persist the value.
 */
function _attach_listeners(datatable) {
    const $root = datatable
        ? $(datatable.wrapper)
        : $(".dt-scrollable");   // fallback selector

    // ── Select dropdowns ────────────────────────────────────────────
    $root.find(".fpih-remark-select").off("change.fpih").on("change.fpih", function () {
        _save_field($(this), $(this).val());
    });

    // ── Date inputs ─────────────────────────────────────────────────
    $root.find(".fpih-date-input").off("change.fpih").on("change.fpih", function () {
        _save_field($(this), $(this).val());
    });
}

/**
 * Persist a single field value and give visual feedback.
 * Triggers a full report refresh when every interactive cell in the
 * row has a non-empty value (selects + date inputs).
 */
function _save_field($el, value) {
    const ocn            = $el.data("ocn");
    const colour         = $el.data("colour");
    const field          = $el.data("field");
    const $originalColor = $el.css("color");

    // Optimistic UI feedback
    $el.css("color", "#6366f1");

    frappe.call({
        method: "analytix.analytix.report.fabric_pending_inhouse.fabric_pending_inhouse.save_remark",
        args: { ocn, colour, field, value },
        callback(r) {
            if (!r.exc) {
                $el.css("color", "#16a34a");   // green = saved
                setTimeout(() => $el.css("color", $originalColor), 1500);

                // If every interactive cell in this row is filled,
                // refresh so the row moves to the bottom (Rule 4).
                const $row         = $el.closest("tr");
                const $selects     = $row.find(".fpih-remark-select");
                const $dates       = $row.find(".fpih-date-input");
                const selectsFull  = [...$selects].every(s => $(s).val() !== "");
                const datesFull    = [...$dates].every(d => $(d).val() !== "");

                if (selectsFull && datesFull && ($selects.length + $dates.length) > 0) {
                    frappe.query_report.refresh();
                }
            } else {
                $el.css("color", "#dc2626");   // red = error
                frappe.show_alert({ message: __("Failed to save remark"), indicator: "red" });
            }
        },
    });
}